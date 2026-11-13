#pragma once

#include "common.hpp"
#include <string>
#include <vector>
#include <memory>
#include <cuda_runtime.h>
#include <NvInfer.h>

namespace Forensic {

enum class VramProfile {
    LAPTOP,  // < 8GB VRAM (Target footprint < 2.5GB, reduced batch)
    DESKTOP  // >= 8GB VRAM (RTX 5070 Ti 16GB, maximized workspace)
};

struct Detection {
    float x1{0.0f};
    float y1{0.0f};
    float x2{0.0f};
    float y2{0.0f};
    int class_id{0};
    float confidence{0.0f};
};

class TRTLogger : public nvinfer1::ILogger {
public:
    void log(Severity severity, const char* msg) noexcept override;
};

class TensorRTEngine {
public:
    explicit TensorRTEngine(const std::string& engine_path = "models/model.engine");
    ~TensorRTEngine();

    TensorRTEngine(const TensorRTEngine&) = delete;
    TensorRTEngine& operator=(const TensorRTEngine&) = delete;

    VramProfile initializeAndScale();
    bool is_loaded() const { return m_engine != nullptr; }

    bool infer(
        const uint8_t* d_y_plane,
        int width,
        int height,
        int pitch,
        std::vector<Detection>& out_detections,
        cudaStream_t stream = nullptr
    );

    uint8_t encodeBoustrophedonToken(
        const Detection& det,
        int cell_x,
        int cell_y,
        float dx,
        float dy
    ) const;

    VramProfile getProfile() const { return m_profile; }
    int getBatchSize() const { return m_batch_size; }

private:
    std::string m_engine_path;
    VramProfile m_profile{VramProfile::LAPTOP};
    int m_batch_size{1};

    TRTLogger m_logger;
    nvinfer1::IRuntime* m_runtime{nullptr};
    nvinfer1::ICudaEngine* m_engine{nullptr};
    nvinfer1::IExecutionContext* m_context{nullptr};

    void* m_d_input_tensor{nullptr};
    void* m_d_output_tensor{nullptr};

    int m_input_w{640};
    int m_input_h{640};
    size_t m_input_size{0};
    size_t m_output_size{0};

    bool loadEngineFile();
    void applyVramConstraints(size_t total_global_mem);
};

} // namespace Forensic
