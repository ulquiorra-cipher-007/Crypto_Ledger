#include "ledger_db.hpp"
#include "crypto_merkle.hpp"
#include <stdexcept>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <cstring>

namespace Forensic {

LedgerDB::LedgerDB(const std::string& db_path) : db_path_(db_path) {
    int rc = sqlite3_open(db_path_.c_str(), &db_);
    if (rc != SQLITE_OK) {
        std::string err = sqlite3_errmsg(db_);
        if (db_) sqlite3_close(db_);
        throw std::runtime_error("Failed to open SQLite ledger: " + err);
    }
    init_schema();
}

LedgerDB::~LedgerDB() {
    if (db_) {
        sqlite3_close(db_);
        db_ = nullptr;
    }
}

void LedgerDB::execute_simple(const std::string& sql) {
    char* err_msg = nullptr;
    int rc = sqlite3_exec(db_, sql.c_str(), nullptr, nullptr, &err_msg);
    if (rc != SQLITE_OK) {
        std::string err = err_msg ? err_msg : "Unknown SQLite error";
        sqlite3_free(err_msg);
        throw std::runtime_error("SQLite exec error: " + err + " [SQL: " + sql + "]");
    }
}

void LedgerDB::init_schema() {
    execute_simple("PRAGMA journal_mode=WAL;");
    execute_simple("PRAGMA synchronous=NORMAL;");
    execute_simple("PRAGMA busy_timeout=5000;");
    execute_simple("PRAGMA foreign_keys=ON;");

    const char* schema_sql = R"(
        CREATE TABLE IF NOT EXISTS video_metadata (
            video_id TEXT PRIMARY KEY,
            source_uri TEXT NOT NULL,
            duration_us INTEGER NOT NULL,
            file_size INTEGER NOT NULL,
            creation_date TEXT NOT NULL,
            mop TEXT NOT NULL,
            root_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS frame_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,
            pts INTEGER NOT NULL,
            frame_hash TEXT NOT NULL,
            FOREIGN KEY (video_id) REFERENCES video_metadata(video_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_frame_lookup ON frame_ledger(video_id, pts);

        CREATE TABLE IF NOT EXISTS frame_cas_metadata (
            packet_hash TEXT PRIMARY KEY,
            leaf_index INTEGER NOT NULL,
            video_id TEXT NOT NULL,
            pts INTEGER NOT NULL,
            dts INTEGER NOT NULL,
            color_grid BLOB NOT NULL,
            detections_blob BLOB,
            semantic_summary TEXT,
            FOREIGN KEY (video_id) REFERENCES video_metadata(video_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_cas_video_leaf ON frame_cas_metadata(video_id, leaf_index);
        CREATE INDEX IF NOT EXISTS idx_cas_video_pts ON frame_cas_metadata(video_id, pts);

        CREATE TABLE IF NOT EXISTS forensic_frame_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            packet_hash TEXT NOT NULL,
            video_id TEXT NOT NULL,
            leaf_index INTEGER NOT NULL,
            pts INTEGER NOT NULL,
            dts INTEGER NOT NULL,
            track_id INTEGER,
            entity_type TEXT NOT NULL,
            bbox_x1 REAL,
            bbox_y1 REAL,
            bbox_x2 REAL,
            bbox_y2 REAL,
            confidence REAL,
            face_embedding BLOB,
            plate_text TEXT,
            signal_state INTEGER,
            signal_timer INTEGER,
            dominant_colors BLOB,
            ref_crop_blob BLOB,
            FOREIGN KEY (video_id) REFERENCES video_metadata(video_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_metadata_pts ON forensic_frame_metadata(pts);
        CREATE INDEX IF NOT EXISTS idx_metadata_plate ON forensic_frame_metadata(plate_text);
        CREATE INDEX IF NOT EXISTS idx_metadata_track ON forensic_frame_metadata(track_id);
        CREATE INDEX IF NOT EXISTS idx_metadata_packet ON forensic_frame_metadata(packet_hash);
        CREATE INDEX IF NOT EXISTS idx_metadata_video_pts ON forensic_frame_metadata(video_id, pts);

        CREATE TABLE IF NOT EXISTS vector_frames_blockchain (
            block_index INTEGER NOT NULL,
            video_id TEXT NOT NULL,
            pts INTEGER NOT NULL,
            frame_index INTEGER NOT NULL,
            grid_signature BLOB NOT NULL,
            frame_hash TEXT NOT NULL,
            prev_block_hash TEXT NOT NULL,
            block_hash TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            PRIMARY KEY (video_id, block_index),
            FOREIGN KEY (video_id) REFERENCES video_metadata(video_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_vec_blockchain_pts ON vector_frames_blockchain(video_id, pts);

        CREATE TABLE IF NOT EXISTS semantic_evidence_blockchain (
            block_index INTEGER NOT NULL,
            video_id TEXT NOT NULL,
            window_idx INTEGER NOT NULL,
            entity_idx INTEGER NOT NULL DEFAULT 0,
            start_pts INTEGER NOT NULL,
            end_pts INTEGER NOT NULL,
            boustro_cx INTEGER NOT NULL,
            boustro_cy INTEGER NOT NULL,
            boustro_s1d INTEGER NOT NULL,
            centroid_x INTEGER NOT NULL,
            centroid_y INTEGER NOT NULL,
            speed REAL NOT NULL,
            heading_code INTEGER NOT NULL,
            entity_label TEXT NOT NULL,
            evidence_payload TEXT NOT NULL,
            prev_block_hash TEXT NOT NULL,
            block_hash TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            PRIMARY KEY (video_id, block_index),
            FOREIGN KEY (video_id) REFERENCES video_metadata(video_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_sem_blockchain_lookup ON semantic_evidence_blockchain(video_id, start_pts, end_pts, entity_idx);

        CREATE TABLE IF NOT EXISTS semantic_sliding_window (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,
            window_idx INTEGER NOT NULL,
            entity_idx INTEGER NOT NULL DEFAULT 0,
            start_pts INTEGER NOT NULL,
            end_pts INTEGER NOT NULL,
            token_5bit INTEGER NOT NULL,
            boustro_cx INTEGER NOT NULL,
            boustro_cy INTEGER NOT NULL,
            boustro_s1d INTEGER NOT NULL,
            centroid_x INTEGER NOT NULL,
            centroid_y INTEGER NOT NULL,
            speed REAL NOT NULL,
            entity_label TEXT NOT NULL DEFAULT '',
            english_translation TEXT NOT NULL,
            FOREIGN KEY (video_id) REFERENCES video_metadata(video_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_boustro_window ON semantic_sliding_window(video_id, start_pts, end_pts, entity_idx);
    )";

    execute_simple(schema_sql);
    char* err_msg = nullptr;
    sqlite3_exec(db_, "ALTER TABLE semantic_sliding_window ADD COLUMN entity_idx INTEGER NOT NULL DEFAULT 0;", nullptr, nullptr, &err_msg);
    if (err_msg) sqlite3_free(err_msg);
    err_msg = nullptr;
    sqlite3_exec(db_, "ALTER TABLE semantic_sliding_window ADD COLUMN entity_label TEXT NOT NULL DEFAULT '';", nullptr, nullptr, &err_msg);
    if (err_msg) sqlite3_free(err_msg);
}

bool LedgerDB::store_metadata(const VideoMetadata& meta) {
    const char* sql = R"(
        INSERT OR REPLACE INTO video_metadata 
        (video_id, source_uri, duration_us, file_size, creation_date, mop, root_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    )";

    sqlite3_stmt* stmt = nullptr;
    int rc = sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr);
    if (rc != SQLITE_OK) {
        std::cerr << "[LedgerDB] Prepare store_metadata failed: " << sqlite3_errmsg(db_) << std::endl;
        return false;
    }

    sqlite3_bind_text(stmt, 1, meta.video_id.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, meta.source_uri.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_int64(stmt, 3, meta.duration_us);
    sqlite3_bind_int64(stmt, 4, meta.file_size);
    sqlite3_bind_text(stmt, 5, meta.creation_date.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 6, meta.mop.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 7, meta.root_hash.c_str(), -1, SQLITE_STATIC);

    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    return (rc == SQLITE_DONE);
}

bool LedgerDB::store_frame_ledger(const std::string& video_id, const std::vector<FrameHashRecord>& records) {
    if (records.empty()) return true;

    execute_simple("BEGIN TRANSACTION;");

    const char* sql = "INSERT INTO frame_ledger (video_id, pts, frame_hash) VALUES (?, ?, ?);";
    sqlite3_stmt* stmt = nullptr;
    int rc = sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr);
    if (rc != SQLITE_OK) {
        std::cerr << "[LedgerDB] Prepare insert frame failed: " << sqlite3_errmsg(db_) << std::endl;
        execute_simple("ROLLBACK;");
        return false;
    }

    for (const auto& rec : records) {
        sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmt, 2, rec.pts);
        
        std::string hex = rec.hex_hash.empty() ? to_hex_string(rec.hash) : rec.hex_hash;
        sqlite3_bind_text(stmt, 3, hex.c_str(), -1, SQLITE_TRANSIENT);

        rc = sqlite3_step(stmt);
        if (rc != SQLITE_DONE) {
            std::cerr << "[LedgerDB] Insert step failed: " << sqlite3_errmsg(db_) << std::endl;
            sqlite3_finalize(stmt);
            execute_simple("ROLLBACK;");
            return false;
        }
        sqlite3_reset(stmt);
    }

    sqlite3_finalize(stmt);
    execute_simple("COMMIT;");
    return true;
}

std::optional<VideoMetadata> LedgerDB::get_metadata(const std::string& video_id) {
    const char* sql = "SELECT video_id, source_uri, duration_us, file_size, creation_date, mop, root_hash FROM video_metadata WHERE video_id = ?;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        return std::nullopt;
    }

    sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);

    std::optional<VideoMetadata> result = std::nullopt;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        VideoMetadata meta;
        meta.video_id = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
        meta.source_uri = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        meta.duration_us = sqlite3_column_int64(stmt, 2);
        meta.file_size = sqlite3_column_int64(stmt, 3);
        meta.creation_date = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4));
        meta.mop = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 5));
        meta.root_hash = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 6));
        result = meta;
    }

    sqlite3_finalize(stmt);
    return result;
}

std::unordered_map<int64_t, HashDigest> LedgerDB::load_baseline_hashes(const std::string& video_id) {
    std::unordered_map<int64_t, HashDigest> map;
    const char* sql = "SELECT pts, frame_hash FROM frame_ledger WHERE video_id = ? ORDER BY pts ASC;";
    sqlite3_stmt* stmt = nullptr;

    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        std::cerr << "[LedgerDB] Failed to query baseline hashes: " << sqlite3_errmsg(db_) << std::endl;
        return map;
    }

    sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int64_t pts = sqlite3_column_int64(stmt, 0);
        const char* hex_ptr = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        if (hex_ptr) {
            map[pts] = hex_to_digest(std::string(hex_ptr));
        }
    }

    sqlite3_finalize(stmt);
    return map;
}

std::vector<FrameHashRecord> LedgerDB::load_ordered_records(const std::string& video_id) {
    std::vector<FrameHashRecord> records;
    const char* sql = "SELECT pts, frame_hash FROM frame_ledger WHERE video_id = ? ORDER BY pts ASC;";
    sqlite3_stmt* stmt = nullptr;

    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        return records;
    }

    sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        FrameHashRecord rec;
        rec.pts = sqlite3_column_int64(stmt, 0);
        const char* hex_ptr = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        if (hex_ptr) {
            rec.hex_hash = hex_ptr;
            rec.hash = hex_to_digest(rec.hex_hash);
        }
        records.push_back(std::move(rec));
    }

    sqlite3_finalize(stmt);
    return records;
}

std::vector<std::string> LedgerDB::list_video_ids() {
    std::vector<std::string> ids;
    const char* sql = "SELECT video_id FROM video_metadata ORDER BY creation_date DESC;";
    sqlite3_stmt* stmt = nullptr;

    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) == SQLITE_OK) {
        while (sqlite3_step(stmt) == SQLITE_ROW) {
            const char* id = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
            if (id) ids.emplace_back(id);
        }
        sqlite3_finalize(stmt);
    }
    return ids;
}

bool LedgerDB::has_video(const std::string& video_id) {
    const char* sql = "SELECT 1 FROM video_metadata WHERE video_id = ? LIMIT 1;";
    sqlite3_stmt* stmt = nullptr;
    bool found = false;

    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) == SQLITE_OK) {
        sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
        if (sqlite3_step(stmt) == SQLITE_ROW) {
            found = true;
        }
        sqlite3_finalize(stmt);
    }
    return found;
}

bool LedgerDB::store_vector_blockchain(const std::string& video_id, const std::vector<VectorBlock>& blocks) {
    if (blocks.empty()) return true;

    execute_simple("BEGIN TRANSACTION;");

    const char* sql = R"(
        INSERT OR REPLACE INTO vector_frames_blockchain
        (block_index, video_id, pts, frame_index, grid_signature, frame_hash, prev_block_hash, block_hash, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    )";

    sqlite3_stmt* stmt = nullptr;
    int rc = sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr);
    if (rc != SQLITE_OK) {
        std::cerr << "[LedgerDB] Prepare store_vector_blockchain failed: " << sqlite3_errmsg(db_) << std::endl;
        execute_simple("ROLLBACK;");
        return false;
    }

    for (const auto& b : blocks) {
        sqlite3_bind_int64(stmt, 1, b.block_index);
        sqlite3_bind_text(stmt, 2, video_id.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmt, 3, b.pts);
        sqlite3_bind_int64(stmt, 4, b.frame_index);
        bool has_color = false;
        for (size_t k = 0; k < COLOR_GRID_BYTES; ++k) {
            if (b.color_grid_signature[k] != 0) {
                has_color = true;
                break;
            }
        }
        if (has_color) {
            sqlite3_bind_blob(stmt, 5, b.color_grid_signature.data(), COLOR_GRID_BYTES, SQLITE_STATIC);
        } else {
            sqlite3_bind_blob(stmt, 5, b.grid_signature.data(), GRID_CELLS, SQLITE_STATIC);
        }
        sqlite3_bind_text(stmt, 6, b.frame_hash.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 7, b.prev_block_hash.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 8, b.block_hash.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 9, b.timestamp.c_str(), -1, SQLITE_STATIC);

        rc = sqlite3_step(stmt);
        if (rc != SQLITE_DONE) {
            std::cerr << "[LedgerDB] Step store_vector_blockchain failed: " << sqlite3_errmsg(db_) << std::endl;
            sqlite3_finalize(stmt);
            execute_simple("ROLLBACK;");
            return false;
        }
        sqlite3_reset(stmt);
    }

    sqlite3_finalize(stmt);
    execute_simple("COMMIT;");
    return true;
}

bool LedgerDB::store_semantic_blockchain(const std::string& video_id, const std::vector<SemanticBlock>& blocks) {
    if (blocks.empty()) return true;

    execute_simple("BEGIN TRANSACTION;");

    const char* sql = R"(
        INSERT OR REPLACE INTO semantic_evidence_blockchain
        (block_index, video_id, window_idx, entity_idx, start_pts, end_pts, boustro_cx, boustro_cy, boustro_s1d, centroid_x, centroid_y, speed, heading_code, entity_label, evidence_payload, prev_block_hash, block_hash, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    )";

    sqlite3_stmt* stmt = nullptr;
    int rc = sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr);
    if (rc != SQLITE_OK) {
        std::cerr << "[LedgerDB] Prepare store_semantic_blockchain failed: " << sqlite3_errmsg(db_) << std::endl;
        execute_simple("ROLLBACK;");
        return false;
    }

    for (const auto& b : blocks) {
        sqlite3_bind_int64(stmt, 1, b.block_index);
        sqlite3_bind_text(stmt, 2, video_id.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmt, 3, b.window_idx);
        sqlite3_bind_int64(stmt, 4, b.entity_idx);
        sqlite3_bind_int64(stmt, 5, b.start_pts);
        sqlite3_bind_int64(stmt, 6, b.end_pts);
        sqlite3_bind_int(stmt, 7, b.boustro_cx);
        sqlite3_bind_int(stmt, 8, b.boustro_cy);
        sqlite3_bind_int(stmt, 9, b.boustro_s1d);
        sqlite3_bind_int(stmt, 10, b.centroid_x);
        sqlite3_bind_int(stmt, 11, b.centroid_y);
        sqlite3_bind_double(stmt, 12, b.speed);
        sqlite3_bind_int(stmt, 13, b.heading_code);
        sqlite3_bind_text(stmt, 14, b.entity_label.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 15, b.evidence_payload.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 16, b.prev_block_hash.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 17, b.block_hash.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 18, b.timestamp.c_str(), -1, SQLITE_STATIC);

        rc = sqlite3_step(stmt);
        if (rc != SQLITE_DONE) {
            std::cerr << "[LedgerDB] Step store_semantic_blockchain failed: " << sqlite3_errmsg(db_) << std::endl;
            sqlite3_finalize(stmt);
            execute_simple("ROLLBACK;");
            return false;
        }
        sqlite3_reset(stmt);
    }
    sqlite3_finalize(stmt);

    // Also populate legacy semantic_sliding_window table for seamless backward compatibility
    const char* sw_sql = R"(
        INSERT OR REPLACE INTO semantic_sliding_window
        (video_id, window_idx, entity_idx, start_pts, end_pts, token_5bit, boustro_cx, boustro_cy, boustro_s1d, centroid_x, centroid_y, speed, entity_label, english_translation)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    )";

    sqlite3_stmt* sw_stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sw_sql, -1, &sw_stmt, nullptr) == SQLITE_OK) {
        for (const auto& b : blocks) {
            int token_5bit = 0;
            if (b.entity_label != "Scene Clear") {
                int cat_id = 3;
                if (b.entity_label.find("Bicycle") != std::string::npos || b.entity_label.find("Cycle") != std::string::npos) cat_id = 1;
                else if (b.entity_label.find("Person") != std::string::npos) cat_id = 0;
                else if (b.entity_label.find("Vehicle") != std::string::npos || b.entity_label.find("Car") != std::string::npos) cat_id = 2;
                token_5bit = ((cat_id & 0x03) << 3) | (b.heading_code & 0x07);
            }

            sqlite3_bind_text(sw_stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
            sqlite3_bind_int64(sw_stmt, 2, b.window_idx);
            sqlite3_bind_int64(sw_stmt, 3, b.entity_idx);
            sqlite3_bind_int64(sw_stmt, 4, b.start_pts);
            sqlite3_bind_int64(sw_stmt, 5, b.end_pts);
            sqlite3_bind_int(sw_stmt, 6, token_5bit);
            sqlite3_bind_int(sw_stmt, 7, b.boustro_cx);
            sqlite3_bind_int(sw_stmt, 8, b.boustro_cy);
            sqlite3_bind_int(sw_stmt, 9, b.boustro_s1d);
            sqlite3_bind_int(sw_stmt, 10, b.centroid_x);
            sqlite3_bind_int(sw_stmt, 11, b.centroid_y);
            sqlite3_bind_double(sw_stmt, 12, b.speed);
            sqlite3_bind_text(sw_stmt, 13, b.entity_label.c_str(), -1, SQLITE_STATIC);
            sqlite3_bind_text(sw_stmt, 14, b.evidence_payload.c_str(), -1, SQLITE_STATIC);

            sqlite3_step(sw_stmt);
            sqlite3_reset(sw_stmt);
        }
        sqlite3_finalize(sw_stmt);
    }

    execute_simple("COMMIT;");
    return true;

}

static std::string compute_vector_block_hash(
    int64_t block_index,
    const std::string& video_id,
    int64_t pts,
    const std::string& frame_hash,
    const uint8_t* grid_sig_data,
    size_t grid_sig_len,
    const std::string& prev_block_hash
) {
    std::string data = std::to_string(block_index) + ":" + video_id + ":" +
                       std::to_string(pts) + ":" + frame_hash + ":" +
                       to_hex_string(grid_sig_data, grid_sig_len) + ":" + prev_block_hash;
    HashDigest d = FrameHasher::compute_sha256(reinterpret_cast<const uint8_t*>(data.data()), data.size());
    return to_hex_string(d);
}

bool LedgerDB::verify_vector_blockchain(const std::string& video_id, size_t& out_total_blocks, std::string& out_tip_hash) {
    out_total_blocks = 0;
    out_tip_hash = "";

    const char* sql = "SELECT block_index, pts, frame_hash, grid_signature, prev_block_hash, block_hash "
                      "FROM vector_frames_blockchain WHERE video_id = ? ORDER BY block_index ASC;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        return false;
    }
    sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);

    std::string expected_prev_hash(64, '0');
    int64_t expected_idx = 0;
    bool valid = true;

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int64_t b_idx = sqlite3_column_int64(stmt, 0);
        int64_t pts = sqlite3_column_int64(stmt, 1);
        const char* f_hash = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
        const void* blob_sig = sqlite3_column_blob(stmt, 3);
        int blob_bytes = sqlite3_column_bytes(stmt, 3);
        const char* prev_hash = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4));
        const char* b_hash = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 5));

        if (!f_hash || !prev_hash || !b_hash || !blob_sig ||
            (blob_bytes != static_cast<int>(GRID_CELLS) && blob_bytes != static_cast<int>(COLOR_GRID_BYTES))) {
            valid = false;
            break;
        }

        if (b_idx != expected_idx) {
            valid = false;
            break;
        }

        if (expected_prev_hash != prev_hash) {
            valid = false;
            break;
        }

        std::string calc_hash = compute_vector_block_hash(
            b_idx, video_id, pts, f_hash,
            reinterpret_cast<const uint8_t*>(blob_sig), blob_bytes, prev_hash
        );

        if (calc_hash != b_hash) {
            valid = false;
            break;
        }

        expected_prev_hash = b_hash;
        out_tip_hash = b_hash;
        expected_idx++;
        out_total_blocks++;
    }

    sqlite3_finalize(stmt);
    return valid && (out_total_blocks > 0);
}

static std::string compute_semantic_block_hash(
    int64_t block_index,
    const std::string& video_id,
    int64_t window_idx,
    int64_t entity_idx,
    int64_t start_pts,
    int64_t end_pts,
    const std::string& entity_label,
    const std::string& evidence_payload,
    const std::string& prev_block_hash
) {
    std::string data = std::to_string(block_index) + ":" + video_id + ":" +
                       std::to_string(window_idx) + ":" + std::to_string(entity_idx) + ":" +
                       std::to_string(start_pts) + ":" + std::to_string(end_pts) + ":" +
                       entity_label + ":" + evidence_payload + ":" + prev_block_hash;
    HashDigest d = FrameHasher::compute_sha256(reinterpret_cast<const uint8_t*>(data.data()), data.size());
    return to_hex_string(d);
}

bool LedgerDB::verify_semantic_blockchain(const std::string& video_id, size_t& out_total_blocks, std::string& out_tip_hash) {
    out_total_blocks = 0;
    out_tip_hash = "";

    const char* sql = "SELECT block_index, window_idx, entity_idx, start_pts, end_pts, entity_label, evidence_payload, prev_block_hash, block_hash "
                      "FROM semantic_evidence_blockchain WHERE video_id = ? ORDER BY block_index ASC;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        return false;
    }
    sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);

    std::string expected_prev_hash(64, '0');
    int64_t expected_idx = 0;
    bool valid = true;

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int64_t b_idx = sqlite3_column_int64(stmt, 0);
        int64_t win_idx = sqlite3_column_int64(stmt, 1);
        int64_t ent_idx = sqlite3_column_int64(stmt, 2);
        int64_t s_pts = sqlite3_column_int64(stmt, 3);
        int64_t e_pts = sqlite3_column_int64(stmt, 4);
        const char* e_label = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 5));
        const char* e_payload = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 6));
        const char* prev_hash = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 7));
        const char* b_hash = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 8));

        if (!e_label || !e_payload || !prev_hash || !b_hash) {
            valid = false;
            break;
        }

        if (b_idx != expected_idx) {
            valid = false;
            break;
        }

        if (expected_prev_hash != prev_hash) {
            valid = false;
            break;
        }

        std::string calc_hash = compute_semantic_block_hash(
            b_idx, video_id, win_idx, ent_idx, s_pts, e_pts, e_label, e_payload, prev_hash
        );

        if (calc_hash != b_hash) {
            valid = false;
            break;
        }

        expected_prev_hash = b_hash;
        out_tip_hash = b_hash;
        expected_idx++;
        out_total_blocks++;
    }

    sqlite3_finalize(stmt);
    return valid && (out_total_blocks > 0);
}

std::vector<VectorBlock> LedgerDB::load_vector_blockchain(const std::string& video_id) {
    std::vector<VectorBlock> blocks;
    const char* sql = "SELECT block_index, pts, frame_index, grid_signature, frame_hash, prev_block_hash, block_hash, timestamp "
                      "FROM vector_frames_blockchain WHERE video_id = ? ORDER BY block_index ASC;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) return blocks;
    sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        VectorBlock b;
        b.block_index = sqlite3_column_int64(stmt, 0);
        b.video_id = video_id;
        b.pts = sqlite3_column_int64(stmt, 1);
        b.frame_index = sqlite3_column_int64(stmt, 2);
        const void* blob = sqlite3_column_blob(stmt, 3);
        int bytes = sqlite3_column_bytes(stmt, 3);
        if (blob) {
            if (bytes == static_cast<int>(COLOR_GRID_BYTES)) {
                std::memcpy(b.color_grid_signature.data(), blob, COLOR_GRID_BYTES);
                std::memcpy(b.grid_signature.data(), blob, GRID_CELLS);
            } else if (bytes == static_cast<int>(GRID_CELLS)) {
                std::memcpy(b.grid_signature.data(), blob, GRID_CELLS);
            }
        }
        const char* t = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4));
        if (t) b.frame_hash = t;
        t = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 5));
        if (t) b.prev_block_hash = t;
        t = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 6));
        if (t) b.block_hash = t;
        t = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 7));
        if (t) b.timestamp = t;
        blocks.push_back(std::move(b));
    }
    sqlite3_finalize(stmt);
    return blocks;
}

std::vector<SemanticBlock> LedgerDB::load_semantic_blockchain(const std::string& video_id) {
    std::vector<SemanticBlock> blocks;
    const char* sql = "SELECT block_index, window_idx, entity_idx, start_pts, end_pts, boustro_cx, boustro_cy, boustro_s1d, centroid_x, centroid_y, speed, heading_code, entity_label, evidence_payload, prev_block_hash, block_hash, timestamp "
                      "FROM semantic_evidence_blockchain WHERE video_id = ? ORDER BY block_index ASC;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) return blocks;
    sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        SemanticBlock b;
        b.block_index = sqlite3_column_int64(stmt, 0);
        b.video_id = video_id;
        b.window_idx = sqlite3_column_int64(stmt, 1);
        b.entity_idx = sqlite3_column_int64(stmt, 2);
        b.start_pts = sqlite3_column_int64(stmt, 3);
        b.end_pts = sqlite3_column_int64(stmt, 4);
        b.boustro_cx = sqlite3_column_int(stmt, 5);
        b.boustro_cy = sqlite3_column_int(stmt, 6);
        b.boustro_s1d = sqlite3_column_int(stmt, 7);
        b.centroid_x = sqlite3_column_int(stmt, 8);
        b.centroid_y = sqlite3_column_int(stmt, 9);
        b.speed = static_cast<float>(sqlite3_column_double(stmt, 10));
        b.heading_code = static_cast<uint8_t>(sqlite3_column_int(stmt, 11));
        const char* t = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 12));
        if (t) b.entity_label = t;
        t = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 13));
        if (t) b.evidence_payload = t;
        t = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 14));
        if (t) b.prev_block_hash = t;
        t = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 15));
        if (t) b.block_hash = t;
        t = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 16));
        if (t) b.timestamp = t;
        blocks.push_back(std::move(b));
    }
    sqlite3_finalize(stmt);
    return blocks;
}

bool LedgerDB::delete_video(const std::string& video_id) {
    execute_simple("BEGIN TRANSACTION;");
    const char* t_vec = "DELETE FROM vector_frames_blockchain WHERE video_id = ?;";
    const char* t_sem = "DELETE FROM semantic_evidence_blockchain WHERE video_id = ?;";
    const char* t_win = "DELETE FROM semantic_sliding_window WHERE video_id = ?;";
    const char* t_cas = "DELETE FROM frame_cas_metadata WHERE video_id = ?;";
    const char* t_for = "DELETE FROM forensic_frame_metadata WHERE video_id = ?;";
    const char* t_frm = "DELETE FROM frame_ledger WHERE video_id = ?;";
    const char* t_meta = "DELETE FROM video_metadata WHERE video_id = ?;";

    auto run_del = [&](const char* sql) {
        sqlite3_stmt* stmt = nullptr;
        if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) == SQLITE_OK) {
            sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        }
    };

    run_del(t_vec);
    run_del(t_sem);
    run_del(t_win);
    run_del(t_cas);
    run_del(t_for);
    run_del(t_frm);
    run_del(t_meta);

    execute_simple("COMMIT;");
    return true;
}

std::string LedgerDB::get_baseline_semantics(const std::string& video_id, int64_t pts) {
    // 1. First search semantic_evidence_blockchain for active moving entity
    const char* sql_active = 
        "SELECT evidence_payload FROM semantic_evidence_blockchain "
        "WHERE video_id = ? AND start_pts <= ? AND end_pts >= ? AND entity_label != 'Scene Clear' "
        "ORDER BY speed DESC LIMIT 1;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql_active, -1, &stmt, nullptr) == SQLITE_OK) {
        sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmt, 2, pts);
        sqlite3_bind_int64(stmt, 3, pts);
        if (sqlite3_step(stmt) == SQLITE_ROW) {
            const unsigned char* text = sqlite3_column_text(stmt, 0);
            if (text && text[0] != '\0') {
                std::string res = reinterpret_cast<const char*>(text);
                sqlite3_finalize(stmt);
                return res;
            }
        }
        sqlite3_finalize(stmt);
    }

    // 2. Query frame_cas_metadata for active detections in this temporal vicinity
    const char* sql_cas =
        "SELECT semantic_summary FROM frame_cas_metadata "
        "WHERE video_id = ? AND pts >= ? - 2000000 AND pts <= ? + 2000000 "
        "AND semantic_summary NOT LIKE '%Scene Clear%' "
        "ORDER BY ABS(pts - ?) ASC LIMIT 1;";
    stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql_cas, -1, &stmt, nullptr) == SQLITE_OK) {
        sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmt, 2, pts);
        sqlite3_bind_int64(stmt, 3, pts);
        sqlite3_bind_int64(stmt, 4, pts);
        if (sqlite3_step(stmt) == SQLITE_ROW) {
            const unsigned char* text = sqlite3_column_text(stmt, 0);
            if (text && text[0] != '\0') {
                std::string res = reinterpret_cast<const char*>(text);
                sqlite3_finalize(stmt);
                return res;
            }
        }
        sqlite3_finalize(stmt);
    }

    // 3. Fallback to any semantic_evidence_blockchain block (e.g. Scene Clear)
    const char* sql_any = 
        "SELECT evidence_payload FROM semantic_evidence_blockchain "
        "WHERE video_id = ? AND start_pts <= ? AND end_pts >= ? LIMIT 1;";
    stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql_any, -1, &stmt, nullptr) == SQLITE_OK) {
        sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmt, 2, pts);
        sqlite3_bind_int64(stmt, 3, pts);
        if (sqlite3_step(stmt) == SQLITE_ROW) {
            const unsigned char* text = sqlite3_column_text(stmt, 0);
            if (text && text[0] != '\0') {
                std::string res = reinterpret_cast<const char*>(text);
                sqlite3_finalize(stmt);
                return res;
            }
        }
        sqlite3_finalize(stmt);
    }

    // 3. Fallback to semantic_sliding_window
    const char* sql_legacy = 
        "SELECT english_translation FROM semantic_sliding_window "
        "WHERE video_id = ? AND start_pts <= ? AND end_pts >= ? "
        "ORDER BY (CASE WHEN entity_label != 'Scene Clear' THEN 1 ELSE 0 END) DESC, speed DESC LIMIT 1;";
    stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql_legacy, -1, &stmt, nullptr) == SQLITE_OK) {
        sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmt, 2, pts);
        sqlite3_bind_int64(stmt, 3, pts);
        std::string result = "";
        if (sqlite3_step(stmt) == SQLITE_ROW) {
            const unsigned char* text = sqlite3_column_text(stmt, 0);
            if (text) result = reinterpret_cast<const char*>(text);
        }
        sqlite3_finalize(stmt);
        return result;
    }

    return "";
}

bool LedgerDB::store_cas_record(const FrameCasRecord& rec) {
    return store_cas_records(rec.video_id, {rec});
}

bool LedgerDB::store_cas_records(const std::string& video_id, const std::vector<FrameCasRecord>& recs) {
    if (recs.empty()) return true;

    execute_simple("BEGIN TRANSACTION;");
    const char* sql = R"(
        INSERT OR REPLACE INTO frame_cas_metadata
        (packet_hash, leaf_index, video_id, pts, dts, color_grid, detections_blob, semantic_summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    )";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        std::cerr << "[LedgerDB] Prepare store_cas_records failed: " << sqlite3_errmsg(db_) << std::endl;
        execute_simple("ROLLBACK;");
        return false;
    }

    for (const auto& r : recs) {
        sqlite3_bind_text(stmt, 1, r.packet_hash.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmt, 2, static_cast<sqlite3_int64>(r.leaf_index));
        sqlite3_bind_text(stmt, 3, video_id.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmt, 4, r.pts);
        sqlite3_bind_int64(stmt, 5, r.dts);
        sqlite3_bind_blob(stmt, 6, r.color_grid.data(), static_cast<int>(r.color_grid.size()), SQLITE_STATIC);
        if (!r.detections.empty()) {
            sqlite3_bind_blob(stmt, 7, r.detections.data(), static_cast<int>(r.detections.size() * sizeof(QuantizedBBox)), SQLITE_STATIC);
        } else {
            sqlite3_bind_null(stmt, 7);
        }
        sqlite3_bind_text(stmt, 8, r.semantic_summary.c_str(), -1, SQLITE_STATIC);

        if (sqlite3_step(stmt) != SQLITE_DONE) {
            std::cerr << "[LedgerDB] Step store_cas_records failed: " << sqlite3_errmsg(db_) << std::endl;
            sqlite3_finalize(stmt);
            execute_simple("ROLLBACK;");
            return false;
        }
        sqlite3_reset(stmt);
    }

    sqlite3_finalize(stmt);
    execute_simple("COMMIT;");
    return true;
}

static FrameCasRecord parse_cas_record(sqlite3_stmt* stmt) {
    FrameCasRecord rec;
    const char* ph = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
    if (ph) rec.packet_hash = ph;
    rec.leaf_index = static_cast<uint64_t>(sqlite3_column_int64(stmt, 1));
    const char* vid = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
    if (vid) rec.video_id = vid;
    rec.pts = sqlite3_column_int64(stmt, 3);
    rec.dts = sqlite3_column_int64(stmt, 4);

    const void* cg_blob = sqlite3_column_blob(stmt, 5);
    int cg_bytes = sqlite3_column_bytes(stmt, 5);
    if (cg_blob && cg_bytes == static_cast<int>(COLOR_GRID_BYTES)) {
        std::memcpy(rec.color_grid.data(), cg_blob, COLOR_GRID_BYTES);
    }

    const void* det_blob = sqlite3_column_blob(stmt, 6);
    int det_bytes = sqlite3_column_bytes(stmt, 6);
    if (det_blob && det_bytes > 0 && det_bytes % sizeof(QuantizedBBox) == 0) {
        size_t count = det_bytes / sizeof(QuantizedBBox);
        rec.detections.resize(count);
        std::memcpy(rec.detections.data(), det_blob, det_bytes);
    }

    const char* sum = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 7));
    if (sum) rec.semantic_summary = sum;

    return rec;
}

std::optional<FrameCasRecord> LedgerDB::get_cas_record(const std::string& packet_hash) {
    const char* sql = "SELECT packet_hash, leaf_index, video_id, pts, dts, color_grid, detections_blob, semantic_summary "
                      "FROM frame_cas_metadata WHERE packet_hash = ? LIMIT 1;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) return std::nullopt;
    sqlite3_bind_text(stmt, 1, packet_hash.c_str(), -1, SQLITE_STATIC);

    if (sqlite3_step(stmt) == SQLITE_ROW) {
        FrameCasRecord rec = parse_cas_record(stmt);
        sqlite3_finalize(stmt);
        return rec;
    }
    sqlite3_finalize(stmt);
    return std::nullopt;
}

std::optional<FrameCasRecord> LedgerDB::get_cas_record_by_index(const std::string& video_id, uint64_t leaf_index) {
    const char* sql = "SELECT packet_hash, leaf_index, video_id, pts, dts, color_grid, detections_blob, semantic_summary "
                      "FROM frame_cas_metadata WHERE video_id = ? AND leaf_index = ? LIMIT 1;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) return std::nullopt;
    sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_int64(stmt, 2, static_cast<sqlite3_int64>(leaf_index));

    if (sqlite3_step(stmt) == SQLITE_ROW) {
        FrameCasRecord rec = parse_cas_record(stmt);
        sqlite3_finalize(stmt);
        return rec;
    }
    sqlite3_finalize(stmt);
    return std::nullopt;
}

std::optional<FrameCasRecord> LedgerDB::get_cas_record_by_pts(const std::string& video_id, int64_t pts) {
    const char* sql = "SELECT packet_hash, leaf_index, video_id, pts, dts, color_grid, detections_blob, semantic_summary "
                      "FROM frame_cas_metadata WHERE video_id = ? AND pts = ? LIMIT 1;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) return std::nullopt;
    sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_int64(stmt, 2, pts);

    if (sqlite3_step(stmt) == SQLITE_ROW) {
        FrameCasRecord rec = parse_cas_record(stmt);
        sqlite3_finalize(stmt);
        return rec;
    }
    sqlite3_finalize(stmt);
    return std::nullopt;
}

std::vector<FrameCasRecord> LedgerDB::get_cas_records_in_range(
    const std::string& video_id,
    uint64_t leaf_start,
    uint64_t leaf_end
) {
    std::vector<FrameCasRecord> records;
    const char* sql = "SELECT packet_hash, leaf_index, video_id, pts, dts, color_grid, detections_blob, semantic_summary "
                      "FROM frame_cas_metadata WHERE video_id = ? AND leaf_index >= ? AND leaf_index <= ? "
                      "ORDER BY leaf_index ASC;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) return records;
    sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_int64(stmt, 2, static_cast<sqlite3_int64>(leaf_start));
    sqlite3_bind_int64(stmt, 3, static_cast<sqlite3_int64>(leaf_end));

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        records.push_back(parse_cas_record(stmt));
    }
    sqlite3_finalize(stmt);
    return records;
}

std::vector<HashDigest> LedgerDB::load_baseline_leaves(const std::string& video_id) {
    std::vector<HashDigest> leaves;

    // Check frame_ledger first (canonical Merkle tree leaf hashes)
    const char* sql_fl = "SELECT frame_hash FROM frame_ledger WHERE video_id = ? ORDER BY id ASC;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql_fl, -1, &stmt, nullptr) == SQLITE_OK) {
        sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
        while (sqlite3_step(stmt) == SQLITE_ROW) {
            const char* hex = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
            if (hex) {
                leaves.push_back(hex_to_digest(hex));
            }
        }
        sqlite3_finalize(stmt);
    }

    if (leaves.empty()) {
        // Fallback to frame_cas_metadata if frame_ledger is empty
        const char* sql_cas = "SELECT packet_hash FROM frame_cas_metadata WHERE video_id = ? ORDER BY leaf_index ASC;";
        if (sqlite3_prepare_v2(db_, sql_cas, -1, &stmt, nullptr) == SQLITE_OK) {
            sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
            while (sqlite3_step(stmt) == SQLITE_ROW) {
                const char* hex = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
                if (hex) {
                    leaves.push_back(hex_to_digest(hex));
                }
            }
            sqlite3_finalize(stmt);
        }
    }

    return leaves;
}

static ForensicEntityRecord parse_forensic_record(sqlite3_stmt* stmt) {
    ForensicEntityRecord rec;
    rec.id = sqlite3_column_int64(stmt, 0);
    const char* ph = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
    if (ph) rec.packet_hash = ph;
    const char* vid = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
    if (vid) rec.video_id = vid;
    rec.leaf_index = static_cast<uint64_t>(sqlite3_column_int64(stmt, 3));
    rec.pts = sqlite3_column_int64(stmt, 4);
    rec.dts = sqlite3_column_int64(stmt, 5);
    rec.track_id = sqlite3_column_int(stmt, 6);
    const char* et = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 7));
    if (et) rec.entity_type = et;
    rec.bbox_x1 = static_cast<float>(sqlite3_column_double(stmt, 8));
    rec.bbox_y1 = static_cast<float>(sqlite3_column_double(stmt, 9));
    rec.bbox_x2 = static_cast<float>(sqlite3_column_double(stmt, 10));
    rec.bbox_y2 = static_cast<float>(sqlite3_column_double(stmt, 11));
    rec.confidence = static_cast<float>(sqlite3_column_double(stmt, 12));

    if (sqlite3_column_type(stmt, 13) != SQLITE_NULL) {
        const void* fe_blob = sqlite3_column_blob(stmt, 13);
        int fe_bytes = sqlite3_column_bytes(stmt, 13);
        if (fe_blob && fe_bytes > 0 && fe_bytes % sizeof(float) == 0) {
            size_t count = fe_bytes / sizeof(float);
            rec.face_embedding.resize(count);
            std::memcpy(rec.face_embedding.data(), fe_blob, fe_bytes);
        }
    }

    if (sqlite3_column_type(stmt, 14) != SQLITE_NULL) {
        const char* pt = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 14));
        if (pt) rec.plate_text = pt;
    }

    if (sqlite3_column_type(stmt, 15) != SQLITE_NULL) {
        rec.signal_state = sqlite3_column_int(stmt, 15);
    }

    if (sqlite3_column_type(stmt, 16) != SQLITE_NULL) {
        rec.signal_timer = sqlite3_column_int(stmt, 16);
    }

    if (sqlite3_column_type(stmt, 17) != SQLITE_NULL) {
        const uint8_t* dc_blob = reinterpret_cast<const uint8_t*>(sqlite3_column_blob(stmt, 17));
        int dc_bytes = sqlite3_column_bytes(stmt, 17);
        if (dc_blob && dc_bytes >= 2) {
            rec.dominant_colors.primary = dc_blob[0];
            rec.dominant_colors.secondary = dc_blob[1];
        }
    }

    if (sqlite3_column_type(stmt, 18) != SQLITE_NULL) {
        const uint8_t* crop_blob = reinterpret_cast<const uint8_t*>(sqlite3_column_blob(stmt, 18));
        int crop_bytes = sqlite3_column_bytes(stmt, 18);
        if (crop_blob && crop_bytes > 0) {
            rec.ref_crop_blob.assign(crop_blob, crop_blob + crop_bytes);
        }
    }

    return rec;
}

bool LedgerDB::store_forensic_records(const std::string& video_id, const std::vector<ForensicEntityRecord>& records) {
    if (records.empty()) return true;

    execute_simple("BEGIN TRANSACTION;");
    const char* sql = R"(
        INSERT INTO forensic_frame_metadata
        (packet_hash, video_id, leaf_index, pts, dts, track_id, entity_type,
         bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence,
         face_embedding, plate_text, signal_state, signal_timer, dominant_colors, ref_crop_blob)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    )";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        std::cerr << "[LedgerDB] Prepare store_forensic_records failed: " << sqlite3_errmsg(db_) << std::endl;
        execute_simple("ROLLBACK;");
        return false;
    }

    for (const auto& r : records) {
        sqlite3_bind_text(stmt, 1, r.packet_hash.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 2, video_id.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmt, 3, static_cast<sqlite3_int64>(r.leaf_index));
        sqlite3_bind_int64(stmt, 4, r.pts);
        sqlite3_bind_int64(stmt, 5, r.dts);
        sqlite3_bind_int(stmt, 6, r.track_id);
        sqlite3_bind_text(stmt, 7, r.entity_type.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_double(stmt, 8, r.bbox_x1);
        sqlite3_bind_double(stmt, 9, r.bbox_y1);
        sqlite3_bind_double(stmt, 10, r.bbox_x2);
        sqlite3_bind_double(stmt, 11, r.bbox_y2);
        sqlite3_bind_double(stmt, 12, r.confidence);

        if (!r.face_embedding.empty()) {
            sqlite3_bind_blob(stmt, 13, r.face_embedding.data(), static_cast<int>(r.face_embedding.size() * sizeof(float)), SQLITE_STATIC);
        } else {
            sqlite3_bind_null(stmt, 13);
        }

        if (!r.plate_text.empty()) {
            sqlite3_bind_text(stmt, 14, r.plate_text.c_str(), -1, SQLITE_STATIC);
        } else {
            sqlite3_bind_null(stmt, 14);
        }

        if (r.signal_state != STATE_UNKNOWN) {
            sqlite3_bind_int(stmt, 15, r.signal_state);
        } else {
            sqlite3_bind_null(stmt, 15);
        }

        if (r.signal_timer >= 0) {
            sqlite3_bind_int(stmt, 16, r.signal_timer);
        } else {
            sqlite3_bind_null(stmt, 16);
        }

        if (r.dominant_colors.primary != COLOR_UNKNOWN) {
            uint8_t dc[2] = {r.dominant_colors.primary, r.dominant_colors.secondary};
            sqlite3_bind_blob(stmt, 17, dc, 2, SQLITE_STATIC);
        } else {
            sqlite3_bind_null(stmt, 17);
        }

        if (!r.ref_crop_blob.empty()) {
            sqlite3_bind_blob(stmt, 18, r.ref_crop_blob.data(), static_cast<int>(r.ref_crop_blob.size()), SQLITE_STATIC);
        } else {
            sqlite3_bind_null(stmt, 18);
        }

        if (sqlite3_step(stmt) != SQLITE_DONE) {
            std::cerr << "[LedgerDB] Step store_forensic_records failed: " << sqlite3_errmsg(db_) << std::endl;
            sqlite3_finalize(stmt);
            execute_simple("ROLLBACK;");
            return false;
        }
        sqlite3_reset(stmt);
    }

    sqlite3_finalize(stmt);
    execute_simple("COMMIT;");
    return true;
}

std::vector<ForensicEntityRecord> LedgerDB::get_forensic_records_by_pts(const std::string& video_id, int64_t pts) {
    std::vector<ForensicEntityRecord> records;
    const char* sql = "SELECT id, packet_hash, video_id, leaf_index, pts, dts, track_id, entity_type, "
                      "bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence, face_embedding, plate_text, signal_state, signal_timer, dominant_colors, ref_crop_blob "
                      "FROM forensic_frame_metadata WHERE video_id = ? AND pts = ? ORDER BY id ASC;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) return records;
    sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_int64(stmt, 2, pts);

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        records.push_back(parse_forensic_record(stmt));
    }
    sqlite3_finalize(stmt);
    return records;
}

std::vector<ForensicEntityRecord> LedgerDB::get_forensic_records_by_packet_hash(const std::string& packet_hash) {
    std::vector<ForensicEntityRecord> records;
    const char* sql = "SELECT id, packet_hash, video_id, leaf_index, pts, dts, track_id, entity_type, "
                      "bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence, face_embedding, plate_text, signal_state, signal_timer, dominant_colors, ref_crop_blob "
                      "FROM forensic_frame_metadata WHERE packet_hash = ? ORDER BY id ASC;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) return records;
    sqlite3_bind_text(stmt, 1, packet_hash.c_str(), -1, SQLITE_STATIC);

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        records.push_back(parse_forensic_record(stmt));
    }
    sqlite3_finalize(stmt);
    return records;
}

std::vector<ForensicEntityRecord> LedgerDB::get_forensic_records_in_range(
    const std::string& video_id,
    int64_t pts_start,
    int64_t pts_end
) {
    std::vector<ForensicEntityRecord> records;
    const char* sql = "SELECT id, packet_hash, video_id, leaf_index, pts, dts, track_id, entity_type, "
                      "bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence, face_embedding, plate_text, signal_state, signal_timer, dominant_colors, ref_crop_blob "
                      "FROM forensic_frame_metadata WHERE video_id = ? AND pts >= ? AND pts <= ? ORDER BY pts ASC, id ASC;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) return records;
    sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_int64(stmt, 2, pts_start);
    sqlite3_bind_int64(stmt, 3, pts_end);

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        records.push_back(parse_forensic_record(stmt));
    }
    sqlite3_finalize(stmt);
    return records;
}

std::vector<ForensicEntityRecord> LedgerDB::get_forensic_records_by_track(const std::string& video_id, int track_id) {
    std::vector<ForensicEntityRecord> records;
    const char* sql = "SELECT id, packet_hash, video_id, leaf_index, pts, dts, track_id, entity_type, "
                      "bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence, face_embedding, plate_text, signal_state, signal_timer, dominant_colors, ref_crop_blob "
                      "FROM forensic_frame_metadata WHERE video_id = ? AND track_id = ? ORDER BY pts ASC;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) return records;
    sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_int(stmt, 2, track_id);

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        records.push_back(parse_forensic_record(stmt));
    }
    sqlite3_finalize(stmt);
    return records;
}

std::vector<ForensicEntityRecord> LedgerDB::get_forensic_records_by_plate(const std::string& video_id, const std::string& plate_text) {
    std::vector<ForensicEntityRecord> records;
    const char* sql = "SELECT id, packet_hash, video_id, leaf_index, pts, dts, track_id, entity_type, "
                      "bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence, face_embedding, plate_text, signal_state, signal_timer, dominant_colors, ref_crop_blob "
                      "FROM forensic_frame_metadata WHERE video_id = ? AND plate_text = ? ORDER BY pts ASC;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) return records;
    sqlite3_bind_text(stmt, 1, video_id.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, plate_text.c_str(), -1, SQLITE_STATIC);

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        records.push_back(parse_forensic_record(stmt));
    }
    sqlite3_finalize(stmt);
    return records;
}

} // namespace Forensic

