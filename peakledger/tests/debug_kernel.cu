#include "cuda_spatial_hash.cuh"
#include <iostream>

int main() {
    uint8_t* d_y = nullptr;
    uint8_t* d_out = nullptr;
    cudaMalloc(&d_y, 1920 * 1080);
    cudaMemset(d_y, 100, 1920 * 1080);
    cudaMalloc(&d_out, 512);
    cudaMemset(d_out, 0, 512);

    Forensic::launch_integer_spatial_hash_kernel(d_y, 1920, 1080, 1920, d_out, nullptr);
    cudaError_t err = cudaDeviceSynchronize();
    std::cout << "Kernel sync error: " << cudaGetErrorString(err) << std::endl;

    uint8_t h_out[512];
    cudaMemcpy(h_out, d_out, 512, cudaMemcpyDeviceToHost);
    std::cout << "Cell 0: " << (int)h_out[0] << ", Cell 1: " << (int)h_out[1] << std::endl;
    return 0;
}
