#pragma once

#include <cstdint>
#include <cstddef>
#include <string>
#include <vector>
#include <cmath>
#include <algorithm>
#include "ring_buffer.hpp"

namespace Forensic {

constexpr int CLASS_PERSON = 0;
constexpr int CLASS_BICYCLE = 1;
constexpr int CLASS_CAR = 2;
constexpr int CLASS_MOTORCYCLE = 3;
constexpr int CLASS_AIRPLANE = 4;
constexpr int CLASS_BUS = 5;
constexpr int CLASS_TRAIN = 6;
constexpr int CLASS_TRUCK = 7;
constexpr int CLASS_BOAT = 8;

constexpr int SEMANTIC_CAT_PERSON = 0;   // 0b00: Person (Solo)
constexpr int SEMANTIC_CAT_CYCLIST = 1;  // 0b01: Woman / Person (With Bicycle)
constexpr int SEMANTIC_CAT_VEHICLE = 2;  // 0b10: Automobile / Vehicle
constexpr int SEMANTIC_CAT_OBJECT = 3;   // 0b11: Dynamic Anomaly / Object

/**
 * @brief 32-byte compact binary telemetry serialized directly into TelemetryFrame::_pad.
 * Preserves exact 640-byte TelemetryFrame and 164,608-byte ForensicSharedMemory size.
 */
struct alignas(4) SemanticMotionTelemetry {
    uint8_t has_person;
    uint8_t has_bicycle;
    uint8_t is_paired;
    uint8_t heading_code; // 0=Stationary, 1=E, 2=NE, 3=N, 4=NW, 5=W, 6=SW, 7=S, 8=SE
    uint16_t centroid_x;
    uint16_t centroid_y;
    float speed;          // pixels per frame
    char summary[20];     // Short descriptor e.g. "Person+Car NE 12.5"
};

static_assert(sizeof(SemanticMotionTelemetry) == 32, "SemanticMotionTelemetry must be exactly 32 bytes");


struct TrackedEntity {
    int track_id{0};
    int class_id{0};     // COCO class ID (0..79)
    char label[24]{};    // Descriptive name e.g. "Person", "Car", "Truck", "Boat"
    float x1{0.0f};
    float y1{0.0f};
    float x2{0.0f};
    float y2{0.0f};
    float cx{0.0f};
    float cy{0.0f};
    float score{0.0f};
    float prev_cx{0.0f};
    float prev_cy{0.0f};
    float vx{0.0f};
    float vy{0.0f};
    float speed{0.0f};
    uint8_t heading_code{0};
    bool is_paired{false};
    int missed_frames{0};
};

/**
 * @brief Centroid Motion Tracker & Multi-Entity Correlated Plain-English Telemetry Engine
 * 
 * Ingests 80-class COCO YOLO TensorRT detections (including Vehicles, Persons, Bicycles,
 * Animals, and Objects), tracks multiple simultaneous entities across frames with
 * class-wise NMS, pairs composite cyclist entities, formats multi-entity correlated
 * plain-English telemetry strings, and serializes the 32-byte payload directly into
 * the POSIX shared memory ring buffer.
 */
class MotionTracker {
public:
    explicit MotionTracker(
        float conf_threshold = 0.25f,
        float nms_iou_threshold = 0.45f,
        float max_match_distance = 160.0f,
        float pairing_distance_ratio = 1.0f
    );

    /**
     * @brief Process a single inference frame.
     * 
     * @param trt_output_fp32  Device or host pointer to 1x84x8400 TensorRT output tensor.
     * @param frame_width      Native frame width (e.g. 1920).
     * @param frame_height     Native frame height (e.g. 1080).
     * @param pts              Current video frame PTS in microseconds.
     * @param out_telemetry    Output 32-byte binary payload for ring buffer.
     * @param out_english      Optional buffer to receive plain-English formatted telemetry.
     * @param max_english_len  Size of out_english buffer.
     */
    void process_frame(
        const float* trt_output_fp32,
        int frame_width,
        int frame_height,
        int64_t pts,
        SemanticMotionTelemetry& out_telemetry,
        char* out_english = nullptr,
        size_t max_english_len = 0
    );

    /**
     * @brief Serialize SemanticMotionTelemetry into TelemetryFrame's pad bytes.
     */
    static void serialize_to_frame(const SemanticMotionTelemetry& telem, TelemetryFrame& frame);

    /**
     * @brief Convert integer heading code to direction string.
     */
    static const char* heading_to_string(uint8_t heading_code);

    /**
     * @brief Get human-readable COCO class name.
     */
    static const char* get_coco_name(int coco_class);

    /**
     * @brief Map COCO class and pairing status to 2-bit semantic category.
     */
    static int get_semantic_category(int coco_class, bool is_paired);

    const std::vector<TrackedEntity>& active_tracks() const { return active_tracks_; }

private:
    float conf_thresh_;
    float nms_thresh_;
    float max_dist_;
    float pairing_ratio_;
    int next_track_id_{1};

    std::vector<TrackedEntity> active_tracks_;
    std::vector<TrackedEntity> candidate_entities_;
    std::vector<TrackedEntity> nms_kept_;
    std::vector<bool> nms_suppressed_;
    std::vector<bool> matched_new_;
    std::vector<bool> matched_active_;

    void parse_candidate_boxes(
        const float* trt_output,
        int width,
        int height,
        std::vector<TrackedEntity>& entities
    );

    void apply_nms(std::vector<TrackedEntity>& boxes);

    void update_tracks(std::vector<TrackedEntity>& detections);

    uint8_t compute_heading_code(float dx, float dy, float speed);
};

} // namespace Forensic
