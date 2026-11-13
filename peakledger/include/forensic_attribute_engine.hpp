#pragma once

#include "common.hpp"
#include "motion_tracker.hpp"
#include "nvdec_decoder.hpp"

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavutil/opt.h>
}

#include <vector>
#include <string>
#include <array>
#include <unordered_map>
#include <memory>
#include <cmath>
#include <algorithm>

namespace Forensic {

/**
 * @brief Production sweet-spot threshold for ArcFace cosine similarity
 * across aggressive WhatsApp / WebRTC transcoding and H.264 macroblocking.
 */
constexpr float FACE_COSINE_MATCH_THRESHOLD = 0.72f;

/**
 * @brief Maximum allowable Levenshtein distance for vehicle plate matching
 * to accommodate compression artifacts and character noise.
 */
constexpr int PLATE_LEVENSHTEIN_MAX_DISTANCE = 1;

/**
 * @brief Layer 2 Forensic Intelligence & Attribute Engine
 * 
 * Performs:
 * 1. 512-D ArcFace facial embedding extraction & 1-to-1 cosine similarity auditing
 * 2. Alphanumeric license plate OCR with Levenshtein distance auditing (<= 1)
 * 3. Discrete traffic signal state classification (RED, AMBER, GREEN) & countdown timer
 * 4. Pedestrian torso/lower-body dominant HSV clothing palette extraction
 * 5. Track-aware storage optimization (stores reference crops only on track birth)
 */
class ForensicAttributeEngine {
public:
    explicit ForensicAttributeEngine(const std::string& arcface_engine_path = "");
    ~ForensicAttributeEngine();

    ForensicAttributeEngine(const ForensicAttributeEngine&) = delete;
    ForensicAttributeEngine& operator=(const ForensicAttributeEngine&) = delete;

    // --- Forensic Metrics & Mathematical Primitives ---

    // 1-to-1 Cosine similarity over unit-normalized 512-D vectors
    static float compute_cosine_similarity(const std::vector<float>& u, const std::vector<float>& v);
    static float compute_cosine_similarity(const float* u, const float* v, size_t dim = 512);

    // Levenshtein edit distance between alphanumeric strings
    static int compute_levenshtein_distance(const std::string& s1, const std::string& s2);

    // Human-readable string conversions
    static const char* signal_state_to_string(int state);
    static const char* color_bin_to_string(uint8_t bin);

    // --- High-Level Forensic Attribute Ingestion ---

    /**
     * @brief Extract structured forensic entity records from detected tracks on a decoded frame.
     */
    std::vector<ForensicEntityRecord> extract_frame_attributes(
        const std::vector<TrackedEntity>& active_tracks,
        const uint8_t* nv12_y,
        const uint8_t* nv12_uv,
        int frame_width,
        int frame_height,
        int pitch_y,
        int pitch_uv,
        int64_t pts,
        int64_t dts,
        uint64_t leaf_index,
        const std::string& packet_hash,
        const std::string& video_id
    );

    // --- Individual Specialized Attribute Extractors ---

    // 1. Face ArcFace 512-D Normalized Embedding
    std::vector<float> extract_face_embedding(
        const uint8_t* nv12_y,
        const uint8_t* nv12_uv,
        int width, int height, int pitch_y, int pitch_uv,
        float x1, float y1, float x2, float y2
    );

    // 2. Alphanumeric Vehicle Plate OCR
    std::string extract_plate_text(
        const uint8_t* nv12_y,
        const uint8_t* nv12_uv,
        int width, int height, int pitch_y, int pitch_uv,
        float x1, float y1, float x2, float y2,
        int class_id,
        float& out_confidence
    );

    // 3. Discrete Traffic Signal State & Countdown Timer
    void extract_traffic_signal(
        const uint8_t* nv12_y,
        const uint8_t* nv12_uv,
        int width, int height, int pitch_y, int pitch_uv,
        float x1, float y1, float x2, float y2,
        int& out_signal_state,
        int& out_signal_timer
    );

    // 4. Pedestrian HSV Dominant Color Palette (Top 2 Bins)
    DominantColors extract_pedestrian_palette(
        const uint8_t* nv12_y,
        const uint8_t* nv12_uv,
        int width, int height, int pitch_y, int pitch_uv,
        float x1, float y1, float x2, float y2
    );

    // 5. Crop & JPEG Compression for Reference Crop Storage (Track Birth)
    std::vector<uint8_t> encode_reference_crop(
        const uint8_t* nv12_y,
        const uint8_t* nv12_uv,
        int width, int height, int pitch_y, int pitch_uv,
        float x1, float y1, float x2, float y2
    );

    // Reset tracking state between videos
    void reset_tracks();

private:
    struct TrackHistory {
        float max_confidence{0.0f};
        int frames_seen{0};
        bool crop_saved{false};
    };

    std::unordered_map<int, TrackHistory> track_history_;
    std::string arcface_engine_path_;

    // Dedicated MJPEG encoder for reference crop compression
    AVCodecContext* jpeg_ctx_{nullptr};
    const AVCodec* jpeg_codec_{nullptr};
    AVFrame* crop_yuv_frame_{nullptr};
    int enc_width_{0};
    int enc_height_{0};

    void init_jpeg_encoder(int width, int height);
};

} // namespace Forensic
