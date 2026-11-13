#include "nvdec_decoder.hpp"
#include <iostream>
#include <stdexcept>
#include <sys/stat.h>

namespace Forensic {

// ============================================================================
// AnnexBNormalizer Implementation
// ============================================================================

AnnexBNormalizer::AnnexBNormalizer() = default;

AnnexBNormalizer::~AnnexBNormalizer() {
    if (bsf_ctx_) {
        av_bsf_free(&bsf_ctx_);
        bsf_ctx_ = nullptr;
    }
}

bool AnnexBNormalizer::initialize(const AVCodecParameters* codecpar) {
    if (!codecpar) return false;

    const char* filter_name = nullptr;
    if (codecpar->codec_id == AV_CODEC_ID_H264) {
        filter_name = "h264_mp4toannexb";
    } else if (codecpar->codec_id == AV_CODEC_ID_HEVC) {
        filter_name = "hevc_mp4toannexb";
    }

    if (!filter_name) {
        is_active_ = false;
        return true;
    }

    const AVBitStreamFilter* bsf = av_bsf_get_by_name(filter_name);
    if (!bsf) {
        std::cerr << "[AnnexBNormalizer] Warning: BSF filter '" << filter_name << "' not found. Passthrough." << std::endl;
        is_active_ = false;
        return true;
    }

    if (av_bsf_alloc(bsf, &bsf_ctx_) < 0) {
        std::cerr << "[AnnexBNormalizer] Failed to allocate BSF context" << std::endl;
        return false;
    }

    if (avcodec_parameters_copy(bsf_ctx_->par_in, codecpar) < 0) {
        av_bsf_free(&bsf_ctx_);
        bsf_ctx_ = nullptr;
        return false;
    }

    if (av_bsf_init(bsf_ctx_) < 0) {
        std::cerr << "[AnnexBNormalizer] Failed to initialize BSF context" << std::endl;
        av_bsf_free(&bsf_ctx_);
        bsf_ctx_ = nullptr;
        return false;
    }

    is_active_ = true;
    return true;
}

bool AnnexBNormalizer::normalize(const AVPacket* in_pkt, std::vector<AVPacket*>& out_packets) {
    if (!is_active_ || !bsf_ctx_) {
        AVPacket* copy = av_packet_alloc();
        if (copy) {
            av_packet_ref(copy, in_pkt);
            out_packets.push_back(copy);
        }
        return !out_packets.empty();
    }

    AVPacket* temp = av_packet_alloc();
    if (!temp) return false;
    av_packet_ref(temp, in_pkt);

    int ret = av_bsf_send_packet(bsf_ctx_, temp);
    av_packet_free(&temp);
    if (ret < 0) {
        return false;
    }

    while (true) {
        AVPacket* filtered = av_packet_alloc();
        ret = av_bsf_receive_packet(bsf_ctx_, filtered);
        if (ret == 0) {
            out_packets.push_back(filtered);
        } else {
            av_packet_free(&filtered);
            break;
        }
    }
    return !out_packets.empty();
}

enum AVPixelFormat NVDecDecoder::get_hw_format(AVCodecContext* /*ctx*/, const enum AVPixelFormat* pix_fmts) {
    for (const enum AVPixelFormat* p = pix_fmts; *p != AV_PIX_FMT_NONE; ++p) {
        if (*p == AV_PIX_FMT_CUDA) {
            return *p;
        }
    }
    std::cerr << "[NVDecDecoder] CUDA hardware format not offered, falling back to software." << std::endl;
    return AV_PIX_FMT_NONE;
}

NVDecDecoder::NVDecDecoder(const std::string& filepath, int gpu_device_id, bool keyframes_only)
    : filepath_(filepath), gpu_device_id_(gpu_device_id), keyframes_only_(keyframes_only) {
    
    struct stat st;
    if (stat(filepath_.c_str(), &st) == 0) {
        file_size_ = st.st_size;
    }

    open_input();
}

NVDecDecoder::~NVDecDecoder() {
    if (sw_transfer_frame_) av_frame_free(&sw_transfer_frame_);
    if (hw_frame_) av_frame_free(&hw_frame_);
    if (pkt_) av_packet_free(&pkt_);
    if (codec_ctx_) avcodec_free_context(&codec_ctx_);
    if (hw_device_ctx_) av_buffer_unref(&hw_device_ctx_);
    if (fmt_ctx_) avformat_close_input(&fmt_ctx_);
}

void NVDecDecoder::open_input() {
    if (avformat_open_input(&fmt_ctx_, filepath_.c_str(), nullptr, nullptr) < 0) {
        throw std::runtime_error("Failed to open video file: " + filepath_);
    }

    if (avformat_find_stream_info(fmt_ctx_, nullptr) < 0) {
        throw std::runtime_error("Failed to find stream information for: " + filepath_);
    }

    video_stream_idx_ = av_find_best_stream(fmt_ctx_, AVMEDIA_TYPE_VIDEO, -1, -1, nullptr, 0);
    if (video_stream_idx_ < 0) {
        throw std::runtime_error("No video stream found in: " + filepath_);
    }

    AVStream* st = fmt_ctx_->streams[video_stream_idx_];
    const AVCodec* decoder = avcodec_find_decoder(st->codecpar->codec_id);
    if (!decoder) {
        throw std::runtime_error("Unsupported video codec in: " + filepath_);
    }

    codec_ctx_ = avcodec_alloc_context3(decoder);
    if (!codec_ctx_) {
        throw std::runtime_error("Failed to allocate AVCodecContext");
    }

    if (avcodec_parameters_to_context(codec_ctx_, st->codecpar) < 0) {
        throw std::runtime_error("Failed to copy codec parameters to context");
    }

    // Initialize CUDA Hardware Acceleration
    std::string dev_str = std::to_string(gpu_device_id_);
    if (av_hwdevice_ctx_create(&hw_device_ctx_, AV_HWDEVICE_TYPE_CUDA, dev_str.c_str(), nullptr, 0) < 0) {
        std::cerr << "[NVDecDecoder] Warning: Could not create CUDA hwdevice on device " << dev_str << std::endl;
    } else {
        codec_ctx_->hw_device_ctx = av_buffer_ref(hw_device_ctx_);
        codec_ctx_->get_format = get_hw_format;
    }

    // Enable hardware motion vector export side data
    AVDictionary* opts = nullptr;
    av_dict_set(&opts, "flags2", "+export_mvs", 0);

    // Note: 100% of all packets are processed (no AVDISCARD_NONKEY) to guarantee Layer 1 integrity
    if (avcodec_open2(codec_ctx_, decoder, &opts) < 0) {
        av_dict_free(&opts);
        throw std::runtime_error("Failed to open video codec: " + std::string(decoder->name));
    }
    av_dict_free(&opts);

    width_ = codec_ctx_->width;
    height_ = codec_ctx_->height;
    if (st->duration > 0 && st->time_base.den > 0) {
        duration_us_ = av_rescale_q(st->duration, st->time_base, {1, 1000000});
    } else if (fmt_ctx_->duration > 0) {
        duration_us_ = fmt_ctx_->duration;
    }

    if (st->avg_frame_rate.den > 0 && st->avg_frame_rate.num > 0) {
        fps_ = av_q2d(st->avg_frame_rate);
    }

    pkt_ = av_packet_alloc();
    hw_frame_ = av_frame_alloc();
    sw_transfer_frame_ = av_frame_alloc();
}

const AVCodecParameters* NVDecDecoder::get_codecpar() const {
    if (!fmt_ctx_ || video_stream_idx_ < 0) return nullptr;
    return fmt_ctx_->streams[video_stream_idx_]->codecpar;
}

AVRational NVDecDecoder::get_time_base() const {
    if (!fmt_ctx_ || video_stream_idx_ < 0) return AVRational{1, 1000000};
    return fmt_ctx_->streams[video_stream_idx_]->time_base;
}

bool NVDecDecoder::read_next_packet(AVPacket* out_pkt, int64_t& out_pts, int64_t& out_dts, bool& out_is_key) {
    while (av_read_frame(fmt_ctx_, pkt_) >= 0) {
        if (pkt_->stream_index == video_stream_idx_) {
            AVRational stream_tb = fmt_ctx_->streams[video_stream_idx_]->time_base;

            int64_t raw_pts = (pkt_->pts != AV_NOPTS_VALUE) ? pkt_->pts : static_cast<int64_t>(packet_counter_);
            int64_t raw_dts = (pkt_->dts != AV_NOPTS_VALUE) ? pkt_->dts : raw_pts;

            out_pts = (stream_tb.den > 0 && stream_tb.num > 0)
                ? av_rescale_q(raw_pts, stream_tb, {1, 1000000})
                : raw_pts;
            out_dts = (stream_tb.den > 0 && stream_tb.num > 0)
                ? av_rescale_q(raw_dts, stream_tb, {1, 1000000})
                : raw_dts;
            out_is_key = (pkt_->flags & AV_PKT_FLAG_KEY) != 0;

            av_packet_move_ref(out_pkt, pkt_);
            packet_counter_++;
            return true;
        }
        av_packet_unref(pkt_);
    }
    return false;
}

void NVDecDecoder::fill_gpu_frame(GpuDecodedFrame& out_frame) {
    int64_t raw_pts = (hw_frame_->best_effort_timestamp != AV_NOPTS_VALUE)
        ? hw_frame_->best_effort_timestamp
        : ((hw_frame_->pts != AV_NOPTS_VALUE) ? hw_frame_->pts : static_cast<int64_t>(frame_counter_));
    AVRational stream_tb = fmt_ctx_->streams[video_stream_idx_]->time_base;
    out_frame.pts = (stream_tb.den > 0 && stream_tb.num > 0)
        ? av_rescale_q(raw_pts, stream_tb, {1, 1000000})
        : raw_pts;
    out_frame.frame_index = frame_counter_++;
    out_frame.width = hw_frame_->width;
    out_frame.height = hw_frame_->height;
    out_frame.pitch = hw_frame_->linesize[0];
    out_frame.raw_frame = hw_frame_;

    if (hw_frame_->format == AV_PIX_FMT_CUDA) {
        out_frame.d_y_plane = hw_frame_->data[0];
        out_frame.d_uv_plane = hw_frame_->data[1];
        out_frame.is_hw_cuda = true;
    } else {
        out_frame.d_y_plane = hw_frame_->data[0];
        out_frame.d_uv_plane = hw_frame_->data[1];
        out_frame.is_hw_cuda = false;
    }

    out_frame.motion_vectors.clear();
    AVFrameSideData* sd = av_frame_get_side_data(hw_frame_, AV_FRAME_DATA_MOTION_VECTORS);
    if (sd && sd->size > 0) {
        size_t num_mvs = sd->size / sizeof(AVMotionVector);
        const AVMotionVector* mvs = reinterpret_cast<const AVMotionVector*>(sd->data);
        out_frame.motion_vectors.assign(mvs, mvs + num_mvs);
    }
}

bool NVDecDecoder::decode_packet(const AVPacket* in_pkt, GpuDecodedFrame& out_frame) {
    if (in_pkt) {
        AVPacket* temp = av_packet_alloc();
        if (temp) {
            av_packet_ref(temp, in_pkt);
            int ret = avcodec_send_packet(codec_ctx_, temp);
            av_packet_free(&temp);
            if (ret < 0 && ret != AVERROR(EAGAIN)) {
                return false;
            }
        }
    } else {
        avcodec_send_packet(codec_ctx_, nullptr);
    }

    int ret = avcodec_receive_frame(codec_ctx_, hw_frame_);
    if (ret == 0) {
        fill_gpu_frame(out_frame);
        return true;
    }
    return false;
}

bool NVDecDecoder::flush_decoder(GpuDecodedFrame& out_frame) {
    avcodec_send_packet(codec_ctx_, nullptr);
    int ret = avcodec_receive_frame(codec_ctx_, hw_frame_);
    if (ret == 0) {
        fill_gpu_frame(out_frame);
        return true;
    }
    return false;
}

bool NVDecDecoder::read_next_frame(GpuDecodedFrame& out_frame) {
    while (true) {
        int ret = avcodec_receive_frame(codec_ctx_, hw_frame_);
        if (ret == 0) {
            fill_gpu_frame(out_frame);
            return true;
        }

        if (ret == AVERROR_EOF) {
            return false;
        }

        ret = av_read_frame(fmt_ctx_, pkt_);
        if (ret < 0) {
            // Flush decoder
            avcodec_send_packet(codec_ctx_, nullptr);
            ret = avcodec_receive_frame(codec_ctx_, hw_frame_);
            if (ret == 0) {
                fill_gpu_frame(out_frame);
                return true;
            }
            return false;
        }

        if (pkt_->stream_index == video_stream_idx_) {
            avcodec_send_packet(codec_ctx_, pkt_);
        }
        av_packet_unref(pkt_);
    }
}

bool NVDecDecoder::transfer_to_host(const GpuDecodedFrame& gpu_frame, AVFrame* sw_frame) {
    if (!gpu_frame.raw_frame) return false;

    if (gpu_frame.raw_frame->format == AV_PIX_FMT_CUDA) {
        av_frame_unref(sw_frame);
        int ret = av_hwframe_transfer_data(sw_frame, gpu_frame.raw_frame, 0);
        return (ret >= 0);
    } else {
        av_frame_ref(sw_frame, gpu_frame.raw_frame);
        return true;
    }
}

} // namespace Forensic
