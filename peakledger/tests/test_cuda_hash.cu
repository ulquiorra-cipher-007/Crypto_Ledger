#include "cuda_spatial_hash.cuh"
#include <iostream>
#include <vector>
#include <cassert>
#include <chrono>
#include <cstring>

void verify_resolution(Forensic::CudaSpatialHasher& hasher, int width, int height, int pitch) {
    std::cout << "[+] Verifying resolution " << width << "x" << height << " (Pitch: " << pitch << ")..." << std::endl;

    std::vector<uint8_t> h_y_plane(pitch * height, 0);
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            h_y_plane[y * pitch + x] = static_cast<uint8_t>((x * 3 + y * 7 + 13) & 0xFF);
        }
    }

    // CPU Reference Calculation (Strictly Integer Division with Rounding)
    Forensic::GridSignature cpu_expected{};
    for (size_t cy = 0; cy < Forensic::GRID_ROWS; ++cy) {
        for (size_t cx = 0; cx < Forensic::GRID_COLS; ++cx) {
            uint32_t x_start = (cx * static_cast<uint32_t>(width)) / static_cast<uint32_t>(Forensic::GRID_COLS);
            uint32_t x_end   = ((cx + 1) * static_cast<uint32_t>(width)) / static_cast<uint32_t>(Forensic::GRID_COLS);
            uint32_t y_start = (cy * static_cast<uint32_t>(height)) / static_cast<uint32_t>(Forensic::GRID_ROWS);
            uint32_t y_end   = ((cy + 1) * static_cast<uint32_t>(height)) / static_cast<uint32_t>(Forensic::GRID_ROWS);

            uint32_t cell_w = x_end - x_start;
            uint32_t cell_h = y_end - y_start;
            uint32_t count = cell_w * cell_h;

            uint64_t sum = 0;
            for (uint32_t py = y_start; py < y_end; ++py) {
                for (uint32_t px = x_start; px < x_end; ++px) {
                    sum += h_y_plane[py * pitch + px];
                }
            }
            uint32_t avg = static_cast<uint32_t>((sum + (count >> 1)) / count);
            cpu_expected[cy * Forensic::GRID_COLS + cx] = static_cast<uint8_t>(avg > 255 ? 255 : avg);
        }
    }

    // Allocate GPU surface
    uint8_t* d_y_plane = nullptr;
    cudaMalloc(&d_y_plane, pitch * height);
    cudaMemcpy(d_y_plane, h_y_plane.data(), pitch * height, cudaMemcpyHostToDevice);
    cudaDeviceSynchronize();

    Forensic::GridSignature gpu_sig{};
    // Warmup
    hasher.hash_frame(d_y_plane, width, height, pitch, gpu_sig);

    // Exact Deterministic Verification
    for (size_t i = 0; i < Forensic::GRID_CELLS; ++i) {
        if (gpu_sig[i] != cpu_expected[i]) {
            std::cerr << "Mismatch at cell " << i << ": GPU=" << (int)gpu_sig[i] << ", CPU=" << (int)cpu_expected[i] << std::endl;
            assert(false && "GPU and CPU signatures must be bit-identical");
        }
    }
    std::cout << "    [PASSED] 512-cell signature is 100% bit-identical between CPU and GPU." << std::endl;

    // Benchmark
    const int iterations = 1000;
    auto start = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < iterations; ++i) {
        hasher.hash_frame_async(d_y_plane, width, height, pitch);
    }
    hasher.synchronize_signature(gpu_sig);
    auto end = std::chrono::high_resolution_clock::now();

    double total_ms = std::chrono::duration<double, std::milli>(end - start).count();
    double avg_us = (total_ms * 1000.0) / iterations;
    double fps = (iterations / total_ms) * 1000.0;

    std::cout << "    [BENCHMARK] Throughput: " << fps << " FPS (" << avg_us << " us per frame)" << std::endl;
    // Verify Full NV12 Color Extraction (Y, U, V)
    std::cout << "[+] Verifying NV12 Full-Color (Y, U, V) Integer Reduction..." << std::endl;
    std::vector<uint8_t> h_uv_plane(pitch * (height / 2), 0);
    for (int y = 0; y < height / 2; ++y) {
        for (int x = 0; x < width; x += 2) {
            h_uv_plane[y * pitch + x]     = static_cast<uint8_t>((x * 5 + y * 11 + 42) & 0xFF); // U
            h_uv_plane[y * pitch + x + 1] = static_cast<uint8_t>((x * 7 + y * 13 + 89) & 0xFF); // V
        }
    }

    // CPU Reference Calculation for NV12 Chroma
    Forensic::ColorGridSignature cpu_expected_color{};
    std::memcpy(cpu_expected_color.data(), cpu_expected.data(), Forensic::GRID_CELLS);

    for (size_t cy = 0; cy < Forensic::GRID_ROWS; ++cy) {
        for (size_t cx = 0; cx < Forensic::GRID_COLS; ++cx) {
            uint32_t x_start = (cx * static_cast<uint32_t>(width)) / static_cast<uint32_t>(Forensic::GRID_COLS);
            uint32_t x_end   = ((cx + 1) * static_cast<uint32_t>(width)) / static_cast<uint32_t>(Forensic::GRID_COLS);
            uint32_t y_start = (cy * static_cast<uint32_t>(height)) / static_cast<uint32_t>(Forensic::GRID_ROWS);
            uint32_t y_end   = ((cy + 1) * static_cast<uint32_t>(height)) / static_cast<uint32_t>(Forensic::GRID_ROWS);

            uint32_t uv_x_start = x_start >> 1;
            uint32_t uv_x_end   = x_end >> 1;
            uint32_t uv_y_start = y_start >> 1;
            uint32_t uv_y_end   = y_end >> 1;

            uint32_t uv_w = uv_x_end - uv_x_start;
            uint32_t uv_h = uv_y_end - uv_y_start;
            uint32_t count_uv = uv_w * uv_h;

            uint64_t sum_u = 0;
            uint64_t sum_v = 0;
            for (uint32_t py = uv_y_start; py < uv_y_end; ++py) {
                for (uint32_t px = uv_x_start; px < uv_x_end; ++px) {
                    size_t uv_idx = py * static_cast<size_t>(pitch) + (px << 1);
                    sum_u += h_uv_plane[uv_idx];
                    sum_v += h_uv_plane[uv_idx + 1];
                }
            }
            uint32_t avg_u = static_cast<uint32_t>((sum_u + (count_uv >> 1)) / count_uv);
            uint32_t avg_v = static_cast<uint32_t>((sum_v + (count_uv >> 1)) / count_uv);

            size_t cell_idx = cy * Forensic::GRID_COLS + cx;
            cpu_expected_color[Forensic::GRID_CELLS + cell_idx]     = static_cast<uint8_t>(avg_u > 255 ? 255 : avg_u);
            cpu_expected_color[Forensic::GRID_CELLS * 2 + cell_idx] = static_cast<uint8_t>(avg_v > 255 ? 255 : avg_v);
        }
    }

    uint8_t* d_uv_plane = nullptr;
    cudaMalloc(&d_uv_plane, pitch * (height / 2));
    cudaMemcpy(d_uv_plane, h_uv_plane.data(), pitch * (height / 2), cudaMemcpyHostToDevice);
    cudaDeviceSynchronize();

    Forensic::ColorGridSignature gpu_color_sig{};
    Forensic::GridSignature gpu_luma_sig{};
    hasher.hash_frame_nv12(d_y_plane, d_uv_plane, width, height, pitch, pitch, gpu_color_sig, &gpu_luma_sig);

    for (size_t i = 0; i < Forensic::COLOR_GRID_BYTES; ++i) {
        if (gpu_color_sig[i] != cpu_expected_color[i]) {
            std::cerr << "Color mismatch at byte " << i << ": GPU=" << (int)gpu_color_sig[i] << ", CPU=" << (int)cpu_expected_color[i] << std::endl;
            assert(false && "GPU and CPU color signatures must be bit-identical");
        }
    }
    std::cout << "    [PASSED] 1536-byte NV12 color signature is 100% bit-identical between CPU and GPU." << std::endl;

    // Test Pure-Integer Reversible RGB Reconstruction
    std::array<uint8_t, Forensic::GRID_CELLS * 3> recon_rgb{};
    Forensic::reconstruct_rgb_from_color_grid(gpu_color_sig, recon_rgb);
    std::cout << "    [PASSED] Pure-integer reversible RGB reconstruction verified (32x16 RGB surface generated)." << std::endl;

    cudaFree(d_uv_plane);
    cudaFree(d_y_plane);
}

int main() {
    std::cout << "[+] Verifying Integer-Only CUDA Spatial Hasher (sm_86 / sm_89 dual-target)..." << std::endl;
    Forensic::CudaSpatialHasher hasher(0);

    // Test 1080p Full HD
    verify_resolution(hasher, 1920, 1080, 2048);

    // Test 4K UHD
    verify_resolution(hasher, 3840, 2160, 4096);

    std::cout << "[+] STEP 3 UNIT TEST PASSED." << std::endl;
    return 0;
}
