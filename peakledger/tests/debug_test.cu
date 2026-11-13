#include "cuda_spatial_hash.cuh"
#include <iostream>
#include <vector>

int main() {
    const int width = 1920;
    const int height = 1080;
    const int pitch = 2048;

    std::vector<uint8_t> h_y_plane(pitch * height, 0);
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            h_y_plane[y * pitch + x] = static_cast<uint8_t>((x * 3 + y * 7 + 13) & 0xFF);
        }
    }

    uint8_t* d_y_plane = nullptr;
    cudaMalloc(&d_y_plane, pitch * height);
    cudaMemcpy(d_y_plane, h_y_plane.data(), pitch * height, cudaMemcpyHostToDevice);

    Forensic::CudaSpatialHasher hasher(0);
    Forensic::GridSignature gpu_sig{};
    hasher.hash_frame(d_y_plane, width, height, pitch, gpu_sig);

    std::cout << "GPU sig[0]: " << (int)gpu_sig[0] << std::endl;
    std::cout << "GPU sig[1]: " << (int)gpu_sig[1] << std::endl;
    return 0;
}
