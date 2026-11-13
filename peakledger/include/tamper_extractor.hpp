#pragma once

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavutil/motion_vector.h>
}

#include "common.hpp"
#include "nvdec_decoder.hpp"
#include "ring_buffer.hpp"
#include <string>
#include <vector>
#include <memory>

namespace Forensic {

struct TamperEvidence {
    int64_t pts{0};
    uint64_t frame_index{0};
    HashDigest expected_hash{};
    HashDigest observed_hash{};
    uint32_t residual_energy{0};
    std::string image_filepath;
    std::vector<uint32_t> cell_residuals; // 512-cell residual energy map
};

class TamperExtractor {
public:
    explicit TamperExtractor(const std::string& evidence_dir = "evidence");
    ~TamperExtractor();

    // Computes spatial residual energy from motion vectors
    uint32_t compute_motion_residual(
        const GpuDecodedFrame& frame,
        std::vector<uint32_t>& out_cell_residuals
    );

    // Dumps full-color frame as real, standard-compliant JPEG image
    std::string dump_evidence_frame(
        NVDecDecoder& decoder,
        const GpuDecodedFrame& gpu_frame,
        int64_t pts
    );

    // Formats and emits real-time signal to stderr
    void emit_tamper_signal(
        int64_t pts,
        const std::string& image_filepath,
        uint32_t residual_energy
    );

private:
    std::string evidence_dir_;
    AVFrame* sw_frame_{nullptr};
    AVFrame* yuv420_frame_{nullptr};
    AVCodecContext* jpeg_ctx_{nullptr};
    const AVCodec* jpeg_codec_{nullptr};

    void init_jpeg_encoder(int width, int height);
    bool encode_frame_to_jpeg(const AVFrame* frame, const std::string& out_path);
};

} // namespace Forensic
