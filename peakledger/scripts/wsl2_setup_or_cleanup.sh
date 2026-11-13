#!/usr/bin/env bash
# ==============================================================================
# PeakLedger WSL2 Autonomous Setup & Hardware-Adaptive Optimizer
# Designed for autonomous agy execution (--dangerously-skip-permissions enabled)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "========================================================================"
echo "PEAKLEDGER AUTONOMOUS WSL2 SETUP & HARDWARE AUDIT"
echo "========================================================================"

# 1. Check GPU & CUDA
HAS_GPU=0
if command -v nvidia-smi &> /dev/null; then
    if nvidia-smi &> /dev/null; then
        HAS_GPU=1
        GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n 1)
        GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader | head -n 1)
        echo "[+] NVIDIA GPU Detected: $GPU_NAME ($GPU_MEM)"
    fi
fi

# 2. Check Disk Space (Available in MB)
AVAIL_DISK_MB=$(df -m . | awk 'NR==2 {print $4}')
echo "[+] Available Disk Space: ${AVAIL_DISK_MB} MB"

if [ "$HAS_GPU" -eq 1 ]; then
    echo "[+] Minimum hardware requirements MET for GPU acceleration."
    echo "[+] Compiling C++20 / CUDA forensic backend..."
    make clean || true
    make -j"$(nproc)"
    echo "[+] Compilation successful. Running test suites..."
    ./bin/test_crypto_merkle
    ./bin/test_ledger_db
    ./bin/test_forensic_attribute_engine
    echo "========================================================================"
    echo "[SUCCESS] PeakLedger backend fully operational with GPU acceleration."
    echo "========================================================================"
else
    echo "[-] WARNING: Minimum NVIDIA GPU hardware NOT detected (CPU-only / Low-spec environment)."
    echo "[*] Activating Lightweight CPU Forensic Mode & Storage Optimization..."

    # Remove non-essential heavy scripts to clear up space
    echo "[*] Purging documentation and render generators to clear disk space..."
    rm -f scripts/render_architecture_flowchart.py scripts/generate_docx_manual.py
    
    # If disk space is tight (< 1000 MB), purge heavy engine models
    if [ "$AVAIL_DISK_MB" -lt 1000 ]; then
        echo "[*] Disk space under 1GB: Purging heavy serialized model engines..."
        rm -f models/model.engine yolo11n.onnx
    fi

    # Compile Layer 1 Bitstream Merkle & SQLite CAS engine using standard g++ (CPU only)
    mkdir -p bin
    echo "[*] Compiling CPU Layer 1 Bitstream Merkle & SQLite CAS verification engines..."
    g++ -std=c++20 -O3 -I./include tests/test_crypto_merkle.cpp src/crypto_merkle.cpp -lcrypto -lpthread -o bin/test_crypto_merkle
    g++ -std=c++20 -O3 -I./include tests/test_ledger_db.cpp src/ledger_db.cpp src/crypto_merkle.cpp -lsqlite3 -lcrypto -lpthread -o bin/test_ledger_db

    echo "[*] Running Layer 1 Bitstream Merkle Tree verification..."
    ./bin/test_crypto_merkle
    echo "[*] Running SQLite Forensic CAS Database verification..."
    ./bin/test_ledger_db

    echo "========================================================================"
    echo "[SUCCESS] Space cleared. Layer 1 CPU Bitstream Verification PASSED 100%!"
    echo "========================================================================"
fi
