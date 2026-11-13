#include "ring_buffer.hpp"
#include <iostream>
#include <cassert>
#include <thread>
#include <atomic>
#include <vector>

int main() {
    const std::string shm_test_name = "/forensic_shm_unit_test";
    std::cout << "[+] Initializing POSIX IPC Ring Buffer Producer on " << shm_test_name << "..." << std::endl;

    // Verify compile-time layout invariants
    static_assert(sizeof(Forensic::TelemetryFrame) == 640, "Size mismatch");
    static_assert(sizeof(Forensic::ForensicSharedMemory) == 164608, "Size mismatch");

    Forensic::ShmProducer producer(shm_test_name, true);
    auto* raw = producer.raw();
    assert(raw != nullptr);
    assert(raw->magic == 0x4653484D);
    assert(raw->capacity == Forensic::RING_BUFFER_CAPACITY);
    assert(raw->write_seq.load() == 0);
    std::cout << "    [OK] Header magic (0x4653484D), capacity (256), and alignment verified." << std::endl;

    Forensic::ShmConsumer consumer(shm_test_name);
    assert(consumer.raw() != nullptr);
    assert(consumer.raw()->magic == 0x4653484D);
    std::cout << "    [OK] Consumer mapped shared memory successfully." << std::endl;

    // Test 1: Real-time pacing (consumer tracks producer without drop)
    const uint64_t paced_frames = 200;
    uint64_t consumer_seq = 0;
    std::vector<Forensic::TelemetryFrame> polled;
    polled.reserve(paced_frames);

    for (uint64_t i = 0; i < paced_frames; ++i) {
        Forensic::TelemetryFrame frame{};
        frame.pts = static_cast<int64_t>(i * 33333);
        frame.frame_index = i;
        frame.is_match = (i == 42) ? 0 : 1;
        frame.residual_energy = (i == 42) ? 99999 : 50;
        frame.timestamp_ns = 1750000000000ULL + i;
        std::memset(frame.grid_signature, static_cast<uint8_t>(i & 0xFF), Forensic::GRID_CELLS);
        producer.push_telemetry(frame);

        Forensic::TelemetryFrame polled_frame{};
        if (consumer.poll_latest(polled_frame, consumer_seq)) {
            polled.push_back(polled_frame);
        }
    }

    assert(polled.size() == paced_frames);
    assert(polled[42].is_match == 0);
    assert(polled[42].residual_energy == 99999);
    assert(polled[42].grid_signature[0] == (42 & 0xFF));
    std::cout << "    [OK] Real-time stream test: 200/200 frames polled losslessly." << std::endl;

    // Test 2: Ring buffer overwrite / lapping protection test
    // Push 500 frames into 256-slot ring without polling
    for (uint64_t i = 200; i < 700; ++i) {
        Forensic::TelemetryFrame frame{};
        frame.pts = static_cast<int64_t>(i * 33333);
        frame.frame_index = i;
        frame.is_match = 1;
        producer.push_telemetry(frame);
    }
    // Consumer should safely fast-forward and poll the newest 256 frames
    uint64_t lapped_count = 0;
    Forensic::TelemetryFrame last_frame{};
    while (consumer.poll_latest(last_frame, consumer_seq)) {
        lapped_count++;
    }
    assert(lapped_count == Forensic::RING_BUFFER_CAPACITY);
    assert(last_frame.frame_index == 699);
    std::cout << "    [OK] Overwrite protection test: lapped consumer safely retrieved " << lapped_count << " latest frames." << std::endl;

    // Test 3: Tamper flag propagation
    producer.set_tamper_flag(42 * 33333, "/evidence/tamper_frame_1399986.jpg");
    int64_t t_pts = 0;
    std::string t_path;
    assert(consumer.is_tampered(t_pts, t_path));
    assert(t_pts == 42 * 33333);
    assert(t_path == "/evidence/tamper_frame_1399986.jpg");
    std::cout << "    [OK] Tamper trigger propagation verified (PTS: " << t_pts << ", Path: " << t_path << ")." << std::endl;

    // Test 4: Completion flag propagation
    producer.set_completed();
    assert(consumer.is_completed());
    std::cout << "    [OK] Stream completion state propagation verified." << std::endl;

    // Clean up unit test SHM
    shm_unlink(shm_test_name.c_str());

    std::cout << "[+] STEP 2 UNIT TEST PASSED." << std::endl;
    return 0;
}
