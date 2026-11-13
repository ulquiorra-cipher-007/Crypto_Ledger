#include "crypto_merkle.hpp"
#include <stdexcept>
#include <cstring>

namespace Forensic {

FrameHasher::FrameHasher() {
    ctx_ = EVP_MD_CTX_new();
    if (!ctx_) {
        throw std::runtime_error("Failed to allocate OpenSSL EVP_MD_CTX");
    }
    md_ = EVP_sha256();
    if (!md_) {
        throw std::runtime_error("Failed to fetch OpenSSL EVP_sha256 implementation");
    }
}

FrameHasher::~FrameHasher() {
    if (ctx_) {
        EVP_MD_CTX_free(ctx_);
        ctx_ = nullptr;
    }
}

HashDigest FrameHasher::hash_canonical_packet(
    const uint8_t* nal_data,
    size_t nal_size,
    int64_t pts,
    int64_t dts,
    uint64_t leaf_index
) {
    HashDigest digest{};
    unsigned int len = 0;

    EVP_DigestInit_ex(ctx_, md_, nullptr);
    if (nal_data && nal_size > 0) {
        EVP_DigestUpdate(ctx_, nal_data, nal_size);
    }
    uint64_t u_size = static_cast<uint64_t>(nal_size);
    EVP_DigestUpdate(ctx_, &u_size, sizeof(u_size));
    EVP_DigestUpdate(ctx_, &pts, sizeof(pts));
    EVP_DigestUpdate(ctx_, &dts, sizeof(dts));
    EVP_DigestUpdate(ctx_, &leaf_index, sizeof(leaf_index));
    EVP_DigestFinal_ex(ctx_, digest.data(), &len);

    return digest;
}

HashDigest FrameHasher::hash_frame(const uint8_t* sig_512, int64_t pts) {
    HashDigest digest{};
    unsigned int len = 0;

    // Reinitializing pre-allocated context guarantees zero heap allocations in hot path
    EVP_DigestInit_ex(ctx_, md_, nullptr);
    EVP_DigestUpdate(ctx_, sig_512, GRID_CELLS);
    EVP_DigestUpdate(ctx_, &pts, sizeof(pts));
    EVP_DigestFinal_ex(ctx_, digest.data(), &len);

    return digest;
}

HashDigest FrameHasher::hash_frame(const GridSignature& sig, int64_t pts) {
    return hash_frame(sig.data(), pts);
}

HashDigest FrameHasher::compute_sha256(const uint8_t* data, size_t len) {
    HashDigest digest{};
    unsigned int out_len = 0;
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    if (ctx) {
        EVP_DigestInit_ex(ctx, EVP_sha256(), nullptr);
        if (data && len > 0) {
            EVP_DigestUpdate(ctx, data, len);
        }
        EVP_DigestFinal_ex(ctx, digest.data(), &out_len);
        EVP_MD_CTX_free(ctx);
    }
    return digest;
}

HashDigest FrameHasher::combine_hashes(const HashDigest& left, const HashDigest& right) {
    HashDigest digest{};
    unsigned int out_len = 0;
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    if (ctx) {
        EVP_DigestInit_ex(ctx, EVP_sha256(), nullptr);
        EVP_DigestUpdate(ctx, left.data(), SHA256_DIGEST_LENGTH);
        EVP_DigestUpdate(ctx, right.data(), SHA256_DIGEST_LENGTH);
        EVP_DigestFinal_ex(ctx, digest.data(), &out_len);
        EVP_MD_CTX_free(ctx);
    }
    return digest;
}

MerkleTree::MerkleTree(const std::vector<HashDigest>& leaves) {
    if (leaves.empty()) {
        root_ = FrameHasher::compute_sha256(nullptr, 0);
        return;
    }

    levels_.push_back(leaves);

    while (levels_.back().size() > 1) {
        const auto& cur = levels_.back();
        std::vector<HashDigest> next_level;
        next_level.reserve((cur.size() + 1) / 2);

        for (size_t i = 0; i < cur.size(); i += 2) {
            if (i + 1 < cur.size()) {
                next_level.push_back(FrameHasher::combine_hashes(cur[i], cur[i + 1]));
            } else {
                // RFC 6962 standard: duplicate trailing leaf if count is odd
                next_level.push_back(FrameHasher::combine_hashes(cur[i], cur[i]));
            }
        }
        levels_.push_back(std::move(next_level));
    }

    root_ = levels_.back()[0];
}

std::vector<MerkleProofNode> MerkleTree::get_proof(size_t leaf_index) const {
    std::vector<MerkleProofNode> proof;
    if (levels_.empty() || leaf_index >= levels_[0].size()) {
        return proof;
    }

    size_t idx = leaf_index;
    for (size_t lvl = 0; lvl + 1 < levels_.size(); ++lvl) {
        const auto& cur_level = levels_[lvl];
        size_t sibling_idx = (idx % 2 == 0) ? idx + 1 : idx - 1;
        if (sibling_idx >= cur_level.size()) {
            sibling_idx = idx; // Sibling was self due to odd duplication
        }

        MerkleProofNode node;
        node.sibling = cur_level[sibling_idx];
        node.is_left = (idx % 2 != 0);
        proof.push_back(node);

        idx /= 2;
    }
    return proof;
}

bool MerkleTree::verify_proof(
    const HashDigest& leaf,
    const std::vector<MerkleProofNode>& proof,
    const HashDigest& expected_root
) {
    HashDigest cur = leaf;
    for (const auto& node : proof) {
        if (node.is_left) {
            cur = FrameHasher::combine_hashes(node.sibling, cur);
        } else {
            cur = FrameHasher::combine_hashes(cur, node.sibling);
        }
    }
    return cur == expected_root;
}

std::vector<std::pair<size_t, size_t>> MerkleTree::find_divergent_spans(
    const std::vector<HashDigest>& baseline_leaves,
    const std::vector<HashDigest>& suspect_leaves
) {
    std::vector<std::pair<size_t, size_t>> spans;
    size_t min_len = std::min(baseline_leaves.size(), suspect_leaves.size());
    size_t max_len = std::max(baseline_leaves.size(), suspect_leaves.size());

    bool in_span = false;
    size_t span_start = 0;

    for (size_t i = 0; i < min_len; ++i) {
        if (baseline_leaves[i] != suspect_leaves[i]) {
            if (!in_span) {
                in_span = true;
                span_start = i;
            }
        } else {
            if (in_span) {
                spans.push_back({span_start, i - 1});
                in_span = false;
            }
        }
    }
    if (in_span) {
        spans.push_back({span_start, min_len - 1});
        in_span = false;
    }

    if (min_len < max_len) {
        spans.push_back({min_len, max_len - 1});
    }

    return spans;
}

} // namespace Forensic
