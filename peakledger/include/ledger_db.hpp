#pragma once

#include "common.hpp"
#include <sqlite3.h>
#include <string>
#include <vector>
#include <unordered_map>
#include <memory>
#include <optional>

namespace Forensic {

class LedgerDB {
public:
    explicit LedgerDB(const std::string& db_path = "ledger.db");
    ~LedgerDB();

    LedgerDB(const LedgerDB&) = delete;
    LedgerDB& operator=(const LedgerDB&) = delete;

    void init_schema();
    
    // Ingestion Mode API
    bool store_metadata(const VideoMetadata& meta);
    bool store_frame_ledger(const std::string& video_id, const std::vector<FrameHashRecord>& records);
    bool store_vector_blockchain(const std::string& video_id, const std::vector<VectorBlock>& blocks);
    bool store_semantic_blockchain(const std::string& video_id, const std::vector<SemanticBlock>& blocks);

    // Layer 2 Content-Addressable Storage (CAS) API
    bool store_cas_record(const FrameCasRecord& rec);
    bool store_cas_records(const std::string& video_id, const std::vector<FrameCasRecord>& recs);
    std::optional<FrameCasRecord> get_cas_record(const std::string& packet_hash);
    std::optional<FrameCasRecord> get_cas_record_by_index(const std::string& video_id, uint64_t leaf_index);
    std::optional<FrameCasRecord> get_cas_record_by_pts(const std::string& video_id, int64_t pts);
    std::vector<FrameCasRecord> get_cas_records_in_range(const std::string& video_id, uint64_t leaf_start, uint64_t leaf_end);

    // Layer 2 Forensic Intelligence & Attribute Metadata API (forensic_frame_metadata)
    bool store_forensic_records(const std::string& video_id, const std::vector<ForensicEntityRecord>& records);
    std::vector<ForensicEntityRecord> get_forensic_records_by_pts(const std::string& video_id, int64_t pts);
    std::vector<ForensicEntityRecord> get_forensic_records_by_packet_hash(const std::string& packet_hash);
    std::vector<ForensicEntityRecord> get_forensic_records_in_range(const std::string& video_id, int64_t pts_start, int64_t pts_end);
    std::vector<ForensicEntityRecord> get_forensic_records_by_track(const std::string& video_id, int track_id);
    std::vector<ForensicEntityRecord> get_forensic_records_by_plate(const std::string& video_id, const std::string& plate_text);

    // Verification Mode API
    std::optional<VideoMetadata> get_metadata(const std::string& video_id);
    std::unordered_map<int64_t, HashDigest> load_baseline_hashes(const std::string& video_id);
    std::vector<HashDigest> load_baseline_leaves(const std::string& video_id);
    std::vector<FrameHashRecord> load_ordered_records(const std::string& video_id);
    std::vector<VectorBlock> load_vector_blockchain(const std::string& video_id);
    std::vector<SemanticBlock> load_semantic_blockchain(const std::string& video_id);
    bool verify_vector_blockchain(const std::string& video_id, size_t& out_total_blocks, std::string& out_tip_hash);
    bool verify_semantic_blockchain(const std::string& video_id, size_t& out_total_blocks, std::string& out_tip_hash);
    std::vector<std::string> list_video_ids();
    bool has_video(const std::string& video_id);
    bool delete_video(const std::string& video_id);
    std::string get_baseline_semantics(const std::string& video_id, int64_t pts);

private:
    sqlite3* db_{nullptr};
    std::string db_path_;

    void execute_simple(const std::string& sql);
};

} // namespace Forensic
