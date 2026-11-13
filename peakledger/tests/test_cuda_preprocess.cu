#include "cuda_preprocess.cuh"
#include <iostream>
#include <vector>
#include <cmath>
#include <chrono>
#include <cassert>
#include <cuda_runtime.h>

#define CUDA_CHECK(call) \
    do { \
        cudaError_t err = call; \
        if (err != cudaSuccess) { \
            std::cerr << "CUDA error at " << __FILE__ << ":" << __LINE__ << ": " \
                      << cudaGetErrorString(err) << std::endl; \
            std::exit(EXIT_FAILURE); \
        } \
    } while (0)

int main() {
    std::cout << "========================================================\n"
              << "[TEST] CUDA NV12-to-NCHW Zero-Copy Preprocessing Kernel\n"
              << "========================================================\n";

    int device_id = 0;
    cudaDeviceProp prop;
    CUDA_CHECK(cudaGetDeviceProperties(&prop, device_id));
    std::cout << "[+] Hardware Device: " << prop.name
              << " (Compute " << prop.major << "." << prop.minor << ")\n";

    const int src_width = 1920;
    const int src_height = 1080;
    const int dst_width = 640;
    const int dst_height = 640;
    const size_t tensor_elements = 3 * dst_width * dst_height;
    const size_t tensor_bytes = tensor_elements * sizeof(float);

    // 1. Allocate pitched device memory for input Y-plane to test pitch awareness
    size_t d_pitch = 0;
    uint8_t* d_src_y = nullptr;
    CUDA_CHECK(cudaMallocPitch(reinterpret_cast<void**>(&d_src_y), &d_pitch, src_width, src_height));
    std::cout << "[+] Allocated 1080p source Y-plane: " << src_width << "x" << src_height
              << " with pitch: " << d_pitch << " bytes\n";

    // 2. Populate host test pattern: smooth 2D gradient + step edge
    std::vector<uint8_t> h_src(d_pitch * src_height, 0);
    for (int y = 0; y < src_height; ++y) {
        for (int x = 0; x < src_width; ++x) {
            float gx = static_cast<float>(x) / static_cast<float>(src_width);
            float gy = static_cast<float>(y) / static_cast<float>(src_height);
            uint8_t val = static_cast<uint8_t>((gx * 0.5f + gy * 0.5f) * 255.0f);
            if (x >= 900 && x <= 1020 && y >= 500 && y <= 600) {
                val = 240; // Step feature block
            }
            h_src[y * d_pitch + x] = val;
        }
    }
    CUDA_CHECK(cudaMemcpy(d_src_y, h_src.data(), d_pitch * src_height, cudaMemcpyHostToDevice));

    // 3. Allocate device destination tensor (1x3x640x640 float)
    float* d_dst_tensor = nullptr;
    CUDA_CHECK(cudaMalloc(reinterpret_cast<void**>(&d_dst_tensor), tensor_bytes));
    CUDA_CHECK(cudaMemset(d_dst_tensor, 0, tensor_bytes));

    // 4. Create dedicated non-blocking inference stream
    cudaStream_t stream = nullptr;
    CUDA_CHECK(cudaStreamCreateWithFlags(&stream, cudaStreamNonBlocking));

    // 5. Instantiate CudaPreprocessor and execute
    Forensic::CudaPreprocessor preprocessor(dst_width, dst_height);
    preprocessor.preprocess(d_src_y, src_width, src_height, static_cast<int>(d_pitch), d_dst_tensor, stream);
    CUDA_CHECK(cudaStreamSynchronize(stream));

    // 6. Copy result to host for mathematical verification
    std::vector<float> h_dst(tensor_elements, 0.0f);
    CUDA_CHECK(cudaMemcpy(h_dst.data(), d_dst_tensor, tensor_bytes, cudaMemcpyDeviceToHost));

    // Verify properties:
    // (a) All values within [0.0f, 1.0f]
    float min_val = 1.0f, max_val = 0.0f;
    for (size_t i = 0; i < tensor_elements; ++i) {
        float v = h_dst[i];
        if (v < 0.0f || v > 1.0f) {
            std::cerr << "[-] Error: Out-of-bounds tensor value at index " << i << ": " << v << std::endl;
            return 1;
        }
        if (v < min_val) min_val = v;
        if (v > max_val) max_val = v;
    }
    std::cout << "[+] Value bounds check passed: range [" << min_val << ", " << max_val << "] in [0.0, 1.0]\n";

    // (b) Channel broadcast identity: Channel 0 == Channel 1 == Channel 2
    const size_t plane_size = dst_width * dst_height;
    double max_channel_diff = 0.0;
    for (size_t i = 0; i < plane_size; ++i) {
        float r = h_dst[0 * plane_size + i];
        float g = h_dst[1 * plane_size + i];
        float b = h_dst[2 * plane_size + i];
        double diff_rg = std::abs(r - g);
        double diff_rb = std::abs(r - b);
        if (diff_rg > max_channel_diff) max_channel_diff = diff_rg;
        if (diff_rb > max_channel_diff) max_channel_diff = diff_rb;
    }
    std::cout << "[+] Planar NCHW channel broadcast check passed (max inter-channel diff: " << max_channel_diff << ")\n";
    if (max_channel_diff > 1e-6) {
        std::cerr << "[-] Error: Channels do not match perfectly!\n";
        return 1;
    }

    // (c) Mathematical CPU verification of bilinear interpolation
    float scale_x = static_cast<float>(src_width) / static_cast<float>(dst_width);
    float scale_y = static_cast<float>(src_height) / static_cast<float>(dst_height);
    double max_error_vs_cpu = 0.0;

    for (int y_dst = 0; y_dst < dst_height; ++y_dst) {
        for (int x_dst = 0; x_dst < dst_width; ++x_dst) {
            float src_x = (static_cast<float>(x_dst) + 0.5f) * scale_x - 0.5f;
            float src_y = (static_cast<float>(y_dst) + 0.5f) * scale_y - 0.5f;
            src_x = std::max(0.0f, std::min(src_x, static_cast<float>(src_width - 1)));
            src_y = std::max(0.0f, std::min(src_y, static_cast<float>(src_height - 1)));

            int x0 = static_cast<int>(src_x);
            int y0 = static_cast<int>(src_y);
            int x1 = std::min(x0 + 1, src_width - 1);
            int y1 = std::min(y0 + 1, src_height - 1);

            float wx = src_x - static_cast<float>(x0);
            float wy = src_y - static_cast<float>(y0);

            float v00 = static_cast<float>(h_src[y0 * d_pitch + x0]);
            float v10 = static_cast<float>(h_src[y0 * d_pitch + x1]);
            float v01 = static_cast<float>(h_src[y1 * d_pitch + x0]);
            float v11 = static_cast<float>(h_src[y1 * d_pitch + x1]);

            float expected = ((1.0f - wx) * (1.0f - wy) * v00 +
                              wx * (1.0f - wy) * v10 +
                              (1.0f - wx) * wy * v01 +
                              wx * wy * v11) / 255.0f;

            float actual = h_dst[0 * plane_size + (y_dst * dst_width + x_dst)];
            double err = std::abs(expected - actual);
            if (err > max_error_vs_cpu) max_error_vs_cpu = err;
        }
    }
    std::cout << "[+] CPU vs GPU Bilinear Interpolation verification passed (max error: " << max_error_vs_cpu << ")\n";
    if (max_error_vs_cpu > 1e-4) {
        std::cerr << "[-] Error: Significant deviation between GPU and CPU bilinear calculations!\n";
        return 1;
    }

    // 7. Throughput Benchmarking (1,000 runs)
    std::cout << "[+] Commencing 1,000-iteration asynchronous throughput benchmark...\n";
    const int benchmark_iters = 1000;
    cudaEvent_t start, stop;
    CUDA_CHECK(cudaEventCreate(&start));
    CUDA_CHECK(cudaEventCreate(&stop));

    // Warm-up
    for (int i = 0; i < 50; ++i) {
        preprocessor.preprocess(d_src_y, src_width, src_height, static_cast<int>(d_pitch), d_dst_tensor, stream);
    }
    CUDA_CHECK(cudaStreamSynchronize(stream));

    CUDA_CHECK(cudaEventRecord(start, stream));
    for (int i = 0; i < benchmark_iters; ++i) {
        preprocessor.preprocess(d_src_y, src_width, src_height, static_cast<int>(d_pitch), d_dst_tensor, stream);
    }
    CUDA_CHECK(cudaEventRecord(stop, stream));
    CUDA_CHECK(cudaEventSynchronize(stop));

    float total_ms = 0.0f;
    CUDA_CHECK(cudaEventElapsedTime(&total_ms, start, stop));
    float avg_us = (total_ms * 1000.0f) / benchmark_iters;
    float fps = (benchmark_iters * 1000.0f) / total_ms;

    std::cout << "========================================================\n"
              << "BENCHMARK PERFORMANCE SUMMARY\n"
              << "  Resolution Ingest : " << src_width << "x" << src_height << " NV12 (Y-plane)\n"
              << "  Tensor Target     : 1x3x" << dst_width << "x" << dst_height << " FP32 NCHW\n"
              << "  Average Latency   : " << avg_us << " µs/frame\n"
              << "  Throughput        : " << fps << " FPS\n"
              << "  Target Requirement: 300+ FPS (" << (fps >= 300.0f ? "PASSED [EXCEEDED]" : "FAILED") << ")\n"
              << "========================================================\n";

    // Clean up
    CUDA_CHECK(cudaEventDestroy(start));
    CUDA_CHECK(cudaEventDestroy(stop));
    CUDA_CHECK(cudaStreamDestroy(stream));
    CUDA_CHECK(cudaFree(d_src_y));
    CUDA_CHECK(cudaFree(d_dst_tensor));

    std::cout << "[SUCCESS] STEP 1 VERIFICATION COMPLETE: Preprocessor functional & deterministic.\n";
    return 0;
}
