#include "crypto_merkle.hpp"
#include <iostream>
#include <cassert>
#include <vector>
#include <chrono>

int main() {
    std::cout << "[+] Verifying OpenSSL EVP SHA-256 (SHA-NI) Canonical Packet Hasher..." << std::endl;
    Forensic::FrameHasher hasher;

    // Synthetic Annex B NAL unit (e.g. 00 00 00 01 67 ... SPS/IDR packet)
    std::vector<uint8_t> canonical_nal = {0x00, 0x00, 0x00, 0x01, 0x67, 0x42, 0x00, 0x1E, 0x96, 0x54, 0x05, 0x01, 0xE9, 0x80};
    int64_t pts = 33333;
    int64_t dts = 33333;
    uint64_t leaf_index = 0;

    auto h1 = hasher.hash_canonical_packet(canonical_nal.data(), canonical_nal.size(), pts, dts, leaf_index);
    auto h2 = hasher.hash_canonical_packet(canonical_nal.data(), canonical_nal.size(), pts, dts, leaf_index);
    assert(h1 == h2);
    std::cout << "    [OK] Canonical packet leaf determinism confirmed: " << Forensic::to_hex_string(h1) << std::endl;

    // Avalanche effect check 1: change 1 byte in NAL payload
    auto tampered_nal = canonical_nal;
    tampered_nal[4] ^= 0x01;
    auto h_tampered_nal = hasher.hash_canonical_packet(tampered_nal.data(), tampered_nal.size(), pts, dts, leaf_index);
    assert(h1 != h_tampered_nal);

    // Avalanche effect check 2: change PTS tick
    auto h_tampered_pts = hasher.hash_canonical_packet(canonical_nal.data(), canonical_nal.size(), pts + 1, dts, leaf_index);
    assert(h1 != h_tampered_pts);

    // Avalanche effect check 3: change DTS tick
    auto h_tampered_dts = hasher.hash_canonical_packet(canonical_nal.data(), canonical_nal.size(), pts, dts + 1, leaf_index);
    assert(h1 != h_tampered_dts);

    // Avalanche effect check 4: change leaf index (replay / reorder attack)
    auto h_tampered_idx = hasher.hash_canonical_packet(canonical_nal.data(), canonical_nal.size(), pts, dts, leaf_index + 1);
    assert(h1 != h_tampered_idx);
    std::cout << "    [OK] Cryptographic avalanche effect verified across NAL, PTS, DTS, and Leaf Index." << std::endl;

    // Benchmark canonical packet hashing throughput
    const int bench_iters = 500000;
    auto t0 = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < bench_iters; ++i) {
        hasher.hash_canonical_packet(canonical_nal.data(), canonical_nal.size(), pts + i, dts + i, i);
    }
    auto t1 = std::chrono::high_resolution_clock::now();
    double total_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    double fps = (bench_iters / total_ms) * 1000.0;
    double us = (total_ms * 1000.0) / bench_iters;
    std::cout << "    [BENCHMARK] Canonical Packet Hashing: " << fps << " hashes/sec (" << us << " us per packet)" << std::endl;

    // Verify Merkle Tree Construction & Proofs
    std::cout << "[+] Verifying In-Memory Merkle Tree Engine & Localization..." << std::endl;
    for (size_t n : {0, 1, 2, 3, 4, 7, 8, 15, 16, 25, 100, 1000}) {
        std::vector<Forensic::HashDigest> leaves(n);
        for (size_t i = 0; i < n; ++i) {
            leaves[i] = hasher.hash_canonical_packet(canonical_nal.data(), canonical_nal.size(), i * 33333, i * 33333, i);
        }

        Forensic::MerkleTree tree(leaves);
        auto root = tree.get_root();
        assert(!tree.get_root_hex().empty());

        // Verify logarithmic proofs for every single leaf
        for (size_t i = 0; i < n; ++i) {
            auto proof = tree.get_proof(i);
            bool valid = Forensic::MerkleTree::verify_proof(leaves[i], proof, root);
            assert(valid);

            // Tamper test: corrupted leaf must fail verification
            Forensic::HashDigest fake_leaf = leaves[i];
            fake_leaf[0] ^= 0xFF;
            assert(!Forensic::MerkleTree::verify_proof(fake_leaf, proof, root));
        }
    }
    std::cout << "    [OK] Merkle root sealing and cryptographic inclusion proofs verified across 0 to 1000 leaf trees." << std::endl;

    // Verify Divergent Span Isolation (Localized Failure Reconciliation)
    const size_t test_size = 50;
    std::vector<Forensic::HashDigest> base_leaves(test_size);
    std::vector<Forensic::HashDigest> suspect_leaves(test_size);
    for (size_t i = 0; i < test_size; ++i) {
        base_leaves[i] = hasher.hash_canonical_packet(canonical_nal.data(), canonical_nal.size(), i * 41666, i * 41666, i);
        suspect_leaves[i] = base_leaves[i];
    }

    // Tamper indices 10 through 14
    for (size_t i = 10; i <= 14; ++i) {
        suspect_leaves[i][0] ^= 0xEE;
    }
    // Tamper index 30
    suspect_leaves[30][0] ^= 0xAA;

    auto spans = Forensic::MerkleTree::find_divergent_spans(base_leaves, suspect_leaves);
    assert(spans.size() == 2);
    assert(spans[0].first == 10 && spans[0].second == 14);
    assert(spans[1].first == 30 && spans[1].second == 30);
    std::cout << "    [OK] Localized Failure Reconciliation: isolated divergent spans [10..14] and [30..30]." << std::endl;

    std::cout << "[+] STEP 4 UNIT TEST PASSED." << std::endl;
    return 0;
}
