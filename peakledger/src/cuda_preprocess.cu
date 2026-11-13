#include "cuda_preprocess.cuh"
#include <stdexcept>
#include <string>

namespace Forensic {

__global__ void preprocess_nv12_y_to_nchw_kernel(
    const uint8_t* __restrict__ d_src_y,
    int src_width,
    int src_height,
    int src_pitch,
    float* __restrict__ d_dst_nchw,
    int dst_width,
    int dst_height
) {
    int x_dst = blockIdx.x * blockDim.x + threadIdx.x;
    int y_dst = blockIdx.y * blockDim.y + threadIdx.y;

    if (x_dst >= dst_width || y_dst >= dst_height) return;

    // Coordinate mapping with center pixel alignment
    float scale_x = static_cast<float>(src_width) / static_cast<float>(dst_width);
    float scale_y = static_cast<float>(src_height) / static_cast<float>(dst_height);

    float src_x = (static_cast<float>(x_dst) + 0.5f) * scale_x - 0.5f;
    float src_y = (static_cast<float>(y_dst) + 0.5f) * scale_y - 0.5f;

    // Boundary clamp
    src_x = fmaxf(0.0f, fminf(src_x, static_cast<float>(src_width - 1)));
    src_y = fmaxf(0.0f, fminf(src_y, static_cast<float>(src_height - 1)));

    int x0 = static_cast<int>(src_x);
    int y0 = static_cast<int>(src_y);
    int x1 = min(x0 + 1, src_width - 1);
    int y1 = min(y0 + 1, src_height - 1);

    float wx = src_x - static_cast<float>(x0);
    float wy = src_y - static_cast<float>(y0);

    // Read four neighboring luminance pixels using pitch offset
    float v00 = static_cast<float>(d_src_y[y0 * src_pitch + x0]);
    float v10 = static_cast<float>(d_src_y[y0 * src_pitch + x1]);
    float v01 = static_cast<float>(d_src_y[y1 * src_pitch + x0]);
    float v11 = static_cast<float>(d_src_y[y1 * src_pitch + x1]);

    // Bilinear interpolation
    float val = (1.0f - wx) * (1.0f - wy) * v00 +
                wx * (1.0f - wy) * v10 +
                (1.0f - wx) * wy * v01 +
                wx * wy * v11;

    // Normalize [0, 255] -> [0.0f, 1.0f]
    float norm_val = val * (1.0f / 255.0f);

    // Planar NCHW layout (1 x 3 x dst_height x dst_width)
    int plane_size = dst_width * dst_height;
    int out_idx = y_dst * dst_width + x_dst;

    d_dst_nchw[0 * plane_size + out_idx] = norm_val; // Channel 0 (R)
    d_dst_nchw[1 * plane_size + out_idx] = norm_val; // Channel 1 (G)
    d_dst_nchw[2 * plane_size + out_idx] = norm_val; // Channel 2 (B)
}

CudaPreprocessor::CudaPreprocessor(int dst_w, int dst_h)
    : dst_width_(dst_w), dst_height_(dst_h) {
    if (dst_width_ <= 0 || dst_height_ <= 0) {
        throw std::invalid_argument("Target dimensions must be positive integers");
    }
}

void CudaPreprocessor::preprocess(
    const uint8_t* d_src_y,
    int src_width,
    int src_height,
    int src_pitch,
    float* d_dst_tensor,
    cudaStream_t stream
) {
    if (!d_src_y || !d_dst_tensor) {
        throw std::invalid_argument("Device pointers cannot be null in CudaPreprocessor::preprocess");
    }
    if (src_width <= 0 || src_height <= 0 || src_pitch < src_width) {
        throw std::invalid_argument("Invalid source geometry in CudaPreprocessor::preprocess");
    }

    dim3 block(16, 16);
    dim3 grid(
        (dst_width_ + block.x - 1) / block.x,
        (dst_height_ + block.y - 1) / block.y
    );

    preprocess_nv12_y_to_nchw_kernel<<<grid, block, 0, stream>>>(
        d_src_y,
        src_width,
        src_height,
        src_pitch,
        d_dst_tensor,
        dst_width_,
        dst_height_
    );

    cudaError_t err = cudaGetLastError();
    if (err != cudaSuccess) {
        throw std::runtime_error(std::string("CUDA kernel launch failed in CudaPreprocessor: ") + cudaGetErrorString(err));
    }
}

} // namespace Forensic
