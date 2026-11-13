#!/usr/bin/env bash
# ==============================================================================
# Clean Ledger & Evidence Helper Script
# Wipes SQLite databases (including WAL/SHM files) and evidence artifacts
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "[-] Cleaning SQLite ledger databases..."
rm -f evidence/ledger.db*
rm -f evidence/e2e_test_ledger.db*
rm -f /home/ulquiorra/Desktop/crypto_video_ledger/ledger.db*
rm -f /home/ulquiorra/Desktop/crypto_video_ledger/build/ledger.db*

echo "[-] Cleaning loose evidence frame captures..."
rm -f evidence/tamper_frame_*.jpg
rm -f evidence/pure_hybrid_test.png
rm -f evidence/clean_hybrid_*.png
rm -f evidence/test_hybrid_*.png

# Ensure sample video symlinks exist
if [ -f "/home/ulquiorra/Desktop/crypto_video_ledger/clean_surveillance.mp4" ]; then
    ln -sf /home/ulquiorra/Desktop/crypto_video_ledger/clean_surveillance.mp4 evidence/sample_pristine.mp4
fi
if [ -f "/home/ulquiorra/Desktop/crypto_video_ledger/morphed_surveillance.mp4" ]; then
    ln -sf /home/ulquiorra/Desktop/crypto_video_ledger/morphed_surveillance.mp4 evidence/sample_suspect.mp4
fi

echo "[+] Ledger databases and temporary evidence reset cleanly."
echo "[+] Ready for a fresh Ingestion / Verification run."
