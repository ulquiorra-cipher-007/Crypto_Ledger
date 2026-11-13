#include "trt_inference.hpp"
#include "cuda_preprocess.cuh"
#include <iostream>
#include <vector>
#include <cmath>
#include <chrono>
#include <cassert>

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
              << "[TEST] TensorRT 10/11 Execution Wrapper (enqueueV3)\n"
              << "========================================================\n";

    int device_id = 0;
    cudaDeviceProp prop;
    CUDA_CHECK(cudaGetDeviceProperties(&prop, device_id));
    std::cout << "[+] Hardware Device: " << prop.name
              << " (Compute " << prop.major << "." << prop.minor << ")\n";

    // 1. Create dedicated inference stream
    cudaStream_t stream = nullptr;
    CUDA_CHECK(cudaStreamCreateWithFlags(&stream, cudaStreamNonBlocking));

    // 2. Instantiate and initialize TrtInferenceEngine
    Forensic::TrtInferenceEngine engine("models/model.engine", stream);
    if (!engine.initialize(stream)) {
        std::cerr << "[-] Error: Failed to initialize TensorRT engine." << std::endl;
        return 1;
    }
    std::cout << "[+] TensorRT Engine successfully loaded: " << engine.engine_path() << "\n"
              << "    Input Tensor : " << engine.input_tensor_name() << "\n"
              << "    Output Tensor: " << engine.output_tensor_name() << "\n";

    assert(engine.input_tensor_name() == "images");
    assert(engine.output_tensor_name() == "output0");

    // 3. Prepare test 1080p source image
    const int src_width = 1920;
    const int src_height = 1080;
    size_t pitch = 0;

    uint8_t* d_src_y = nullptr;
    CUDA_CHECK(cudaMallocPitch(reinterpret_cast<void**>(&d_src_y), &pitch, src_width, src_height));
    std::vector<uint8_t> h_src(pitch * src_height, 128);
    CUDA_CHECK(cudaMemcpy(d_src_y, h_src.data(), pitch * src_height, cudaMemcpyHostToDevice));

    // 4. Verify double-buffering ping-pong
    Forensic::CudaPreprocessor preprocessor(640, 640);
    size_t slot0 = engine.active_slot_index();
    float* out1 = engine.infer_nv12(preprocessor, d_src_y, src_width, src_height, static_cast<int>(pitch), stream);
    size_t slot1 = engine.active_slot_index();
    float* out2 = engine.infer_nv12(preprocessor, d_src_y, src_width, src_height, static_cast<int>(pitch), stream);
    size_t slot2 = engine.active_slot_index();

    engine.synchronize(stream);

    std::cout << "[+] Double-buffering ping-pong verified: Slot " << slot0
              << " -> Slot " << slot1 << " -> Slot " << slot2 << "\n";
    assert(slot0 != slot1);
    assert(slot0 == slot2);
    assert(out1 != out2); // Different physical buffer addresses in VRAM

    // 5. Verify output tensor contents (no NaNs or Infs)
    std::vector<float> h_output(Forensic::TRT_OUTPUT_ELEMENTS);
    CUDA_CHECK(cudaMemcpy(h_output.data(), out1, Forensic::TRT_OUTPUT_BYTES, cudaMemcpyDeviceToHost));

    size_t nan_count = 0;
    size_t inf_count = 0;
    float min_val = 1e9f, max_val = -1e9f;
    for (size_t i = 0; i < Forensic::TRT_OUTPUT_ELEMENTS; ++i) {
        float v = h_output[i];
        if (std::isnan(v)) nan_count++;
        if (std::isinf(v)) inf_count++;
        if (v < min_val) min_val = v;
        if (v > max_val) max_val = v;
    }

    std::cout << "[+] Output verification: " << Forensic::TRT_OUTPUT_ELEMENTS << " elements (84x8400)\n"
              << "    Range: [" << min_val << ", " << max_val << "]\n"
              << "    NaNs: " << nan_count << " | Infs: " << inf_count << "\n";
    assert(nan_count == 0);
    assert(inf_count == 0);

    // 6. Benchmark sustained throughput (500 iterations)
    std::cout << "[+] Commencing 500-iteration double-buffered inference benchmark...\n";
    const int benchmark_iters = 500;
    cudaEvent_t start, stop;
    CUDA_CHECK(cudaEventCreate(&start));
    CUDA_CHECK(cudaEventCreate(&stop));

    // Warm-up
    for (int i = 0; i < 20; ++i) {
        engine.infer_nv12(preprocessor, d_src_y, src_width, src_height, static_cast<int>(pitch), stream);
    }
    engine.synchronize(stream);

    CUDA_CHECK(cudaEventRecord(start, stream));
    for (int i = 0; i < benchmark_iters; ++i) {
        engine.infer_nv12(preprocessor, d_src_y, src_width, src_height, static_cast<int>(pitch), stream);
    }
    CUDA_CHECK(cudaEventRecord(stop, stream));
    CUDA_CHECK(cudaEventSynchronize(stop));

    float total_ms = 0.0f;
    CUDA_CHECK(cudaEventElapsedTime(&total_ms, start, stop));
    float avg_latency_ms = total_ms / benchmark_iters;
    float sustained_fps = (benchmark_iters * 1000.0f) / total_ms;

    std::cout << "========================================================\n"
              << "TENSORRT EXECUTION PERFORMANCE SUMMARY\n"
              << "  Model Engine       : " << engine.engine_path() << "\n"
              << "  Execution API      : IExecutionContext::enqueueV3 (Double-Buffered)\n"
              << "  Average Latency    : " << avg_latency_ms << " ms/frame\n"
              << "  Sustained Throughput: " << sustained_fps << " FPS\n"
              << "  Target Requirement : 300+ FPS (" << (sustained_fps >= 300.0f ? "PASSED [EXCEEDED]" : "FAILED") << ")\n"
              << "========================================================\n";

    // 7. Verify CLI conversion snippet
    std::string trtexec_cmd = Forensic::TrtInferenceEngine::get_trtexec_cli_command();
    std::cout << "[+] Automated CLI conversion snippet:\n"
              << "    " << trtexec_cmd << "\n";
    assert(trtexec_cmd == "./bin/trtexec --onnx=yolo11n.onnx --saveEngine=models/yolo11n_fp16.engine --fp16");

    // Clean up
    CUDA_CHECK(cudaEventDestroy(start));
    CUDA_CHECK(cudaEventDestroy(stop));
    CUDA_CHECK(cudaStreamDestroy(stream));
    CUDA_CHECK(cudaFree(d_src_y));

    std::cout << "[SUCCESS] STEP 2 VERIFICATION COMPLETE: TensorRT wrapper functional & verified.\n";
    return 0;
}
