#pragma once

#include "common.hpp"
#include <cuda_runtime.h>
#include <memory>
#include <string>

namespace Forensic {

class CudaSpatialHasher {
public:
    explicit CudaSpatialHasher(int device_id = 0);
    ~CudaSpatialHasher();

    CudaSpatialHasher(const CudaSpatialHasher&) = delete;
    CudaSpatialHasher& operator=(const CudaSpatialHasher&) = delete;

    // Asynchronously launches integer spatial hashing kernel on d_y_plane and initiates DMA to pinned host memory (legacy luma)
    void hash_frame_async(const uint8_t* d_y_plane, int width, int height, int pitch);

    // Asynchronously launches integer spatial hashing kernel on full NV12 (Y + UV)
    void hash_frame_nv12_async(
        const uint8_t* d_y_plane,
        const uint8_t* d_uv_plane,
        int width,
        int height,
        int pitch_y,
        int pitch_uv
    );

    // Waits for the stream to complete and copies the 512-byte luminance signature to host
    void synchronize_signature(GridSignature& out_sig);

    // Waits for stream to complete and copies the 1536-byte color signature to host (and optionally 512-byte luma)
    void synchronize_color_signature(ColorGridSignature& out_color_sig, GridSignature* out_luma_sig = nullptr);

    // Synchronous convenience API (legacy luma)
    void hash_frame(const uint8_t* d_y_plane, int width, int height, int pitch, GridSignature& out_sig);

    // Synchronous full-color NV12 spatial hashing API
    void hash_frame_nv12(
        const uint8_t* d_y_plane,
        const uint8_t* d_uv_plane,
        int width,
        int height,
        int pitch_y,
        int pitch_uv,
        ColorGridSignature& out_color_sig,
        GridSignature* out_luma_sig = nullptr
    );

    cudaStream_t get_stream() const { return stream_; }
    uint8_t* get_device_signature_ptr() const { return d_signature_; }
    uint8_t* get_pinned_host_signature_ptr() const { return h_pinned_signature_; }

private:
    int device_id_{0};
    cudaStream_t stream_{nullptr};
    uint8_t* d_signature_{nullptr};        // Sized to COLOR_GRID_BYTES (1536 bytes)
    uint8_t* h_pinned_signature_{nullptr}; // Sized to COLOR_GRID_BYTES (1536 bytes)
};

// Raw kernel launcher for external integration (e.g. within NVDEC pipeline)
void launch_integer_spatial_hash_kernel(
    const uint8_t* d_y_plane,
    const uint8_t* d_uv_plane,
    int width,
    int height,
    int pitch_y,
    int pitch_uv,
    uint8_t* d_out_color_sig,
    cudaStream_t stream
);

// Backward-compatible overload for luma-only
void launch_integer_spatial_hash_kernel(
    const uint8_t* d_y_plane,
    int width,
    int height,
    int pitch,
    uint8_t* d_out_signature,
    cudaStream_t stream
);

} // namespace Forensic
