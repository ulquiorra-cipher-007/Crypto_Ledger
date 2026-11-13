#include "motion_tracker.hpp"
#include <cstdio>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <limits>

namespace Forensic {

const char* MotionTracker::get_coco_name(int coco_class) {
    static const char* const s_coco_names[80] = {
        "Person", "Bicycle", "Car", "Motorcycle", "Airplane", "Bus", "Train", "Truck", "Boat", "Traffic Light",
        "Fire Hydrant", "Stop Sign", "Parking Meter", "Bench", "Bird", "Cat", "Dog", "Horse", "Sheep", "Cow",
        "Elephant", "Bear", "Zebra", "Giraffe", "Backpack", "Umbrella", "Handbag", "Tie", "Suitcase", "Frisbee",
        "Skis", "Snowboard", "Sports Ball", "Kite", "Baseball Bat", "Baseball Glove", "Skateboard", "Surfboard", "Tennis Racket", "Bottle",
        "Wine Glass", "Cup", "Fork", "Knife", "Spoon", "Bowl", "Banana", "Apple", "Sandwich", "Orange",
        "Broccoli", "Carrot", "Hot Dog", "Pizza", "Donut", "Cake", "Chair", "Couch", "Potted Plant", "Bed",
        "Dining Table", "Toilet", "TV", "Laptop", "Mouse", "Remote", "Keyboard", "Cell Phone", "Microwave", "Oven",
        "Toaster", "Sink", "Refrigerator", "Book", "Clock", "Vase", "Scissors", "Teddy Bear", "Hair Drier", "Toothbrush"
    };
    if (coco_class >= 0 && coco_class < 80) return s_coco_names[coco_class];
    return "Entity";
}

int MotionTracker::get_semantic_category(int coco_class, bool is_paired) {
    if (coco_class == CLASS_PERSON) {
        return is_paired ? SEMANTIC_CAT_CYCLIST : SEMANTIC_CAT_PERSON;
    }
    if (coco_class == CLASS_BICYCLE) {
        return is_paired ? SEMANTIC_CAT_CYCLIST : SEMANTIC_CAT_VEHICLE;
    }
    if (coco_class >= 2 && coco_class <= 8) {
        return SEMANTIC_CAT_VEHICLE; // Car, Motorcycle, Airplane, Bus, Train, Truck, Boat
    }
    return SEMANTIC_CAT_OBJECT; // Animals, dynamic portable luggage/objects
}

MotionTracker::MotionTracker(
    float conf_threshold,
    float nms_iou_threshold,
    float max_match_distance,
    float pairing_distance_ratio
) : conf_thresh_(conf_threshold),
    nms_thresh_(nms_iou_threshold),
    max_dist_(max_match_distance),
    pairing_ratio_(pairing_distance_ratio) {
    candidate_entities_.reserve(128);
    nms_kept_.reserve(128);
    nms_suppressed_.reserve(128);
    matched_new_.reserve(128);
    matched_active_.reserve(128);
    active_tracks_.reserve(64);
}

const char* MotionTracker::heading_to_string(uint8_t heading_code) {
    switch (heading_code) {
        case 1: return "E";
        case 2: return "NE";
        case 3: return "N";
        case 4: return "NW";
        case 5: return "W";
        case 6: return "SW";
        case 7: return "S";
        case 8: return "SE";
        default: return "Stationary";
    }
}

uint8_t MotionTracker::compute_heading_code(float dx, float dy, float speed) {
    if (speed < 1.0f) {
        return 0; // Stationary
    }

    // In video coordinates, dy < 0 is North (upwards), dy > 0 is South (downwards)
    // dx > 0 is East (rightwards), dx < 0 is West (leftwards)
    // Angle in degrees from East (0 deg) counter-clockwise
    float rad = std::atan2(-dy, dx);
    float deg = rad * (180.0f / 3.14159265358979323846f);
    if (deg < 0.0f) deg += 360.0f;

    // 8 compass sectors (each 45 deg centered on 0, 45, 90, etc.)
    int sector = static_cast<int>(std::floor((deg + 22.5f) / 45.0f)) % 8;
    // Map sector to 1-based code: 0->E(1), 1->NE(2), 2->N(3), 3->NW(4), 4->W(5), 5->SW(6), 6->S(7), 7->SE(8)
    return static_cast<uint8_t>(sector + 1);
}

void MotionTracker::parse_candidate_boxes(
    const float* trt_output,
    int width,
    int height,
    std::vector<TrackedEntity>& entities
) {
    entities.clear();

    const float scale_x = static_cast<float>(width) / 640.0f;
    const float scale_y = static_cast<float>(height) / 640.0f;

    constexpr int NUM_ANCHORS = 8400;
    const float* p_cx = trt_output + 0 * NUM_ANCHORS;
    const float* p_cy = trt_output + 1 * NUM_ANCHORS;
    const float* p_w  = trt_output + 2 * NUM_ANCHORS;
    const float* p_h  = trt_output + 3 * NUM_ANCHORS;

    // Mask for dynamic surveillance entities (persons, vehicles, animals, portable objects)
    static const bool s_is_dynamic[80] = {
        true,  true,  true,  true,  true,  true,  true,  true,  true,  false, // 0-9 (0:person, 1:bike, 2:car, 3:motorcycle, 4:plane, 5:bus, 6:train, 7:truck, 8:boat, 9:traffic light)
        false, false, false, false, true,  true,  true,  true,  true,  true,  // 10-19 (14:bird, 15:cat, 16:dog, 17:horse, 18:sheep, 19:cow)
        true,  true,  true,  true,  true,  true,  true,  false, true,  true,  // 20-29 (24:backpack, 25:umbrella, 26:handbag, 28:suitcase, 29:frisbee)
        true,  true,  true,  true,  false, false, true,  true,  false, false, // 30-39 (36:skateboard, 37:surfboard)
        false, false, false, false, false, false, false, false, false, false, // 40-49
        false, false, false, false, false, false, false, false, false, false, // 50-59
        false, false, false, false, false, false, false, false, false, false, // 60-69
        false, false, false, false, false, false, false, true,  false, false  // 70-79 (77:teddy bear)
    };

    for (int k = 0; k < NUM_ANCHORS; ++k) {
        float best_score = 0.0f;
        int best_class = -1;

        for (int c = 0; c < 80; ++c) {
            if (!s_is_dynamic[c]) continue;
            float score = trt_output[(4 + c) * NUM_ANCHORS + k];
            if (score > best_score) {
                best_score = score;
                best_class = c;
            }
        }

        if (best_score < conf_thresh_ || best_class < 0) {
            continue;
        }

        float cx = p_cx[k] * scale_x;
        float cy = p_cy[k] * scale_y;
        float w  = p_w[k] * scale_x;
        float h  = p_h[k] * scale_y;

        TrackedEntity entity;
        entity.track_id = 0;
        entity.class_id = best_class;
        entity.score = best_score;
        entity.cx = cx;
        entity.cy = cy;
        entity.x1 = cx - 0.5f * w;
        entity.y1 = cy - 0.5f * h;
        entity.x2 = cx + 0.5f * w;
        entity.y2 = cy + 0.5f * h;
        std::strncpy(entity.label, get_coco_name(best_class), sizeof(entity.label) - 1);
        entity.label[sizeof(entity.label) - 1] = '\0';
        entity.is_paired = false;

        entities.push_back(entity);
    }
}

void MotionTracker::apply_nms(std::vector<TrackedEntity>& boxes) {
    if (boxes.size() <= 1) return;

    std::sort(boxes.begin(), boxes.end(), [](const TrackedEntity& a, const TrackedEntity& b) {
        return a.score > b.score;
    });

    nms_kept_.clear();
    nms_suppressed_.assign(boxes.size(), false);

    for (size_t i = 0; i < boxes.size(); ++i) {
        if (nms_suppressed_[i]) continue;
        nms_kept_.push_back(boxes[i]);

        float area_i = (boxes[i].x2 - boxes[i].x1) * (boxes[i].y2 - boxes[i].y1);

        for (size_t j = i + 1; j < boxes.size(); ++j) {
            if (nms_suppressed_[j]) continue;

            // Class-wise NMS
            if (boxes[i].class_id != boxes[j].class_id) continue;

            float inter_x1 = std::max(boxes[i].x1, boxes[j].x1);
            float inter_y1 = std::max(boxes[i].y1, boxes[j].y1);
            float inter_x2 = std::min(boxes[i].x2, boxes[j].x2);
            float inter_y2 = std::min(boxes[i].y2, boxes[j].y2);

            float inter_w = std::max(0.0f, inter_x2 - inter_x1);
            float inter_h = std::max(0.0f, inter_y2 - inter_y1);
            float inter_area = inter_w * inter_h;

            float area_j = (boxes[j].x2 - boxes[j].x1) * (boxes[j].y2 - boxes[j].y1);
            float union_area = area_i + area_j - inter_area;

            if (union_area > 0.0f && (inter_area / union_area) > nms_thresh_) {
                nms_suppressed_[j] = true;
            }
        }
    }

    boxes = nms_kept_;
}

void MotionTracker::update_tracks(std::vector<TrackedEntity>& detections) {
    // 1. Person-Bicycle Pairing
    for (auto& det : detections) {
        if (det.class_id != CLASS_PERSON) continue;
        float h_p = det.y2 - det.y1;

        for (auto& bike : detections) {
            if (bike.class_id != CLASS_BICYCLE) continue;
            float h_b = bike.y2 - bike.y1;
            float max_h = std::max(h_p, h_b);

            float inter_w = std::max(0.0f, std::min(det.x2, bike.x2) - std::max(det.x1, bike.x1));
            float inter_h = std::max(0.0f, std::min(det.y2, bike.y2) - std::max(det.y1, bike.y1));
            bool intersects = (inter_w > 0.0f && inter_h > 0.0f);
            float dist = std::hypot(det.cx - bike.cx, det.cy - bike.cy);

            if (intersects || dist < (pairing_ratio_ * max_h)) {
                det.is_paired = true;
                bike.is_paired = true;
                break;
            }
        }
    }

    // 2. Nearest Neighbor Tracking
    matched_new_.assign(detections.size(), false);
    matched_active_.assign(active_tracks_.size(), false);

    for (size_t a = 0; a < active_tracks_.size(); ++a) {
        float min_dist = std::numeric_limits<float>::max();
        int best_idx = -1;

        for (size_t n = 0; n < detections.size(); ++n) {
            if (matched_new_[n]) continue;
            // Match same class or compatible vehicle category
            bool class_match = (active_tracks_[a].class_id == detections[n].class_id) ||
                (get_semantic_category(active_tracks_[a].class_id, false) == SEMANTIC_CAT_VEHICLE &&
                 get_semantic_category(detections[n].class_id, false) == SEMANTIC_CAT_VEHICLE);
            if (!class_match) continue;

            float dist = std::hypot(active_tracks_[a].cx - detections[n].cx,
                                    active_tracks_[a].cy - detections[n].cy);
            if (dist < min_dist && dist <= max_dist_) {
                min_dist = dist;
                best_idx = static_cast<int>(n);
            }
        }

        if (best_idx >= 0) {
            matched_active_[a] = true;
            matched_new_[best_idx] = true;

            float prev_x = active_tracks_[a].cx;
            float prev_y = active_tracks_[a].cy;
            float cur_x  = detections[best_idx].cx;
            float cur_y  = detections[best_idx].cy;

            float dx = cur_x - prev_x;
            float dy = cur_y - prev_y;
            float speed = std::hypot(dx, dy);

            active_tracks_[a].prev_cx = prev_x;
            active_tracks_[a].prev_cy = prev_y;
            active_tracks_[a].cx = cur_x;
            active_tracks_[a].cy = cur_y;
            active_tracks_[a].x1 = detections[best_idx].x1;
            active_tracks_[a].y1 = detections[best_idx].y1;
            active_tracks_[a].x2 = detections[best_idx].x2;
            active_tracks_[a].y2 = detections[best_idx].y2;
            active_tracks_[a].score = detections[best_idx].score;
            active_tracks_[a].is_paired = detections[best_idx].is_paired;
            active_tracks_[a].class_id = detections[best_idx].class_id;
            std::snprintf(active_tracks_[a].label, sizeof(active_tracks_[a].label), "%s", detections[best_idx].label);
            active_tracks_[a].vx = dx;
            active_tracks_[a].vy = dy;
            active_tracks_[a].speed = speed;
            active_tracks_[a].heading_code = compute_heading_code(dx, dy, speed);
            active_tracks_[a].missed_frames = 0;
        } else {
            active_tracks_[a].missed_frames++;
        }
    }

    // Add unmatched detections as new tracks (skip paired bicycles since the cyclist track embodies them)
    for (size_t n = 0; n < detections.size(); ++n) {
        if (!matched_new_[n]) {
            if (detections[n].class_id == CLASS_BICYCLE && detections[n].is_paired) {
                continue;
            }
            TrackedEntity track = detections[n];
            track.track_id = next_track_id_++;
            track.prev_cx = track.cx;
            track.prev_cy = track.cy;
            track.vx = 0.0f;
            track.vy = 0.0f;
            track.speed = 0.0f;
            track.heading_code = 0; // Stationary initially
            track.missed_frames = 0;
            active_tracks_.push_back(track);
        }
    }

    // Suppress redundant bicycle tracks that are already embodied by a paired person track within pairing proximity
    for (auto& t : active_tracks_) {
        if (t.class_id == CLASS_BICYCLE) {
            for (const auto& p : active_tracks_) {
                if (p.class_id == CLASS_PERSON && p.is_paired) {
                    float d = std::hypot(t.cx - p.cx, t.cy - p.cy);
                    if (d <= 160.0f) {
                        t.missed_frames = 999; // Mark for immediate pruning
                        break;
                    }
                }
            }
        }
    }

    // Prune stale tracks (> 10 missed frames)
    active_tracks_.erase(
        std::remove_if(active_tracks_.begin(), active_tracks_.end(),
            [](const TrackedEntity& t) { return t.missed_frames > 10; }),
        active_tracks_.end()
    );

    // Sort active tracks: Paired Cyclists > Persons > Vehicles > Objects
    std::sort(active_tracks_.begin(), active_tracks_.end(), [](const TrackedEntity& a, const TrackedEntity& b) {
        auto priority = [](const TrackedEntity& e) -> int {
            if (e.class_id == CLASS_PERSON && e.is_paired) return 300;
            if (e.class_id == CLASS_PERSON) return 200;
            if (e.class_id >= 1 && e.class_id <= 8) return 100;
            return 50;
        };
        int pa = priority(a);
        int pb = priority(b);
        if (pa != pb) return pa > pb;
        return a.score > b.score;
    });
}

void MotionTracker::process_frame(
    const float* trt_output_fp32,
    int frame_width,
    int frame_height,
    int64_t pts,
    SemanticMotionTelemetry& out_telemetry,
    char* out_english,
    size_t max_english_len
) {
    out_telemetry = {};

    if (!trt_output_fp32) return;

    // 1. Parse raw detections across COCO classes
    parse_candidate_boxes(trt_output_fp32, frame_width, frame_height, candidate_entities_);

    // 2. Non-Maximum Suppression per class
    apply_nms(candidate_entities_);

    // 3. Multi-object tracking and pairing
    update_tracks(candidate_entities_);

    // 4. Populate binary shared memory telemetry
    bool has_person = false;
    bool has_bike = false;
    bool has_paired = false;
    bool has_vehicle = false;

    for (const auto& t : active_tracks_) {
        if (t.class_id == CLASS_PERSON) {
            has_person = true;
            if (t.is_paired) has_paired = true;
        } else if (t.class_id == CLASS_BICYCLE) {
            has_bike = true;
        } else if (t.class_id >= 2 && t.class_id <= 8) {
            has_vehicle = true;
        }
    }

    out_telemetry.has_person = has_person ? 1 : 0;
    out_telemetry.has_bicycle = (has_bike || has_vehicle) ? 1 : 0;
    out_telemetry.is_paired = has_paired ? 1 : 0;

    if (!active_tracks_.empty()) {
        const auto& primary = active_tracks_[0];
        out_telemetry.heading_code = primary.heading_code;
        out_telemetry.centroid_x = static_cast<uint16_t>(std::clamp(primary.cx, 0.0f, 65535.0f));
        out_telemetry.centroid_y = static_cast<uint16_t>(std::clamp(primary.cy, 0.0f, 65535.0f));
        out_telemetry.speed = primary.speed;

        const char* heading_str = heading_to_string(primary.heading_code);

        // Compact summary inside 32B telemetry payload
        if (active_tracks_.size() == 1) {
            std::snprintf(
                out_telemetry.summary,
                sizeof(out_telemetry.summary),
                "%.10s %.2s %.1f",
                (primary.is_paired ? "Person+Bike" : primary.label),
                heading_str,
                primary.speed
            );
        } else {
            std::snprintf(
                out_telemetry.summary,
                sizeof(out_telemetry.summary),
                "%d Ent:%.5s+%.5s",
                static_cast<int>(active_tracks_.size()),
                (active_tracks_[0].is_paired ? "Bike" : active_tracks_[0].label),
                active_tracks_[1].label
            );
        }

        // Plain-English telemetry formatting preserving cross-entity correlation
        if (out_english && max_english_len > 0) {
            if (active_tracks_.size() == 1) {
                const char* obj_tag = primary.is_paired ? "With Bicycle" :
                    (primary.class_id == CLASS_PERSON ? "Solo" :
                    (primary.class_id <= 8 ? "Automobile" : "Dynamic Entity"));
                std::snprintf(
                    out_english,
                    max_english_len,
                    "[PTS: %ld] %s at (%d, %d) | Heading: %s | Speed: %.1f px/frame | Object: %s",
                    static_cast<long>(pts),
                    primary.label,
                    static_cast<int>(primary.cx),
                    static_cast<int>(primary.cy),
                    heading_str,
                    primary.speed,
                    obj_tag
                );
            } else {
                std::string corr = "[PTS: " + std::to_string(pts) + "] Correlated Scene (" +
                    std::to_string(active_tracks_.size()) + " Entities): ";
                for (size_t i = 0; i < active_tracks_.size(); ++i) {
                    if (i > 0) corr += " || ";
                    const auto& e = active_tracks_[i];
                    const char* h_str = heading_to_string(e.heading_code);
                    const char* tag = e.is_paired ? "With Bicycle" :
                        (e.class_id == CLASS_PERSON ? "Solo" :
                        (e.class_id <= 8 ? "Automobile" : "Dynamic Entity"));
                    char buf[128];
                    std::snprintf(buf, sizeof(buf), "• [%zu] %s at (%d, %d) | Heading: %s | Speed: %.1f px/frame | Object: %s",
                                  i + 1, e.label, static_cast<int>(e.cx), static_cast<int>(e.cy), h_str, e.speed, tag);
                    corr += buf;
                }
                std::strncpy(out_english, corr.c_str(), max_english_len - 1);
                out_english[max_english_len - 1] = '\0';
            }
        }
    } else {
        if (out_english && max_english_len > 0) {
            std::snprintf(
                out_english,
                max_english_len,
                "[PTS: %ld] Scene Clear | Heading: Stationary | Speed: 0.0 px/frame | Object: None",
                static_cast<long>(pts)
            );
        }
    }
}

void MotionTracker::serialize_to_frame(
    const SemanticMotionTelemetry& telem,
    TelemetryFrame& frame
) {
    std::memcpy(frame._pad, &telem, sizeof(SemanticMotionTelemetry));
}

} // namespace Forensic
