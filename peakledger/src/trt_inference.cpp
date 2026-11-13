#include "trt_inference.hpp"
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <cstring>

namespace Forensic {

void TrtLogger::log(Severity severity, const char* msg) noexcept {
    // Only report warnings and errors to keep console telemetry clean
    if (severity == Severity::kERROR || severity == Severity::kINTERNAL_ERROR) {
        std::cerr << "[TensorRT ERROR] " << msg << std::endl;
    } else if (severity == Severity::kWARNING) {
        std::cerr << "[TensorRT WARNING] " << msg << std::endl;
    }
}

TrtInferenceEngine::TrtInferenceEngine(const std::string& engine_path, cudaStream_t stream)
    : engine_path_(engine_path), stream_(stream) {
    for (size_t i = 0; i < NUM_SLOTS; ++i) {
        slots_[i].d_input = nullptr;
        slots_[i].d_output = nullptr;
        slots_[i].ready_event = nullptr;
    }
}

TrtInferenceEngine::~TrtInferenceEngine() {
    free_buffers(stream_);
}

void TrtInferenceEngine::allocate_buffers(cudaStream_t stream) {
    for (size_t s = 0; s < NUM_SLOTS; ++s) {
        // Allocate double-buffered input/output memory asynchronously on inference stream
        cudaError_t err_in = cudaMallocAsync(
            reinterpret_cast<void**>(&slots_[s].d_input),
            TRT_INPUT_TENSOR_BYTES,
            stream
        );
        if (err_in != cudaSuccess) {
            throw std::runtime_error("cudaMallocAsync failed for TRT input buffer: " + std::string(cudaGetErrorString(err_in)));
        }

        cudaError_t err_out = cudaMallocAsync(
            reinterpret_cast<void**>(&slots_[s].d_output),
            TRT_OUTPUT_BYTES,
            stream
        );
        if (err_out != cudaSuccess) {
            throw std::runtime_error("cudaMallocAsync failed for TRT output buffer: " + std::string(cudaGetErrorString(err_out)));
        }

        cudaError_t err_evt = cudaEventCreateWithFlags(&slots_[s].ready_event, cudaEventDisableTiming);
        if (err_evt != cudaSuccess) {
            throw std::runtime_error("cudaEventCreateWithFlags failed: " + std::string(cudaGetErrorString(err_evt)));
        }
    }
}

void TrtInferenceEngine::free_buffers(cudaStream_t stream) {
    for (size_t s = 0; s < NUM_SLOTS; ++s) {
        if (slots_[s].ready_event) {
            cudaEventDestroy(slots_[s].ready_event);
            slots_[s].ready_event = nullptr;
        }
        if (slots_[s].d_input) {
            cudaFreeAsync(slots_[s].d_input, stream);
            slots_[s].d_input = nullptr;
        }
        if (slots_[s].d_output) {
            cudaFreeAsync(slots_[s].d_output, stream);
            slots_[s].d_output = nullptr;
        }
    }
}

bool TrtInferenceEngine::initialize(cudaStream_t stream) {
    if (initialized_) return true;

    if (stream) {
        stream_ = stream;
    }

    std::ifstream file(engine_path_, std::ios::binary);
    if (!file.is_open()) {
        std::cerr << "[-] Error: Failed to open TensorRT engine file at: " << engine_path_ << std::endl;
        return false;
    }

    file.seekg(0, std::ios::end);
    size_t size = file.tellg();
    file.seekg(0, std::ios::beg);

    std::vector<char> buffer(size);
    file.read(buffer.data(), size);
    file.close();

    runtime_.reset(nvinfer1::createInferRuntime(logger_));
    if (!runtime_) {
        std::cerr << "[-] Error: Failed to create TensorRT InferRuntime." << std::endl;
        return false;
    }

    engine_.reset(runtime_->deserializeCudaEngine(buffer.data(), size));
    if (!engine_) {
        std::cerr << "[-] Error: Failed to deserialize CUDA engine from: " << engine_path_ << std::endl;
        return false;
    }

    context_.reset(engine_->createExecutionContext());
    if (!context_) {
        std::cerr << "[-] Error: Failed to create TensorRT ExecutionContext." << std::endl;
        return false;
    }

    // Inspect and discover tensor bindings in TensorRT 10/11
    int nb_io = engine_->getNbIOTensors();
    for (int i = 0; i < nb_io; ++i) {
        const char* name = engine_->getIOTensorName(i);
        nvinfer1::TensorIOMode mode = engine_->getTensorIOMode(name);
        if (mode == nvinfer1::TensorIOMode::kINPUT) {
            input_name_ = name;
            nvinfer1::Dims dims = engine_->getTensorShape(name);
            // If dynamic batching, set input shape explicitly
            if (dims.d[0] == -1) {
                dims.d[0] = TRT_INFER_BATCH;
                context_->setInputShape(name, dims);
            }
        } else if (mode == nvinfer1::TensorIOMode::kOUTPUT) {
            output_name_ = name;
        }
    }

    // Allocate double-buffered device memory slots
    allocate_buffers(stream_);

    initialized_ = true;
    return true;
}

float* TrtInferenceEngine::enqueue(const float* d_input_tensor, cudaStream_t stream) {
    if (!initialized_) {
        throw std::runtime_error("TrtInferenceEngine::enqueue called on uninitialized engine");
    }

    cudaStream_t exec_stream = stream ? stream : stream_;

    // Select current ping-pong slot
    TrtBufferSlot& slot = slots_[active_slot_];

    // If caller provided external device input tensor, copy it or bind it
    if (d_input_tensor && d_input_tensor != slot.d_input) {
        cudaMemcpyAsync(
            slot.d_input,
            d_input_tensor,
            TRT_INPUT_TENSOR_BYTES,
            cudaMemcpyDeviceToDevice,
            exec_stream
        );
    }

    // Bind input and output addresses via TensorRT 10/11 enqueueV3 API
    context_->setInputTensorAddress(input_name_.c_str(), slot.d_input);
    context_->setOutputTensorAddress(output_name_.c_str(), slot.d_output);

    // Enqueue inference execution asynchronously
    if (!context_->enqueueV3(exec_stream)) {
        throw std::runtime_error("TensorRT execution context enqueueV3 failed");
    }

    // Record completion event for this slot
    cudaEventRecord(slot.ready_event, exec_stream);

    float* output_ptr = slot.d_output;

    // Advance active slot index to double-buffer the next frame
    active_slot_ = (active_slot_ + 1) % NUM_SLOTS;

    return output_ptr;
}

float* TrtInferenceEngine::infer_nv12(
    CudaPreprocessor& preprocessor,
    const uint8_t* d_y_plane,
    int src_width,
    int src_height,
    int src_pitch,
    cudaStream_t stream
) {
    if (!initialized_) {
        throw std::runtime_error("TrtInferenceEngine::infer_nv12 called on uninitialized engine");
    }

    cudaStream_t exec_stream = stream ? stream : stream_;
    TrtBufferSlot& slot = slots_[active_slot_];

    // Zero-copy resize, normalize, and broadcast directly into current slot's input buffer
    preprocessor.preprocess(d_y_plane, src_width, src_height, src_pitch, slot.d_input, exec_stream);

    // Enqueue execution using slot.d_input
    return enqueue(slot.d_input, exec_stream);
}

void TrtInferenceEngine::synchronize(cudaStream_t stream) {
    cudaStream_t sync_stream = stream ? stream : stream_;
    if (sync_stream) {
        cudaStreamSynchronize(sync_stream);
    } else {
        cudaDeviceSynchronize();
    }
}

std::string TrtInferenceEngine::get_trtexec_cli_command(
    const std::string& onnx_path,
    const std::string& engine_out
) {
    return "./bin/trtexec --onnx=" + onnx_path + " --saveEngine=" + engine_out + " --fp16";
}

} // namespace Forensic
