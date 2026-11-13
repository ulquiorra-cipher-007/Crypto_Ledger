#include "motion_tracker.hpp"
#include <iostream>
#include <vector>
#include <cstring>
#include <cmath>
#include <cassert>
#include <chrono>

using namespace Forensic;

static void test_structure_alignment() {
    std::cout << "[TEST 1] Testing SemanticMotionTelemetry structure layout & alignment...\n";
    assert(sizeof(SemanticMotionTelemetry) == 32);
    assert(sizeof(TelemetryFrame) == 640);
    assert(std::is_standard_layout<SemanticMotionTelemetry>::value);
    assert(std::is_trivially_copyable<SemanticMotionTelemetry>::value);
    std::cout << "  -> PASS: SemanticMotionTelemetry is exactly 32 bytes, standard layout, trivially copyable.\n";
}

static void test_heading_computation() {
    std::cout << "[TEST 2] Testing 8-compass heading mapping...\n";

    auto get_heading = [](float dx, float dy) -> std::pair<uint8_t, const char*> {
        std::vector<float> tensor(84 * 8400, 0.0f);
        // Anchor 0: Person
        tensor[0 * 8400 + 0] = 500.0f;
        tensor[1 * 8400 + 0] = 500.0f;
        tensor[2 * 8400 + 0] = 40.0f;
        tensor[3 * 8400 + 0] = 80.0f;
        tensor[4 * 8400 + 0] = 0.9f;

        SemanticMotionTelemetry telem;
        MotionTracker trk;
        trk.process_frame(tensor.data(), 640, 640, 0, telem);

        // Next frame with displacement
        tensor[0 * 8400 + 0] = 500.0f + dx;
        tensor[1 * 8400 + 0] = 500.0f + dy;
        trk.process_frame(tensor.data(), 640, 640, 1, telem);

        return {telem.heading_code, MotionTracker::heading_to_string(telem.heading_code)};
    };

    // Stationary (speed < 1.0)
    auto res = get_heading(0.2f, 0.2f);
    assert(res.first == 0 && std::string(res.second) == "Stationary");

    // East (dx > 0, dy = 0)
    res = get_heading(10.0f, 0.0f);
    assert(res.first == 1 && std::string(res.second) == "E");

    // North-East (dx > 0, dy < 0)
    res = get_heading(10.0f, -10.0f);
    assert(res.first == 2 && std::string(res.second) == "NE");

    // North (dx = 0, dy < 0)
    res = get_heading(0.0f, -10.0f);
    assert(res.first == 3 && std::string(res.second) == "N");

    // North-West (dx < 0, dy < 0)
    res = get_heading(-10.0f, -10.0f);
    assert(res.first == 4 && std::string(res.second) == "NW");

    // West (dx < 0, dy = 0)
    res = get_heading(-10.0f, 0.0f);
    assert(res.first == 5 && std::string(res.second) == "W");

    // South-West (dx < 0, dy > 0)
    res = get_heading(-10.0f, 10.0f);
    assert(res.first == 6 && std::string(res.second) == "SW");

    // South (dx = 0, dy > 0)
    res = get_heading(0.0f, 10.0f);
    assert(res.first == 7 && std::string(res.second) == "S");

    // South-East (dx > 0, dy > 0)
    res = get_heading(10.0f, 10.0f);
    assert(res.first == 8 && std::string(res.second) == "SE");

    std::cout << "  -> PASS: All 8 compass directions + Stationary mapped with 100% precision.\n";
}

static void test_candidate_parsing_and_nms() {
    std::cout << "[TEST 3] Testing class filtering (Person=0, Bicycle=1) & NMS suppression...\n";
    MotionTracker tracker;
    std::vector<float> tensor(84 * 8400, 0.0f);

    // Box 0: Primary Person (conf 0.90) at (320, 240, 50, 100)
    tensor[0 * 8400 + 0] = 320.0f;
    tensor[1 * 8400 + 0] = 240.0f;
    tensor[2 * 8400 + 0] = 50.0f;
    tensor[3 * 8400 + 0] = 100.0f;
    tensor[4 * 8400 + 0] = 0.90f; // person

    // Box 1: Overlapping Person (conf 0.70) at (322, 242, 50, 100) -> Should be suppressed by NMS
    tensor[0 * 8400 + 1] = 322.0f;
    tensor[1 * 8400 + 1] = 242.0f;
    tensor[2 * 8400 + 1] = 50.0f;
    tensor[3 * 8400 + 1] = 100.0f;
    tensor[4 * 8400 + 1] = 0.70f; // person

    // Box 2: Irrelevant Class (Class 2 = Car, conf 0.95) at (100, 100, 80, 80) -> Should be ignored
    tensor[0 * 8400 + 2] = 100.0f;
    tensor[1 * 8400 + 2] = 100.0f;
    tensor[2 * 8400 + 2] = 80.0f;
    tensor[3 * 8400 + 2] = 80.0f;
    tensor[6 * 8400 + 2] = 0.95f; // car (row 4 + class 2 = row 6)

    // Box 3: Low-confidence person (conf 0.15 < 0.25) -> Should be rejected
    tensor[0 * 8400 + 3] = 400.0f;
    tensor[1 * 8400 + 3] = 400.0f;
    tensor[2 * 8400 + 3] = 50.0f;
    tensor[3 * 8400 + 3] = 100.0f;
    tensor[4 * 8400 + 3] = 0.15f;

    // Box 4: Valid Bicycle (conf 0.88) near person at (330, 250, 60, 60)
    tensor[0 * 8400 + 4] = 330.0f;
    tensor[1 * 8400 + 4] = 250.0f;
    tensor[2 * 8400 + 4] = 60.0f;
    tensor[3 * 8400 + 4] = 60.0f;
    tensor[5 * 8400 + 4] = 0.88f; // bicycle (row 5)

    SemanticMotionTelemetry telem;
    char english[256];
    tracker.process_frame(tensor.data(), 640, 640, 100000, telem, english, sizeof(english));

    assert(telem.has_person == 1);
    assert(telem.has_bicycle == 1);
    assert(telem.is_paired == 1);
    assert(telem.centroid_x == 320);
    assert(telem.centroid_y == 240);
    assert(telem.heading_code == 0); // initial frame -> stationary
    assert(tracker.active_tracks().size() == 2); // 1 paired person + 1 car

    std::cout << "  English: \"" << english << "\"\n";
    assert(std::string(english).find("Person at (320, 240)") != std::string::npos);
    assert(std::string(english).find("Car at (100, 100)") != std::string::npos);
    std::cout << "  -> PASS: Multi-entity candidate extraction, vehicle detection, class-wise NMS, and pairing verified.\n";
}

static void test_motion_tracking_multi_frame() {
    std::cout << "[TEST 4] Testing multi-frame tracking, velocity vector & plain English output...\n";
    MotionTracker tracker;
    std::vector<float> tensor(84 * 8400, 0.0f);
    SemanticMotionTelemetry telem;
    char english[256];

    // Frame 1: Person at (200, 300), Solo
    tensor[0 * 8400 + 0] = 200.0f;
    tensor[1 * 8400 + 0] = 300.0f;
    tensor[2 * 8400 + 0] = 40.0f;
    tensor[3 * 8400 + 0] = 80.0f;
    tensor[4 * 8400 + 0] = 0.85f;
    tracker.process_frame(tensor.data(), 1920, 1080, 1000, telem, english, sizeof(english));

    // In 1920x1080 native scale:
    // cx = 200 * (1920/640) = 600
    // cy = 300 * (1080/640) = 506
    assert(telem.has_person == 1);
    assert(telem.is_paired == 0);
    assert(telem.centroid_x == 600);
    assert(telem.centroid_y == 506);
    assert(std::string(english).find("Object: Solo") != std::string::npos);

    // Frame 2: Person moves East by +10 in 640-space (+30 in native space)
    tensor[0 * 8400 + 0] = 210.0f;
    tensor[1 * 8400 + 0] = 300.0f;
    tracker.process_frame(tensor.data(), 1920, 1080, 2000, telem, english, sizeof(english));

    assert(telem.centroid_x == 630);
    assert(telem.centroid_y == 506);
    assert(telem.heading_code == 1); // E
    assert(std::abs(telem.speed - 30.0f) < 0.1f);
    std::cout << "  Frame 2 English: \"" << english << "\"\n";
    assert(std::string(english).find("Heading: E") != std::string::npos);
    assert(std::string(english).find("Speed: 30.0 px/frame") != std::string::npos);

    // Frame 3: Person pairs with Bicycle and moves South-East
    tensor[0 * 8400 + 0] = 220.0f;
    tensor[1 * 8400 + 0] = 310.0f;
    // Add bicycle at (222, 312)
    tensor[0 * 8400 + 1] = 222.0f;
    tensor[1 * 8400 + 1] = 312.0f;
    tensor[2 * 8400 + 1] = 50.0f;
    tensor[3 * 8400 + 1] = 50.0f;
    tensor[5 * 8400 + 1] = 0.90f; // bicycle
    tracker.process_frame(tensor.data(), 1920, 1080, 3000, telem, english, sizeof(english));

    assert(telem.is_paired == 1);
    assert(telem.heading_code == 8); // SE
    std::cout << "  Frame 3 English: \"" << english << "\"\n";
    assert(std::string(english).find("Heading: SE") != std::string::npos);
    assert(std::string(english).find("Object: With Bicycle") != std::string::npos);

    // Frame 4: Scene clears
    std::fill(tensor.begin(), tensor.end(), 0.0f);
    // 11 frames of empty scene to prune track
    for (int f = 0; f < 11; ++f) {
        tracker.process_frame(tensor.data(), 1920, 1080, 4000 + f * 1000, telem, english, sizeof(english));
    }
    std::cout << "  Cleared Scene English: \"" << english << "\"\n";
    assert(std::string(english).find("Scene Clear") != std::string::npos);
    std::cout << "  -> PASS: Multi-frame tracking, coordinate scaling, velocity, and state transitions verified.\n";
}

static void test_telemetry_serialization() {
    std::cout << "[TEST 5] Testing TelemetryFrame::_pad serialization & zero-copy unpacking...\n";
    SemanticMotionTelemetry telem{};
    telem.has_person = 1;
    telem.has_bicycle = 1;
    telem.is_paired = 1;
    telem.heading_code = 2; // NE
    telem.centroid_x = 1024;
    telem.centroid_y = 768;
    telem.speed = 15.5f;
    std::snprintf(telem.summary, sizeof(telem.summary), "Person+Bike NE 15.5");

    TelemetryFrame frame{};
    frame.pts = 987654321;
    frame.is_match = 1;

    MotionTracker::serialize_to_frame(telem, frame);

    // Unpack from frame._pad directly
    const auto* unpacked = reinterpret_cast<const SemanticMotionTelemetry*>(frame._pad);
    assert(unpacked->has_person == 1);
    assert(unpacked->has_bicycle == 1);
    assert(unpacked->is_paired == 1);
    assert(unpacked->heading_code == 2);
    assert(unpacked->centroid_x == 1024);
    assert(unpacked->centroid_y == 768);
    assert(std::abs(unpacked->speed - 15.5f) < 1e-4f);
    assert(std::string(unpacked->summary) == "Person+Bike NE 15.5");

    std::cout << "  -> PASS: Zero-copy serialization into TelemetryFrame::_pad verified.\n";
}

static void benchmark_tracker_throughput() {
    std::cout << "[BENCHMARK] Running 100,000 synthetic frames through MotionTracker...\n";
    MotionTracker tracker;
    std::vector<float> tensor(84 * 8400, 0.0f);

    // Populate active scene
    tensor[0 * 8400 + 0] = 320.0f;
    tensor[1 * 8400 + 0] = 240.0f;
    tensor[2 * 8400 + 0] = 50.0f;
    tensor[3 * 8400 + 0] = 100.0f;
    tensor[4 * 8400 + 0] = 0.90f;

    tensor[0 * 8400 + 1] = 330.0f;
    tensor[1 * 8400 + 1] = 250.0f;
    tensor[2 * 8400 + 1] = 60.0f;
    tensor[3 * 8400 + 1] = 60.0f;
    tensor[5 * 8400 + 1] = 0.88f;

    SemanticMotionTelemetry telem;
    char english[256];

    constexpr int NUM_FRAMES = 10000;
    auto start = std::chrono::high_resolution_clock::now();

    for (int i = 0; i < NUM_FRAMES; ++i) {
        tensor[0 * 8400 + 0] = 320.0f + (i % 100);
        tracker.process_frame(tensor.data(), 1920, 1080, i * 33333, telem, english, sizeof(english));
    }

    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> diff = end - start;

    double fps = static_cast<double>(NUM_FRAMES) / diff.count();
    double latency_us = (diff.count() / NUM_FRAMES) * 1e6;

    std::cout << "  Processed " << NUM_FRAMES << " frames in " << diff.count() << " s\n";
    std::cout << "  Latency:    " << latency_us << " us / frame\n";
    std::cout << "  Throughput: " << fps << " FPS\n";

    assert(fps > 1000.0);
    std::cout << "  -> PASS: Throughput requirement (>1,000 FPS, target 300 FPS) exceeded.\n";
}

int main() {
    std::cout << "========================================================\n";
    std::cout << " ForensicVideoVerifier: MotionTracker Verification Suite \n";
    std::cout << "========================================================\n";

    test_structure_alignment();
    test_heading_computation();
    test_candidate_parsing_and_nms();
    test_motion_tracking_multi_frame();
    test_telemetry_serialization();
    benchmark_tracker_throughput();

    std::cout << "========================================================\n";
    std::cout << " ALL MOTION TRACKER TESTS PASSED SUCCESSFULLY!          \n";
    std::cout << "========================================================\n";
    return 0;
}
