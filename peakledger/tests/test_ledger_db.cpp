#include "ledger_db.hpp"
#include "crypto_merkle.hpp"
#include <iostream>
#include <cassert>
#include <chrono>
#include <cstdio>

int main() {
    const std::string test_db = "/tmp/forensic_ledger_unit_test.db";
    std::remove(test_db.c_str());

    std::cout << "[+] Verifying SQLite3 Forensic Ledger on " << test_db << "..." << std::endl;
    Forensic::LedgerDB db(test_db);

    // 1. Metadata insertion
    Forensic::VideoMetadata meta;
    meta.video_id = "CASE_2026_0908_PRISTINE";
    meta.source_uri = "/evidence/bodycam_axon_x4_raw.mp4";
    meta.duration_us = 300000000; // 300 seconds (5 mins)
    meta.file_size = 1073741824;  // 1 GB
    meta.creation_date = "2026-09-08T20:15:00Z";
    meta.mop = "Axon-Body4-HWRev3";
    meta.root_hash = "3e23e8160039594a33894f6564e1b1348bbd7a0088d42c4acb73eeaed59c009d";

    assert(db.store_metadata(meta));
    std::cout << "    [OK] VideoMetadata successfully stored." << std::endl;

    // 2. High-volume frame ingestion (10,000 frames)
    const size_t num_frames = 10000;
    std::vector<Forensic::FrameHashRecord> records;
    records.reserve(num_frames);

    for (size_t i = 0; i < num_frames; ++i) {
        Forensic::FrameHashRecord rec;
        rec.pts = static_cast<int64_t>(i * 33333);
        for (size_t b = 0; b < Forensic::SHA256_DIGEST_LENGTH; ++b) {
            rec.hash[b] = static_cast<uint8_t>((i + b * 17) & 0xFF);
        }
        rec.hex_hash = Forensic::to_hex_string(rec.hash);
        records.push_back(std::move(rec));
    }

    auto t0 = std::chrono::high_resolution_clock::now();
    bool stored = db.store_frame_ledger(meta.video_id, records);
    auto t1 = std::chrono::high_resolution_clock::now();
    assert(stored);

    double commit_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    double records_per_sec = (num_frames / commit_ms) * 1000.0;
    std::cout << "    [BENCHMARK] Transaction commit: " << num_frames << " frames in " 
              << commit_ms << " ms (" << records_per_sec << " records/sec)" << std::endl;

    // 3. Verification Mode Retrieval
    assert(db.has_video("CASE_2026_0908_PRISTINE"));
    auto fetched_meta = db.get_metadata("CASE_2026_0908_PRISTINE");
    assert(fetched_meta.has_value());
    assert(fetched_meta->source_uri == meta.source_uri);
    assert(fetched_meta->root_hash == meta.root_hash);
    assert(fetched_meta->mop == meta.mop);
    assert(fetched_meta->file_size == meta.file_size);
    std::cout << "    [OK] Retrieved metadata bit-identically matches original." << std::endl;

    // 4. Baseline hash lookup map
    auto t_map_0 = std::chrono::high_resolution_clock::now();
    auto baseline_map = db.load_baseline_hashes("CASE_2026_0908_PRISTINE");
    auto t_map_1 = std::chrono::high_resolution_clock::now();
    double query_ms = std::chrono::duration<double, std::milli>(t_map_1 - t_map_0).count();

    assert(baseline_map.size() == num_frames);
    for (size_t i = 0; i < num_frames; i += 500) {
        int64_t query_pts = static_cast<int64_t>(i * 33333);
        auto it = baseline_map.find(query_pts);
        assert(it != baseline_map.end());
        assert(it->second == records[i].hash);
    }
    std::cout << "    [OK] Baseline hash table loaded in " << query_ms << " ms (" << baseline_map.size() << " frames verified)." << std::endl;

    // 4b. Vector Frames Blockchain Test
    std::cout << "[+] Verifying Vector Frames Blockchain creation and cryptographic audit..." << std::endl;
    std::vector<Forensic::VectorBlock> vblocks;
    std::string v_prev(64, '0');
    for (size_t i = 0; i < 50; ++i) {
        Forensic::VectorBlock vb;
        vb.block_index = i;
        vb.video_id = meta.video_id;
        vb.pts = i * 33333;
        vb.frame_index = i;
        vb.grid_signature.fill(static_cast<uint8_t>(i % 255));
        vb.frame_hash = records[i].hex_hash;
        vb.prev_block_hash = v_prev;
        std::string raw = std::to_string(vb.block_index) + ":" + vb.video_id + ":" +
                          std::to_string(vb.pts) + ":" + vb.frame_hash + ":" +
                          Forensic::to_hex_string(vb.grid_signature.data(), vb.grid_signature.size()) + ":" + vb.prev_block_hash;
        vb.block_hash = Forensic::to_hex_string(Forensic::FrameHasher::compute_sha256(reinterpret_cast<const uint8_t*>(raw.data()), raw.size()));
        v_prev = vb.block_hash;
        vb.timestamp = "2026-09-08T20:15:00Z";
        vblocks.push_back(vb);
    }
    assert(db.store_vector_blockchain(meta.video_id, vblocks));

    size_t v_count = 0;
    std::string v_tip;
    assert(db.verify_vector_blockchain(meta.video_id, v_count, v_tip));
    assert(v_count == 50);
    assert(v_tip == v_prev);
    std::cout << "    [OK] Vector Frames Blockchain: 50 blocks verified (Tip: " << v_tip.substr(0, 16) << "...)" << std::endl;

    // 4c. Semantic Evidence Blockchain Test
    std::cout << "[+] Verifying Semantic Evidence Blockchain creation and cryptographic audit..." << std::endl;
    std::vector<Forensic::SemanticBlock> sblocks;
    std::string s_prev(64, '0');
    for (size_t i = 0; i < 20; ++i) {
        Forensic::SemanticBlock sb;
        sb.block_index = i;
        sb.video_id = meta.video_id;
        sb.window_idx = i + 1;
        sb.entity_idx = 0;
        sb.start_pts = i * 200000;
        sb.end_pts = (i + 1) * 200000;
        sb.boustro_cx = 10;
        sb.boustro_cy = 0;
        sb.boustro_s1d = 10;
        sb.centroid_x = 640;
        sb.centroid_y = 50;
        sb.speed = 9.2f;
        sb.heading_code = 1; // E
        sb.entity_label = "Person moving N to E (with Bicycle)";
        sb.evidence_payload = "Person moving N to E (with Bicycle) at (640, 50) [Macro-Grid: (10, 0)] | Heading: E | Speed: 9.2 px/f";
        sb.prev_block_hash = s_prev;
        std::string raw = std::to_string(sb.block_index) + ":" + sb.video_id + ":" +
                          std::to_string(sb.window_idx) + ":" + std::to_string(sb.entity_idx) + ":" +
                          std::to_string(sb.start_pts) + ":" + std::to_string(sb.end_pts) + ":" +
                          sb.entity_label + ":" + sb.evidence_payload + ":" + sb.prev_block_hash;
        sb.block_hash = Forensic::to_hex_string(Forensic::FrameHasher::compute_sha256(reinterpret_cast<const uint8_t*>(raw.data()), raw.size()));
        s_prev = sb.block_hash;
        sb.timestamp = "2026-09-08T20:15:00Z";
        sblocks.push_back(sb);
    }
    assert(db.store_semantic_blockchain(meta.video_id, sblocks));

    size_t s_count = 0;
    std::string s_tip;
    assert(db.verify_semantic_blockchain(meta.video_id, s_count, s_tip));
    assert(s_count == 20);
    assert(s_tip == s_prev);
    std::cout << "    [OK] Semantic Evidence Blockchain: 20 blocks verified (Tip: " << s_tip.substr(0, 16) << "...)" << std::endl;

    std::string recovered = db.get_baseline_semantics(meta.video_id, 250000);
    assert(!recovered.empty());
    assert(recovered.find("Person moving N to E (with Bicycle)") != std::string::npos);
    std::cout << "    [OK] Recovered Ground-Truth: " << recovered << std::endl;

    // 4d. Layer 2 CAS Metadata Storage & Query Test
    std::cout << "[+] Verifying Layer 2 CAS Metadata storage and spatial retrieval..." << std::endl;
    std::vector<Forensic::FrameCasRecord> cas_batch;
    for (size_t i = 0; i < 100; ++i) {
        Forensic::FrameCasRecord cr;
        cr.packet_hash = records[i].hex_hash;
        cr.leaf_index = i;
        cr.video_id = meta.video_id;
        cr.pts = static_cast<int64_t>(i * 33333);
        cr.dts = cr.pts;
        cr.color_grid.fill(static_cast<uint8_t>((i * 3) & 0xFF));

        Forensic::QuantizedBBox qb;
        qb.x1 = 200; qb.y1 = 300; qb.x2 = 400; qb.y2 = 700;
        qb.class_id = 0; // Person
        qb.confidence_q8 = 230;
        cr.detections.push_back(qb);
        cr.semantic_summary = "Person detected with 0.90 confidence";
        cas_batch.push_back(std::move(cr));
    }
    assert(db.store_cas_records(meta.video_id, cas_batch));

    auto cas_single = db.get_cas_record(records[5].hex_hash);
    assert(cas_single.has_value());
    assert(cas_single->leaf_index == 5);
    assert(cas_single->detections.size() == 1);
    assert(cas_single->detections[0].class_id == 0);
    assert(cas_single->detections[0].x1 == 200);

    auto cas_range = db.get_cas_records_in_range(meta.video_id, 10, 20);
    assert(cas_range.size() == 11);
    assert(cas_range[0].leaf_index == 10);
    assert(cas_range.back().leaf_index == 20);

    auto loaded_leaves = db.load_baseline_leaves(meta.video_id);
    assert(loaded_leaves.size() >= 100);
    assert(loaded_leaves[0] == records[0].hash);
    std::cout << "    [OK] CAS Metadata: 100 records committed, point and range queries verified." << std::endl;

    // 5. Cascade deletion test
    assert(db.delete_video("CASE_2026_0908_PRISTINE"));
    assert(!db.has_video("CASE_2026_0908_PRISTINE"));
    auto empty_map = db.load_baseline_hashes("CASE_2026_0908_PRISTINE");
    assert(empty_map.empty());
    auto empty_cas = db.get_cas_records_in_range("CASE_2026_0908_PRISTINE", 0, 100);
    assert(empty_cas.empty());
    std::cout << "    [OK] Foreign key cascade deletion verified." << std::endl;

    std::remove(test_db.c_str());
    std::cout << "[+] STEP 5 UNIT TEST PASSED." << std::endl;
    return 0;
}
