#pragma once

#include <NvInfer.h>
#include <cuda_runtime.h>
#include <string>
#include <vector>
#include <memory>
#include <cstdint>
#include <cstddef>
#include "cuda_preprocess.cuh"

namespace Forensic {

// Target input/output shapes for YOLO11 / YOLOv8 architecture
constexpr int TRT_INFER_BATCH = 1;
constexpr int TRT_INFER_CHANNELS = 3;
constexpr int TRT_INFER_HEIGHT = 640;
constexpr int TRT_INFER_WIDTH = 640;

constexpr int TRT_OUTPUT_CHANNELS = 84;   // 4 box coordinates (cx, cy, w, h) + 80 COCO classes
constexpr int TRT_OUTPUT_ANCHORS = 8400;  // 8400 prediction candidates across the feature pyramid
constexpr size_t TRT_OUTPUT_ELEMENTS = TRT_OUTPUT_CHANNELS * TRT_OUTPUT_ANCHORS; // 705,600 floats
constexpr size_t TRT_OUTPUT_BYTES = TRT_OUTPUT_ELEMENTS * sizeof(float);          // 2,822,400 bytes (~2.69 MB)

/**
 * @brief Double-buffered execution binding slot to eliminate pipeline bubbles
 * between NVDEC decoding/preprocessing and TensorRT GPU inference.
 */
struct TrtBufferSlot {
    float* d_input{nullptr};          // 1 x 3 x 640 x 640 FP32 (allocated via cudaMallocAsync)
    float* d_output{nullptr};         // 1 x 84 x 8400 FP32 (allocated via cudaMallocAsync)
    cudaEvent_t ready_event{nullptr}; // Signaled when inference completes on stream
};

/**
 * @brief Thread-safe TensorRT 10/11 Logger
 */
class TrtLogger : public nvinfer1::ILogger {
public:
    void log(Severity severity, const char* msg) noexcept override;
};

/**
 * @brief Standalone TensorRT 10/11 Execution Wrapper
 * 
 * Interfacing via IExecutionContext::enqueueV3 with async memory management (cudaMallocAsync)
 * and double-buffered ping-pong execution slots.
 */
class TrtInferenceEngine {
public:
    explicit TrtInferenceEngine(
        const std::string& engine_path = "models/model.engine",
        cudaStream_t stream = nullptr
    );
    ~TrtInferenceEngine();

    TrtInferenceEngine(const TrtInferenceEngine&) = delete;
    TrtInferenceEngine& operator=(const TrtInferenceEngine&) = delete;

    /**
     * @brief Load and deserialize engine, configure execution context,
     * and allocate double-buffered device memory bindings on the stream.
     */
    bool initialize(cudaStream_t stream = nullptr);

    /**
     * @brief Enqueue inference asynchronously using double-buffered bindings (enqueueV3).
     * 
     * @param d_input_tensor  Device pointer to 1x3x640x640 NCHW tensor (from CudaPreprocessor).
     *                        If null, uses the active slot's d_input buffer directly.
     * @param stream          Inference stream.
     * @return Output device pointer (1 x 84 x 8400 FP32) of the executed slot.
     */
    float* enqueue(const float* d_input_tensor = nullptr, cudaStream_t stream = nullptr);

    /**
     * @brief High-throughput zero-copy end-to-end inference from NV12 Y-plane.
     * Integrates CudaPreprocessor with TrtInferenceEngine directly on GPU VRAM.
     */
    float* infer_nv12(
        CudaPreprocessor& preprocessor,
        const uint8_t* d_y_plane,
        int src_width,
        int src_height,
        int src_pitch,
        cudaStream_t stream = nullptr
    );

    /**
     * @brief Synchronize the active inference stream / slot.
     */
    void synchronize(cudaStream_t stream = nullptr);

    /**
     * @brief Returns active slot index (0 or 1).
     */
    size_t active_slot_index() const { return active_slot_; }

    /**
     * @brief Pointer to the most recent output tensor buffer in device VRAM.
     */
    float* get_current_output() const { return slots_[active_slot_].d_output; }

    /**
     * @brief Pointer to the active slot's input buffer in device VRAM.
     */
    float* get_current_input() const { return slots_[active_slot_].d_input; }

    bool is_initialized() const { return initialized_; }
    const std::string& engine_path() const { return engine_path_; }
    const std::string& input_tensor_name() const { return input_name_; }
    const std::string& output_tensor_name() const { return output_name_; }

    /**
     * @brief Automated CLI conversion command using trtexec with FP16 precision.
     */
    static std::string get_trtexec_cli_command(
        const std::string& onnx_path = "yolo11n.onnx",
        const std::string& engine_out = "models/yolo11n_fp16.engine"
    );

private:
    std::string engine_path_;
    std::string input_name_{"images"};
    std::string output_name_{"output0"};

    TrtLogger logger_;
    std::unique_ptr<nvinfer1::IRuntime> runtime_;
    std::unique_ptr<nvinfer1::ICudaEngine> engine_;
    std::unique_ptr<nvinfer1::IExecutionContext> context_;

    static constexpr size_t NUM_SLOTS = 2; // Double-buffering ping-pong
    TrtBufferSlot slots_[NUM_SLOTS];
    size_t active_slot_{0};
    cudaStream_t stream_{nullptr};
    bool initialized_{false};

    void allocate_buffers(cudaStream_t stream);
    void free_buffers(cudaStream_t stream);
};

} // namespace Forensic
