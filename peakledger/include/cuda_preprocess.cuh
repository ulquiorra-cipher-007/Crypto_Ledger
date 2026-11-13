#pragma once

#include <cuda_runtime.h>
#include <cstdint>
#include <cstddef>

namespace Forensic {

constexpr int TRT_INPUT_C = 3;
constexpr int TRT_INPUT_H = 640;
constexpr int TRT_INPUT_W = 640;
constexpr size_t TRT_INPUT_TENSOR_ELEMENTS = TRT_INPUT_C * TRT_INPUT_H * TRT_INPUT_W; // 1,228,800 floats
constexpr size_t TRT_INPUT_TENSOR_BYTES = TRT_INPUT_TENSOR_ELEMENTS * sizeof(float);   // 4,915,200 bytes (~4.69 MB)

/**
 * @brief Standalone CUDA Preprocessor
 * 
 * Ingests raw decoded NV12 luminance buffer (uint8_t* Y-plane) directly from GPU VRAM
 * with zero host memory copies, performs bilinear interpolation resizing to 640x640,
 * normalizes pixel values from [0, 255] to [0.0f, 1.0f], and broadcasts the 1-channel luma
 * across all 3 planar channels (R=Y, G=Y, B=Y) directly into 1x3x640x640 NCHW layout.
 * Runs asynchronously on a designated cudaStream_t.
 */
class CudaPreprocessor {
public:
    explicit CudaPreprocessor(int dst_w = TRT_INPUT_W, int dst_h = TRT_INPUT_H);
    ~CudaPreprocessor() = default;

    CudaPreprocessor(const CudaPreprocessor&) = delete;
    CudaPreprocessor& operator=(const CudaPreprocessor&) = delete;

    /**
     * @brief Asynchronously preprocess NV12 Y-plane into 1x3xHxW planar float32 tensor in VRAM.
     * 
     * @param d_src_y      Device pointer to decoded Y-plane in VRAM.
     * @param src_width    Native frame width in pixels.
     * @param src_height   Native frame height in pixels.
     * @param src_pitch    Stride of Y-plane in bytes (pitch-aware).
     * @param d_dst_tensor Device pointer to pre-allocated NCHW float buffer (3 * dst_w * dst_h).
     * @param stream       CUDA stream for non-blocking asynchronous execution.
     */
    void preprocess(
        const uint8_t* d_src_y,
        int src_width,
        int src_height,
        int src_pitch,
        float* d_dst_tensor,
        cudaStream_t stream = 0
    );

    int target_width() const { return dst_width_; }
    int target_height() const { return dst_height_; }
    size_t tensor_elements() const { return static_cast<size_t>(TRT_INPUT_C) * dst_width_ * dst_height_; }
    size_t tensor_bytes() const { return tensor_elements() * sizeof(float); }

private:
    int dst_width_;
    int dst_height_;
};

} // namespace Forensic
