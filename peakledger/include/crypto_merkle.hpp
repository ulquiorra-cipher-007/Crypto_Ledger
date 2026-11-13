#pragma once

#include "common.hpp"
#include <openssl/evp.h>
#include <vector>
#include <string>
#include <memory>

namespace Forensic {

struct MerkleProofNode {
    HashDigest sibling{};
    bool is_left{false}; // True if sibling is left operand in Hash(sibling || current)
};

class FrameHasher {
public:
    FrameHasher();
    ~FrameHasher();

    FrameHasher(const FrameHasher&) = delete;
    FrameHasher& operator=(const FrameHasher&) = delete;

    /**
     * @brief Computes deterministic Layer 1 canonical packet leaf digest:
     * Leaf_i = SHA256(nal_data || nal_size || pkt.pts || pkt.dts || i)
     * Guarantees 100% bitwise identity across any CPU, GPU, OS, or container remuxing.
     */
    HashDigest hash_canonical_packet(
        const uint8_t* nal_data,
        size_t nal_size,
        int64_t pts,
        int64_t dts,
        uint64_t leaf_index
    );

    // Legacy frame hashing (for backward compatibility with spatial tests)
    HashDigest hash_frame(const GridSignature& sig, int64_t pts);
    HashDigest hash_frame(const uint8_t* sig_512, int64_t pts);

    // Static cryptographic primitives
    static HashDigest compute_sha256(const uint8_t* data, size_t len);
    static HashDigest combine_hashes(const HashDigest& left, const HashDigest& right);

private:
    EVP_MD_CTX* ctx_{nullptr};
    const EVP_MD* md_{nullptr};
};

class MerkleTree {
public:
    explicit MerkleTree(const std::vector<HashDigest>& leaves);

    HashDigest get_root() const { return root_; }
    std::string get_root_hex() const { return to_hex_string(root_); }
    size_t get_leaf_count() const { return levels_.empty() ? 0 : levels_[0].size(); }
    const std::vector<HashDigest>& get_leaves() const {
        static const std::vector<HashDigest> s_empty;
        return levels_.empty() ? s_empty : levels_[0];
    }

    // Traverses leaves and isolates contiguous spans of divergent leaf indices [start, end]
    static std::vector<std::pair<size_t, size_t>> find_divergent_spans(
        const std::vector<HashDigest>& baseline_leaves,
        const std::vector<HashDigest>& suspect_leaves
    );

    // Generates logarithmic cryptographic inclusion proof O(log N)
    std::vector<MerkleProofNode> get_proof(size_t leaf_index) const;

    // Verifies cryptographic inclusion proof against Merkle root
    static bool verify_proof(
        const HashDigest& leaf,
        const std::vector<MerkleProofNode>& proof,
        const HashDigest& expected_root
    );

private:
    std::vector<std::vector<HashDigest>> levels_;
    HashDigest root_{};
};

} // namespace Forensic
