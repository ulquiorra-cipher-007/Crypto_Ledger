#include "cuda_spatial_hash.cuh"
#include <iostream>
#include <stdexcept>
#include <cstring>

namespace Forensic {

#define FULL_MASK 0xffffffff

__global__ void integer_spatial_hash_nv12_kernel(
    const uint8_t* __restrict__ d_y_plane,
    const uint8_t* __restrict__ d_uv_plane,
    int width,
    int height,
    int pitch_y,
    int pitch_uv,
    uint8_t* __restrict__ d_out_color_sig
) {
    const uint32_t cx = blockIdx.x; // [0..31]
    const uint32_t cy = blockIdx.y; // [0..15]
    const uint32_t cell_idx = cy * GRID_COLS + cx;

    const uint32_t x_start = (cx * static_cast<uint32_t>(width)) / static_cast<uint32_t>(GRID_COLS);
    const uint32_t x_end   = ((cx + 1) * static_cast<uint32_t>(width)) / static_cast<uint32_t>(GRID_COLS);
    const uint32_t y_start = (cy * static_cast<uint32_t>(height)) / static_cast<uint32_t>(GRID_ROWS);
    const uint32_t y_end   = ((cy + 1) * static_cast<uint32_t>(height)) / static_cast<uint32_t>(GRID_ROWS);

    const uint32_t cell_w = x_end - x_start;
    const uint32_t cell_h = y_end - y_start;
    const uint32_t pixel_count_y = cell_w * cell_h;

    const uint32_t tid = threadIdx.x;
    const uint32_t bdim = blockDim.x;

    // 1. Coalesced raster traversal across luma (Y) pixels
    uint64_t thread_sum_y = 0;
    for (uint32_t idx = tid; idx < pixel_count_y; idx += bdim) {
        uint32_t local_y = idx / cell_w;
        uint32_t local_x = idx % cell_w;
        uint32_t py = y_start + local_y;
        uint32_t px = x_start + local_x;
        
        thread_sum_y += static_cast<uint64_t>(d_y_plane[py * static_cast<size_t>(pitch_y) + px]);
    }

    // 2. Coalesced raster traversal across interleaved chrominance (UV) pixels
    uint64_t thread_sum_u = 0;
    uint64_t thread_sum_v = 0;
    uint32_t pixel_count_uv = 0;

    if (d_uv_plane != nullptr) {
        const uint32_t uv_x_start = x_start >> 1;
        const uint32_t uv_x_end   = x_end >> 1;
        const uint32_t uv_y_start = y_start >> 1;
        const uint32_t uv_y_end   = y_end >> 1;

        const uint32_t uv_w = uv_x_end - uv_x_start;
        const uint32_t uv_h = uv_y_end - uv_y_start;
        pixel_count_uv = uv_w * uv_h;

        for (uint32_t idx = tid; idx < pixel_count_uv; idx += bdim) {
            uint32_t local_y = idx / uv_w;
            uint32_t local_x = idx % uv_w;
            uint32_t py = uv_y_start + local_y;
            uint32_t px = (uv_x_start + local_x) << 1; // Interleaved U at px, V at px+1
            
            size_t uv_offset = py * static_cast<size_t>(pitch_uv) + px;
            thread_sum_u += static_cast<uint64_t>(d_uv_plane[uv_offset]);
            thread_sum_v += static_cast<uint64_t>(d_uv_plane[uv_offset + 1]);
        }
    }

    // 3. Warp-level integer reduction
    for (int offset = 16; offset > 0; offset >>= 1) {
        thread_sum_y += __shfl_down_sync(FULL_MASK, thread_sum_y, offset);
        if (d_uv_plane != nullptr) {
            thread_sum_u += __shfl_down_sync(FULL_MASK, thread_sum_u, offset);
            thread_sum_v += __shfl_down_sync(FULL_MASK, thread_sum_v, offset);
        }
    }

    __shared__ uint64_t warp_sums_y[4];
    __shared__ uint64_t warp_sums_u[4];
    __shared__ uint64_t warp_sums_v[4];
    const int lane = tid & 31;
    const int warp_id = tid >> 5;

    if (lane == 0) {
        warp_sums_y[warp_id] = thread_sum_y;
        if (d_uv_plane != nullptr) {
            warp_sums_u[warp_id] = thread_sum_u;
            warp_sums_v[warp_id] = thread_sum_v;
        }
    }
    __syncthreads();

    // 4. Block-level reduction by thread 0 with strictly integer half-up rounding
    if (tid == 0) {
        const uint64_t total_sum_y = warp_sums_y[0] + warp_sums_y[1] + warp_sums_y[2] + warp_sums_y[3];
        uint32_t avg_y = 0;
        if (pixel_count_y > 0) {
            avg_y = static_cast<uint32_t>((total_sum_y + (pixel_count_y >> 1)) / pixel_count_y);
        }
        d_out_color_sig[cell_idx] = static_cast<uint8_t>(avg_y > 255 ? 255 : avg_y);

        if (d_uv_plane != nullptr && pixel_count_uv > 0) {
            const uint64_t total_sum_u = warp_sums_u[0] + warp_sums_u[1] + warp_sums_u[2] + warp_sums_u[3];
            const uint64_t total_sum_v = warp_sums_v[0] + warp_sums_v[1] + warp_sums_v[2] + warp_sums_v[3];

            uint32_t avg_u = static_cast<uint32_t>((total_sum_u + (pixel_count_uv >> 1)) / pixel_count_uv);
            uint32_t avg_v = static_cast<uint32_t>((total_sum_v + (pixel_count_uv >> 1)) / pixel_count_uv);

            d_out_color_sig[GRID_CELLS + cell_idx]     = static_cast<uint8_t>(avg_u > 255 ? 255 : avg_u);
            d_out_color_sig[GRID_CELLS * 2 + cell_idx] = static_cast<uint8_t>(avg_v > 255 ? 255 : avg_v);
        } else {
            // Neutral chroma fallback (128)
            d_out_color_sig[GRID_CELLS + cell_idx]     = 128;
            d_out_color_sig[GRID_CELLS * 2 + cell_idx] = 128;
        }
    }
}

void launch_integer_spatial_hash_kernel(
    const uint8_t* d_y_plane,
    const uint8_t* d_uv_plane,
    int width,
    int height,
    int pitch_y,
    int pitch_uv,
    uint8_t* d_out_color_sig,
    cudaStream_t stream
) {
    dim3 grid(GRID_COLS, GRID_ROWS); // 32x16 = 512 blocks
    dim3 block(128, 1, 1);           // 128 threads per block (4 warps)

    integer_spatial_hash_nv12_kernel<<<grid, block, 0, stream>>>(
        d_y_plane, d_uv_plane, width, height, pitch_y, pitch_uv, d_out_color_sig
    );
}

void launch_integer_spatial_hash_kernel(
    const uint8_t* d_y_plane,
    int width,
    int height,
    int pitch,
    uint8_t* d_out_signature,
    cudaStream_t stream
) {
    launch_integer_spatial_hash_kernel(
        d_y_plane, nullptr, width, height, pitch, pitch, d_out_signature, stream
    );
}

CudaSpatialHasher::CudaSpatialHasher(int device_id) : device_id_(device_id) {
    cudaError_t err = cudaSetDevice(device_id_);
    if (err != cudaSuccess) {
        throw std::runtime_error("cudaSetDevice failed: " + std::string(cudaGetErrorString(err)));
    }

    err = cudaStreamCreateWithFlags(&stream_, cudaStreamNonBlocking);
    if (err != cudaSuccess) {
        throw std::runtime_error("cudaStreamCreateWithFlags failed: " + std::string(cudaGetErrorString(err)));
    }

    err = cudaMalloc(&d_signature_, COLOR_GRID_BYTES);
    if (err != cudaSuccess) {
        throw std::runtime_error("cudaMalloc for d_signature failed: " + std::string(cudaGetErrorString(err)));
    }

    err = cudaHostAlloc(&h_pinned_signature_, COLOR_GRID_BYTES, cudaHostAllocDefault);
    if (err != cudaSuccess) {
        throw std::runtime_error("cudaHostAlloc for h_pinned_signature failed: " + std::string(cudaGetErrorString(err)));
    }
}

CudaSpatialHasher::~CudaSpatialHasher() {
    if (stream_) {
        cudaStreamSynchronize(stream_);
        cudaStreamDestroy(stream_);
        stream_ = nullptr;
    }
    if (d_signature_) {
        cudaFree(d_signature_);
        d_signature_ = nullptr;
    }
    if (h_pinned_signature_) {
        cudaFreeHost(h_pinned_signature_);
        h_pinned_signature_ = nullptr;
    }
}

void CudaSpatialHasher::hash_frame_nv12_async(
    const uint8_t* d_y_plane,
    const uint8_t* d_uv_plane,
    int width,
    int height,
    int pitch_y,
    int pitch_uv
) {
    launch_integer_spatial_hash_kernel(
        d_y_plane, d_uv_plane, width, height, pitch_y, pitch_uv, d_signature_, stream_
    );
    
    // Initiate asynchronous PCIe DMA transfer to pinned host memory (1536 bytes)
    cudaMemcpyAsync(
        h_pinned_signature_,
        d_signature_,
        COLOR_GRID_BYTES,
        cudaMemcpyDeviceToHost,
        stream_
    );
}

void CudaSpatialHasher::hash_frame_async(const uint8_t* d_y_plane, int width, int height, int pitch) {
    hash_frame_nv12_async(d_y_plane, nullptr, width, height, pitch, pitch);
}

void CudaSpatialHasher::synchronize_color_signature(ColorGridSignature& out_color_sig, GridSignature* out_luma_sig) {
    cudaError_t err = cudaStreamSynchronize(stream_);
    if (err != cudaSuccess) {
        throw std::runtime_error("cudaStreamSynchronize failed: " + std::string(cudaGetErrorString(err)));
    }
    std::memcpy(out_color_sig.data(), h_pinned_signature_, COLOR_GRID_BYTES);
    if (out_luma_sig != nullptr) {
        std::memcpy(out_luma_sig->data(), h_pinned_signature_, GRID_CELLS);
    }
}

void CudaSpatialHasher::synchronize_signature(GridSignature& out_sig) {
    cudaError_t err = cudaStreamSynchronize(stream_);
    if (err != cudaSuccess) {
        throw std::runtime_error("cudaStreamSynchronize failed: " + std::string(cudaGetErrorString(err)));
    }
    std::memcpy(out_sig.data(), h_pinned_signature_, GRID_CELLS);
}

void CudaSpatialHasher::hash_frame_nv12(
    const uint8_t* d_y_plane,
    const uint8_t* d_uv_plane,
    int width,
    int height,
    int pitch_y,
    int pitch_uv,
    ColorGridSignature& out_color_sig,
    GridSignature* out_luma_sig
) {
    hash_frame_nv12_async(d_y_plane, d_uv_plane, width, height, pitch_y, pitch_uv);
    synchronize_color_signature(out_color_sig, out_luma_sig);
}

void CudaSpatialHasher::hash_frame(const uint8_t* d_y_plane, int width, int height, int pitch, GridSignature& out_sig) {
    hash_frame_async(d_y_plane, width, height, pitch);
    synchronize_signature(out_sig);
}

} // namespace Forensic
