#include "cuda_spatial_hash.cuh"
#include <iostream>

int main() {
    Forensic::CudaSpatialHasher hasher(0);
    uint8_t* d_y = nullptr;
    cudaMalloc(&d_y, 1920 * 1080);
    cudaMemset(d_y, 100, 1920 * 1080);

    Forensic::GridSignature sig{};
    hasher.hash_frame(d_y, 1920, 1080, 1920, sig);
    std::cout << "Sig cell 0: " << (int)sig[0] << std::endl;
    return 0;
}
