#pragma once

#include <cstdint>
#include <cstddef>
#include <string>
#include <array>
#include <vector>
#include <chrono>
#include <cstdlib>

namespace Forensic {

// Deterministic Macro-Grid Dimensions
constexpr size_t GRID_COLS = 32;
constexpr size_t GRID_ROWS = 16;
constexpr size_t GRID_CELLS = GRID_COLS * GRID_ROWS; // Exactly 512 discrete cells
constexpr size_t COLOR_CHANNELS = 3;                 // NV12 Y, U, V
constexpr size_t COLOR_GRID_BYTES = GRID_CELLS * COLOR_CHANNELS; // Exactly 1536 bytes

// Cryptographic Constraints
constexpr size_t SHA256_DIGEST_LENGTH = 32;
constexpr size_t SHA256_HEX_LENGTH = 64;

// POSIX IPC & Ring Buffer Sizing
constexpr const char* DEFAULT_SHM_NAME = "/forensic_shm";
constexpr size_t RING_BUFFER_CAPACITY = 256;

// 512-byte spatial luminance signature (integer averages [0..255])
using GridSignature = std::array<uint8_t, GRID_CELLS>;

// 1536-byte spatial full-color signature (Planar: 512 bytes Y, 512 bytes U, 512 bytes V)
using ColorGridSignature = std::array<uint8_t, COLOR_GRID_BYTES>;

// Max entities embedded into pre-hash fusion payload (deterministic fixed size)
constexpr size_t MAX_PREHASH_ENTITIES = 8;

// Deterministic 20-byte packed integer entity feature struct (100% pure integer arithmetic)
struct alignas(4) YoloEntityFeature {
    uint16_t class_id{0};     // COCO class ID (0..79)
    uint16_t box_x1{0};       // Integer permille [0..1000] relative to frame width
    uint16_t box_y1{0};       // Integer permille [0..1000] relative to frame height
    uint16_t box_x2{0};       // Integer permille [0..1000] relative to frame width
    uint16_t box_y2{0};       // Integer permille [0..1000] relative to frame height
    uint8_t  face_y{0};       // Quantized Y of upper head/face region
    uint8_t  face_u{128};     // Quantized U of upper head/face region
    uint8_t  face_v{128};     // Quantized V of upper head/face region
    uint8_t  attire_y{0};     // Quantized Y of torso/attire region
    uint8_t  attire_u{128};   // Quantized U of torso/attire region
    uint8_t  attire_v{128};   // Quantized V of torso/attire region
    uint8_t  heading_code{0}; // Compass heading [0..8]
    uint16_t speed_q8{0};     // Fixed-point 8.8 integer speed (pixels * 256 / frame)
};
static_assert(sizeof(YoloEntityFeature) == 20, "YoloEntityFeature must be exactly 20 bytes");

// Packed deterministic YOLO frame telemetry signature for pre-hash fusion
struct alignas(4) YoloFrameSignature {
    uint32_t entity_count{0};
    std::array<YoloEntityFeature, MAX_PREHASH_ENTITIES> entities{};
};
static_assert(sizeof(YoloFrameSignature) == 4 + 20 * MAX_PREHASH_ENTITIES, "YoloFrameSignature size check");

/**
 * @brief Pure-integer reversible reconstruction of 32x16 RGB image from ColorGridSignature.
 * Uses fixed-point integer BT.601 math (scale factor 1024) to guarantee bit-identical
 * results on all hardware architectures without floating-point drift.
 */
inline void reconstruct_rgb_from_color_grid(
    const ColorGridSignature& color_grid,
    std::array<uint8_t, GRID_CELLS * 3>& out_rgb
) {
    for (size_t i = 0; i < GRID_CELLS; ++i) {
        int32_t y = static_cast<int32_t>(color_grid[i]);
        int32_t u = static_cast<int32_t>(color_grid[GRID_CELLS + i]);
        int32_t v = static_cast<int32_t>(color_grid[GRID_CELLS * 2 + i]);

        int32_t d = u - 128;
        int32_t e = v - 128;

        // Fixed-point integer BT.601 YUV -> RGB with rounding (scale 1024)
        int32_t r = y + ((1436 * e + 512) >> 10);
        int32_t g = y - ((352 * d + 731 * e + 512) >> 10);
        int32_t b = y + ((1815 * d + 512) >> 10);

        out_rgb[i * 3 + 0] = static_cast<uint8_t>(r < 0 ? 0 : (r > 255 ? 255 : r));
        out_rgb[i * 3 + 1] = static_cast<uint8_t>(g < 0 ? 0 : (g > 255 ? 255 : g));
        out_rgb[i * 3 + 2] = static_cast<uint8_t>(b < 0 ? 0 : (b > 255 ? 255 : b));
    }
}

// 32-byte raw binary SHA-256 digest
using HashDigest = std::array<uint8_t, SHA256_DIGEST_LENGTH>;

// Quantized detection bounding box for CAS metadata (Layer 2)
struct alignas(4) QuantizedBBox {
    uint16_t x1{0};           // Integer permille [0..1000] relative to frame width
    uint16_t y1{0};           // Integer permille [0..1000] relative to frame height
    uint16_t x2{0};           // Integer permille [0..1000] relative to frame width
    uint16_t y2{0};           // Integer permille [0..1000] relative to frame height
    uint16_t class_id{0};     // COCO class ID (0..79)
    uint8_t  confidence_q8{0};// Quantized confidence [0..255]
    uint8_t  reserved{0};     // Padding for 4-byte alignment
};
static_assert(sizeof(QuantizedBBox) == 12, "QuantizedBBox must be exactly 12 bytes");

inline float compute_bbox_iou(const QuantizedBBox& a, const QuantizedBBox& b) {
    if (a.class_id != b.class_id) return 0.0f;
    int x1 = std::max<int>(a.x1, b.x1);
    int y1 = std::max<int>(a.y1, b.y1);
    int x2 = std::min<int>(a.x2, b.x2);
    int y2 = std::min<int>(a.y2, b.y2);
    int iw = std::max<int>(0, x2 - x1);
    int ih = std::max<int>(0, y2 - y1);
    int inter_area = iw * ih;
    int area_a = std::max<int>(0, a.x2 - a.x1) * std::max<int>(0, a.y2 - a.y1);
    int area_b = std::max<int>(0, b.x2 - b.x1) * std::max<int>(0, b.y2 - b.y1);
    int union_area = area_a + area_b - inter_area;
    return union_area > 0 ? (static_cast<float>(inter_area) / static_cast<float>(union_area)) : 0.0f;
}

// Content-Addressable Storage (CAS) record for Layer 2 telemetry
struct FrameCasRecord {
    std::string packet_hash;        // 64-char hex string of Layer 1 canonical leaf digest
    uint64_t leaf_index{0};         // Index in the Merkle Tree (0..N-1)
    std::string video_id;
    int64_t pts{0};                 // Presentation timestamp (microseconds)
    int64_t dts{0};                 // Decoding timestamp (microseconds)
    ColorGridSignature color_grid{};// Planar 32x16 Y, U, V color grid (1536 bytes)
    std::vector<QuantizedBBox> detections;
    std::string semantic_summary;
};

// Transactional record for SQLite ledger
struct FrameHashRecord {
    int64_t pts{0};
    HashDigest hash{};
    std::string hex_hash{};
    uint64_t leaf_index{0};
    int64_t dts{0};
};

// Discrete Traffic Signal States
enum SignalState : uint8_t {
    STATE_RED = 0,
    STATE_AMBER = 1,
    STATE_GREEN = 2,
    STATE_UNKNOWN = 255
};

// Discrete Color Palette Bins
enum ColorBin : uint8_t {
    COLOR_BLACK = 0,
    COLOR_WHITE = 1,
    COLOR_GREY = 2,
    COLOR_RED = 3,
    COLOR_ORANGE = 4,
    COLOR_YELLOW = 5,
    COLOR_GREEN = 6,
    COLOR_BLUE = 7,
    COLOR_PURPLE = 8,
    COLOR_UNKNOWN = 255
};

struct DominantColors {
    uint8_t primary{COLOR_UNKNOWN};
    uint8_t secondary{COLOR_UNKNOWN};
};

// Specialized Forensic Entity Record for Layer 2 Intelligence (forensic_frame_metadata)
struct ForensicEntityRecord {
    int64_t id{0};
    std::string packet_hash;       // 32-byte SHA256 (64 hex characters) from Layer 1
    std::string video_id;
    uint64_t leaf_index{0};
    int64_t pts{0};
    int64_t dts{0};
    int track_id{0};
    std::string entity_type;       // 'FACE', 'VEHICLE', 'SIGNAL', 'PERSON'
    float bbox_x1{0.0f};
    float bbox_y1{0.0f};
    float bbox_x2{0.0f};
    float bbox_y2{0.0f};
    float confidence{0.0f};

    // Specialized Forensic Payloads
    std::vector<float> face_embedding;   // 512-D ArcFace vector (empty if not face)
    std::string plate_text;              // OCR string (empty if not vehicle)
    int signal_state{STATE_UNKNOWN};     // Enum 0, 1, 2, 255
    int signal_timer{-1};                // Countdown integer (-1 if not timer)
    DominantColors dominant_colors{};    // Top 2 HSV color bins
    std::vector<uint8_t> ref_crop_blob;  // JPEG/WebP image data (Populated ONLY on track birth)
    bool is_track_birth{false};
};

// Forensic Tamper Localization structures
struct TamperDelta {
    uint64_t leaf_index{0};
    int64_t pts{0};
    std::string change_type; // "FACE_IDENTITY_SWAP", "PLATE_TAMPERED", "SIGNAL_TAMPERED", "TIMER_TAMPERED", "CLOTHING_COLOR_MISMATCH", "ENTITY_REMOVED", "ENTITY_ADDED", "SPATIAL_INPAINTING", "BITSTREAM_MUTATION"
    uint16_t class_id{0};
    std::string class_name;
    float max_iou{0.0f};
    uint32_t luma_residual{0};
    float cosine_similarity{1.0f};
    int levenshtein_distance{0};
    int signal_state_base{STATE_UNKNOWN};
    int signal_state_suspect{STATE_UNKNOWN};
    int timer_base{-1};
    int timer_suspect{-1};
    std::string colors_base;
    std::string colors_suspect;
    std::string details;
};

struct TamperInterval {
    uint64_t leaf_start{0};
    uint64_t leaf_end{0};
    int64_t pts_start{0};
    int64_t pts_end{0};
    double duration_ms{0.0};
    std::vector<TamperDelta> deltas;
};

struct TamperAuditReport {
    bool is_pristine{false};
    std::string video_id;
    std::string suspect_uri;
    std::string baseline_root;
    std::string suspect_root;
    uint64_t total_packets{0};
    uint64_t tampered_packets{0};
    std::vector<TamperInterval> intervals;
    std::string json_report;
};

// Video metadata record for SQLite ledger
struct VideoMetadata {
    std::string video_id;
    std::string source_uri;
    int64_t duration_us{0};
    int64_t file_size{0};
    std::string creation_date;
    std::string mop; // Mode of Production / Source Device Tag
    std::string root_hash;
};

// Cryptographic Block for vector_frames_blockchain
struct VectorBlock {
    int64_t block_index{0};
    std::string video_id;
    int64_t pts{0};
    int64_t frame_index{0};
    GridSignature grid_signature{};
    ColorGridSignature color_grid_signature{};
    std::string frame_hash;
    std::string prev_block_hash;
    std::string block_hash;
    std::string timestamp;
};

// Cryptographic Block for semantic_evidence_blockchain
struct SemanticBlock {
    int64_t block_index{0};
    std::string video_id;
    int64_t window_idx{0};
    int64_t entity_idx{0};
    int64_t start_pts{0};
    int64_t end_pts{0};
    int boustro_cx{0};
    int boustro_cy{0};
    int boustro_s1d{0};
    int centroid_x{0};
    int centroid_y{0};
    float speed{0.0f};
    uint8_t heading_code{0};
    std::string entity_label;
    std::string evidence_payload;
    std::string prev_block_hash;
    std::string block_hash;
    std::string timestamp;
};

// Convert raw digest to 64-character lowercase hex string
inline std::string to_hex_string(const uint8_t* data, size_t len) {
    static const char hex_digits[] = "0123456789abcdef";
    std::string hex;
    hex.reserve(len * 2);
    for (size_t i = 0; i < len; ++i) {
        hex.push_back(hex_digits[(data[i] >> 4) & 0x0F]);
        hex.push_back(hex_digits[data[i] & 0x0F]);
    }
    return hex;
}

inline std::string to_hex_string(const HashDigest& digest) {
    return to_hex_string(digest.data(), digest.size());
}

// Convert 64-character lowercase hex string to 32-byte digest
inline HashDigest hex_to_digest(const std::string& hex) {
    HashDigest digest{};
    if (hex.length() != SHA256_HEX_LENGTH) return digest;
    for (size_t i = 0; i < SHA256_DIGEST_LENGTH; ++i) {
        std::string byteString = hex.substr(i * 2, 2);
        digest[i] = static_cast<uint8_t>(std::strtoul(byteString.c_str(), nullptr, 16));
    }
    return digest;
}

} // namespace Forensic
