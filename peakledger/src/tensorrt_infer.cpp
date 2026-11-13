#include "tensorrt_infer.hpp"
#include <iostream>
#include <fstream>
#include <vector>
#include <cstring>
#include <cmath>
#include <algorithm>

namespace Forensic {

void TRTLogger::log(Severity severity, const char* msg) noexcept {
    if (severity <= Severity::kWARNING) {
        std::cout << "[TensorRT] " << msg << std::endl;
    }
}

TensorRTEngine::TensorRTEngine(const std::string& engine_path)
    : m_engine_path(engine_path) {
}

TensorRTEngine::~TensorRTEngine() {
    if (m_d_input_tensor) {
        cudaFree(m_d_input_tensor);
        m_d_input_tensor = nullptr;
    }
    if (m_d_output_tensor) {
        cudaFree(m_d_output_tensor);
        m_d_output_tensor = nullptr;
    }
    if (m_context) {
        delete m_context;
        m_context = nullptr;
    }
    if (m_engine) {
        delete m_engine;
        m_engine = nullptr;
    }
    if (m_runtime) {
        delete m_runtime;
        m_runtime = nullptr;
    }
}

VramProfile TensorRTEngine::initializeAndScale() {
    int device = 0;
    cudaGetDevice(&device);
    cudaDeviceProp props;
    if (cudaGetDeviceProperties(&props, device) == cudaSuccess) {
        applyVramConstraints(props.totalGlobalMem);
    }

    if (loadEngineFile()) {
        std::cout << "[TensorRT] Engine loaded successfully. Profile: " 
                  << (m_profile == VramProfile::DESKTOP ? "DESKTOP (>8GB VRAM)" : "LAPTOP (<8GB VRAM)")
                  << " | Batch Size: " << m_batch_size << std::endl;
    }

    return m_profile;
}

void TensorRTEngine::applyVramConstraints(size_t total_global_mem) {
    constexpr size_t EIGHT_GB = 8ULL * 1024 * 1024 * 1024;
    if (total_global_mem < EIGHT_GB) {
        m_profile = VramProfile::LAPTOP;
        m_batch_size = 1;
    } else {
        m_profile = VramProfile::DESKTOP;
        m_batch_size = 4;
    }
}

bool TensorRTEngine::loadEngineFile() {
    std::ifstream file(m_engine_path, std::ios::binary);
    if (!file.good()) {
        return false;
    }

    file.seekg(0, std::ios::end);
    size_t size = file.tellg();
    file.seekg(0, std::ios::beg);

    std::vector<char> engine_data(size);
    file.read(engine_data.data(), size);
    file.close();

    m_runtime = nvinfer1::createInferRuntime(m_logger);
    if (!m_runtime) {
        return false;
    }

    m_engine = m_runtime->deserializeCudaEngine(engine_data.data(), size);
    if (!m_engine) {
        return false;
    }

    m_context = m_engine->createExecutionContext();
    if (!m_context) {
        return false;
    }

    int num_tensors = m_engine->getNbIOTensors();
    for (int i = 0; i < num_tensors; ++i) {
        const char* name = m_engine->getIOTensorName(i);
        nvinfer1::TensorIOMode mode = m_engine->getTensorIOMode(name);
        nvinfer1::Dims dims = m_engine->getTensorShape(name);

        size_t tensor_elements = 1;
        for (int d = 0; d < dims.nbDims; ++d) {
            tensor_elements *= (dims.d[d] > 0 ? dims.d[d] : 1);
        }

        if (mode == nvinfer1::TensorIOMode::kINPUT) {
            m_input_size = tensor_elements * sizeof(float);
            if (dims.nbDims >= 4) {
                m_input_h = dims.d[2];
                m_input_w = dims.d[3];
            }
        } else if (mode == nvinfer1::TensorIOMode::kOUTPUT) {
            m_output_size = tensor_elements * sizeof(float);
        }
    }

    if (m_input_size > 0) cudaMalloc(&m_d_input_tensor, m_input_size);
    if (m_output_size > 0) cudaMalloc(&m_d_output_tensor, m_output_size);

    return true;
}

bool TensorRTEngine::infer(
    const uint8_t* /*d_y_plane*/,
    int /*width*/,
    int /*height*/,
    int /*pitch*/,
    std::vector<Detection>& out_detections,
    cudaStream_t stream
) {
    if (!m_context || !m_d_input_tensor || !m_d_output_tensor) {
        return false;
    }

    int num_tensors = m_engine->getNbIOTensors();
    for (int i = 0; i < num_tensors; ++i) {
        const char* name = m_engine->getIOTensorName(i);
        nvinfer1::TensorIOMode mode = m_engine->getTensorIOMode(name);

        if (mode == nvinfer1::TensorIOMode::kINPUT) {
            m_context->setTensorAddress(name, m_d_input_tensor);
        } else if (mode == nvinfer1::TensorIOMode::kOUTPUT) {
            m_context->setTensorAddress(name, m_d_output_tensor);
        }
    }

    bool status = m_context->enqueueV3(stream);
    out_detections.clear();
    return status;
}

uint8_t TensorRTEngine::encodeBoustrophedonToken(
    const Detection& det,
    int cell_x,
    int cell_y,
    float dx,
    float dy
) const {
    bool is_even_row = ((cell_y % 2) == 0);
    int effective_x = is_even_row ? cell_x : (31 - cell_x);

    uint8_t class_id_part = static_cast<uint8_t>(det.class_id) & 0x03; // 2 bits
    uint8_t trajectory_part = (std::abs(dx) > std::abs(dy)) ? 0x01 : 0x00; // 1 bit
    uint8_t row_parity_part = is_even_row ? 0x01 : 0x00; // 1 bit
    uint8_t grid_offset_part = static_cast<uint8_t>(effective_x) & 0x01; // 1 bit

    uint8_t token_5bit = (class_id_part << 3) | 
                         (trajectory_part << 2) | 
                         (row_parity_part << 1) | 
                         (grid_offset_part);

    return token_5bit & 0x1F;
}

} // namespace Forensic
