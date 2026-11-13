#pragma once

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavcodec/bsf.h>
#include <libavformat/avformat.h>
#include <libavutil/hwcontext.h>
#include <libavutil/motion_vector.h>
#include <libavutil/pixdesc.h>
#include <libavutil/imgutils.h>
}

#include "common.hpp"
#include <string>
#include <vector>
#include <memory>

namespace Forensic {

class AnnexBNormalizer {
public:
    AnnexBNormalizer();
    ~AnnexBNormalizer();

    AnnexBNormalizer(const AnnexBNormalizer&) = delete;
    AnnexBNormalizer& operator=(const AnnexBNormalizer&) = delete;

    bool initialize(const AVCodecParameters* codecpar);
    bool normalize(const AVPacket* in_pkt, std::vector<AVPacket*>& out_packets);
    bool is_active() const { return is_active_; }

private:
    AVBSFContext* bsf_ctx_{nullptr};
    bool is_active_{false};
};

struct GpuDecodedFrame {
    int64_t pts{0};
    uint64_t frame_index{0};
    int width{0};
    int height{0};
    int pitch{0};
    const uint8_t* d_y_plane{nullptr};  // Device pointer to GPU VRAM luminance plane
    const uint8_t* d_uv_plane{nullptr}; // Device pointer to GPU VRAM UV plane
    bool is_hw_cuda{false};
    std::vector<AVMotionVector> motion_vectors;
    AVFrame* raw_frame{nullptr};        // Borrowed pointer to underlying AVFrame
};

class NVDecDecoder {
public:
    explicit NVDecDecoder(const std::string& filepath, int gpu_device_id = 0, bool keyframes_only = false);
    ~NVDecDecoder();

    NVDecDecoder(const NVDecDecoder&) = delete;
    NVDecDecoder& operator=(const NVDecDecoder&) = delete;

    // Packet-level demuxing for 100% Layer 1 ingestion (no frame skipping)
    bool read_next_packet(AVPacket* out_pkt, int64_t& out_pts, int64_t& out_dts, bool& out_is_key);

    // Feeds packet to decoder and attempts to drain a decoded frame
    bool decode_packet(const AVPacket* pkt, GpuDecodedFrame& out_frame);

    // Flushes remaining cached frames from decoder at EOF
    bool flush_decoder(GpuDecodedFrame& out_frame);

    // High-level combined frame decode (now processes 100% of packets)
    bool read_next_frame(GpuDecodedFrame& out_frame);

    int get_width() const { return width_; }
    int get_height() const { return height_; }
    int64_t get_duration_us() const { return duration_us_; }
    int64_t get_file_size() const { return file_size_; }
    double get_fps() const { return fps_; }
    const std::string& get_filepath() const { return filepath_; }
    bool is_keyframe_only() const { return keyframes_only_; }
    const AVCodecParameters* get_codecpar() const;
    AVRational get_time_base() const;
    int get_video_stream_idx() const { return video_stream_idx_; }

    // Transfers GPU frame to host memory for uncompressed evidence saving
    bool transfer_to_host(const GpuDecodedFrame& gpu_frame, AVFrame* sw_frame);

private:
    std::string filepath_;
    int gpu_device_id_{0};
    bool keyframes_only_{false};

    AVFormatContext* fmt_ctx_{nullptr};
    AVCodecContext* codec_ctx_{nullptr};
    AVBufferRef* hw_device_ctx_{nullptr};
    AVPacket* pkt_{nullptr};
    AVFrame* hw_frame_{nullptr};
    AVFrame* sw_transfer_frame_{nullptr};

    int video_stream_idx_{-1};
    int width_{0};
    int height_{0};
    int64_t duration_us_{0};
    int64_t file_size_{0};
    double fps_{30.0};
    uint64_t frame_counter_{0};
    uint64_t packet_counter_{0};

    static enum AVPixelFormat get_hw_format(AVCodecContext* ctx, const enum AVPixelFormat* pix_fmts);
    void open_input();
    void fill_gpu_frame(GpuDecodedFrame& out_frame);
};

} // namespace Forensic
