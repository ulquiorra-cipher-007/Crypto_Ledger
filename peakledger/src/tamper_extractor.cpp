#include "tamper_extractor.hpp"
#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <sys/stat.h>
#include <cmath>

namespace Forensic {

TamperExtractor::TamperExtractor(const std::string& evidence_dir)
    : evidence_dir_(evidence_dir) {
    mkdir(evidence_dir_.c_str(), 0777);
    sw_frame_ = av_frame_alloc();
    yuv420_frame_ = av_frame_alloc();
}

TamperExtractor::~TamperExtractor() {
    if (jpeg_ctx_) avcodec_free_context(&jpeg_ctx_);
    if (yuv420_frame_) av_frame_free(&yuv420_frame_);
    if (sw_frame_) av_frame_free(&sw_frame_);
}

void TamperExtractor::init_jpeg_encoder(int width, int height) {
    if (jpeg_ctx_ && jpeg_ctx_->width == width && jpeg_ctx_->height == height) {
        return;
    }

    if (jpeg_ctx_) {
        avcodec_free_context(&jpeg_ctx_);
    }

    jpeg_codec_ = avcodec_find_encoder(AV_CODEC_ID_MJPEG);
    if (!jpeg_codec_) {
        throw std::runtime_error("MJPEG encoder not available in FFmpeg build");
    }

    jpeg_ctx_ = avcodec_alloc_context3(jpeg_codec_);
    jpeg_ctx_->pix_fmt = AV_PIX_FMT_YUVJ420P;
    jpeg_ctx_->width = width;
    jpeg_ctx_->height = height;
    jpeg_ctx_->time_base = {1, 30};

    if (avcodec_open2(jpeg_ctx_, jpeg_codec_, nullptr) < 0) {
        throw std::runtime_error("Failed to open MJPEG encoder context");
    }

    if (yuv420_frame_->data[0]) {
        av_frame_unref(yuv420_frame_);
    }
    yuv420_frame_->format = AV_PIX_FMT_YUVJ420P;
    yuv420_frame_->width = width;
    yuv420_frame_->height = height;
    if (av_frame_get_buffer(yuv420_frame_, 32) < 0) {
        throw std::runtime_error("Failed to allocate buffer for YUV420 frame");
    }
}

bool TamperExtractor::encode_frame_to_jpeg(const AVFrame* frame, const std::string& out_path) {
    AVPacket* pkt = av_packet_alloc();
    if (!pkt) return false;

    int ret = avcodec_send_frame(jpeg_ctx_, frame);
    if (ret >= 0) {
        ret = avcodec_receive_packet(jpeg_ctx_, pkt);
        if (ret >= 0) {
            std::ofstream out(out_path, std::ios::binary);
            if (out.is_open()) {
                out.write(reinterpret_cast<const char*>(pkt->data), pkt->size);
                out.close();
            } else {
                ret = -1;
            }
        }
    }

    av_packet_free(&pkt);
    return (ret >= 0);
}

uint32_t TamperExtractor::compute_motion_residual(
    const GpuDecodedFrame& frame,
    std::vector<uint32_t>& out_cell_residuals
) {
    out_cell_residuals.assign(GRID_CELLS, 0);
    if (frame.motion_vectors.empty() || frame.width == 0 || frame.height == 0) {
        return 0;
    }

    uint64_t total_energy = 0;

    for (const auto& mv : frame.motion_vectors) {
        // Compute displacement magnitude |dx| + |dy|
        int32_t dx = std::abs(mv.dst_x - mv.src_x);
        int32_t dy = std::abs(mv.dst_y - mv.src_y);
        uint32_t mag = static_cast<uint32_t>(dx + dy);
        total_energy += mag;

        // Map dst coordinate to 32x16 macro grid cell
        int cx = (mv.dst_x * static_cast<int>(GRID_COLS)) / frame.width;
        int cy = (mv.dst_y * static_cast<int>(GRID_ROWS)) / frame.height;

        if (cx >= 0 && cx < static_cast<int>(GRID_COLS) &&
            cy >= 0 && cy < static_cast<int>(GRID_ROWS)) {
            size_t cell_idx = cy * GRID_COLS + cx;
            out_cell_residuals[cell_idx] += mag;
        }
    }

    return static_cast<uint32_t>(total_energy > UINT32_MAX ? UINT32_MAX : total_energy);
}

std::string TamperExtractor::dump_evidence_frame(
    NVDecDecoder& decoder,
    const GpuDecodedFrame& gpu_frame,
    int64_t pts
) {
    if (!decoder.transfer_to_host(gpu_frame, sw_frame_)) {
        std::cerr << "[TamperExtractor] Failed to transfer frame to host" << std::endl;
        return "";
    }

    int width = sw_frame_->width;
    int height = sw_frame_->height;
    init_jpeg_encoder(width, height);

    // Convert NV12 to YUV420P
    // Copy Y plane
    for (int r = 0; r < height; ++r) {
        std::memcpy(
            yuv420_frame_->data[0] + r * yuv420_frame_->linesize[0],
            sw_frame_->data[0] + r * sw_frame_->linesize[0],
            width
        );
    }

    // Deinterleave NV12 UV plane into YUV420P U and V planes
    for (int r = 0; r < height / 2; ++r) {
        const uint8_t* nv12_uv = sw_frame_->data[1] + r * sw_frame_->linesize[1];
        uint8_t* u_plane = yuv420_frame_->data[1] + r * yuv420_frame_->linesize[1];
        uint8_t* v_plane = yuv420_frame_->data[2] + r * yuv420_frame_->linesize[2];

        for (int c = 0; c < width / 2; ++c) {
            u_plane[c] = nv12_uv[c * 2];
            v_plane[c] = nv12_uv[c * 2 + 1];
        }
    }

    std::ostringstream ss;
    ss << evidence_dir_ << "/tamper_frame_" << pts << ".jpg";
    std::string out_path = ss.str();

    if (encode_frame_to_jpeg(yuv420_frame_, out_path)) {
        return out_path;
    }

    return "";
}

void TamperExtractor::emit_tamper_signal(
    int64_t pts,
    const std::string& image_filepath,
    uint32_t residual_energy
) {
    // Format required by specification: TAMPERING_DETECTED|PTS:<pts>|IMAGE:<filepath>
    std::cerr << "TAMPERING_DETECTED|PTS:" << pts 
              << "|IMAGE:" << image_filepath 
              << "|RESIDUAL:" << residual_energy 
              << std::endl;
}

} // namespace Forensic
