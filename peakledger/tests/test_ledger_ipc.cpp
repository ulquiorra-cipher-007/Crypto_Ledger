#include "common.hpp"
#include "ring_buffer.hpp"
#include "ledger_db.hpp"
#include <iostream>
#include <cassert>
#include <thread>

int main() {
    std::cout << "[+] Testing SQLite Ledger..." << std::endl;
    Forensic::LedgerDB db("/tmp/test_forensic_ledger.db");

    Forensic::VideoMetadata meta;
    meta.video_id = "TEST_VID_001";
    meta.source_uri = "/evidence/sample_pristine.mp4";
    meta.duration_us = 10000000; // 10s
    meta.file_size = 45000000;
    meta.creation_date = "2026-09-08T12:00:00Z";
    meta.mop = "BodyCam-Axon-X4";
    meta.root_hash = "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0";

    assert(db.store_metadata(meta));

    std::vector<Forensic::FrameHashRecord> records;
    for (int64_t pts = 0; pts < 100; ++pts) {
        Forensic::FrameHashRecord rec;
        rec.pts = pts * 33333;
        for (size_t b = 0; b < Forensic::SHA256_DIGEST_LENGTH; ++b) {
            rec.hash[b] = static_cast<uint8_t>((pts + b) & 0xFF);
        }
        rec.hex_hash = Forensic::to_hex_string(rec.hash);
        records.push_back(rec);
    }
    assert(db.store_frame_ledger(meta.video_id, records));

    auto loaded_meta = db.get_metadata("TEST_VID_001");
    assert(loaded_meta.has_value());
    assert(loaded_meta->video_id == "TEST_VID_001");
    assert(loaded_meta->root_hash == meta.root_hash);

    auto baseline = db.load_baseline_hashes("TEST_VID_001");
    assert(baseline.size() == 100);
    assert(baseline[0] == records[0].hash);
    std::cout << "    [PASSED] SQLite Ledger transaction and query logic verified." << std::endl;

    std::cout << "[+] Testing POSIX IPC Ring Buffer with Atomic Release/Acquire..." << std::endl;
    Forensic::ShmProducer producer("/test_forensic_shm", true);
    auto* raw_shm = producer.raw();
    assert(raw_shm != nullptr);
    assert(raw_shm->magic == 0x4653484D);

    for (uint64_t i = 0; i < 500; ++i) {
        Forensic::TelemetryFrame frame;
        frame.pts = i * 33333;
        frame.frame_index = i;
        frame.is_match = (i == 42) ? 0 : 1;
        frame.residual_energy = (i == 42) ? 98765 : 12;
        frame.timestamp_ns = 1750000000000ULL + i;
        std::memset(frame.grid_signature, static_cast<uint8_t>(i & 0xFF), Forensic::GRID_CELLS);
        producer.push_telemetry(frame);
    }

    uint64_t write_seq = raw_shm->write_seq.load(std::memory_order_acquire);
    assert(write_seq == 500);
    assert(raw_shm->total_frames_processed.load() == 500);
    assert(raw_shm->total_frames_matched.load() == 499);
    assert(raw_shm->total_frames_tampered.load() == 1);

    // Verify recent slot
    size_t last_slot = 499 % Forensic::RING_BUFFER_CAPACITY;
    assert(raw_shm->slots[last_slot].frame_index == 499);
    assert(raw_shm->slots[last_slot].grid_signature[0] == (499 & 0xFF));

    producer.set_tamper_flag(42 * 33333, "/evidence/tamper_frame_1399986.jpg");
    assert(raw_shm->is_tampered.load() == 1);
    assert(raw_shm->tamper_pts.load() == 42 * 33333);
    assert(std::string(raw_shm->tamper_image_path) == "/evidence/tamper_frame_1399986.jpg");

    std::cout << "    [PASSED] POSIX IPC Ring Buffer lock-free telemetry verified." << std::endl;
    return 0;
}
