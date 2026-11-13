# ==============================================================================
# PEAKLEDGER CORE ENGINE - AGY AUTONOMOUS AGENT CONTEXT & OPERATIONAL DIRECTIVE
# Target: Antigravity CLI (agy) running in WSL2 / Linux Terminal
# Flag: --dangerously-skip-permissions is ENABLED. You have autonomous execution authority.
# ==============================================================================

[SYSTEM IDENTITY & MISSION]
Project: PeakLedger Core Engine (Backend Subsystem)
Context: Smart India Hackathon (SIH) - Forensic Video Integrity & Biometric Ledger
Architecture: Two-Layer Decoupled Forensic Architecture:
  - Layer 1 (Cryptographic Anchor): ITU-T H.264 Annex B Canonical Demuxer + OpenSSL EVP SHA-256 Merkle Tree.
    * Ingests 100% of packets (I, P, B frames). 100% bitwise cross-GPU/CPU determinism. Zero blindspots.
    * Audits at >5.4M packets/sec with ZERO GPU decoding energy.
  - Layer 2 (Forensic Intelligence): Decoupled NVDEC GPU VRAM surface decoder + CUDA Bilinear preprocessor + TensorRT.
    * 512-D ArcFace Biometrics (S_cosine >= 0.72), Levenshtein License Plate OCR (D <= 1).
    * Discrete Traffic Signal State Machine (RED/AMBER/GREEN) & Integer Countdown Timer (|dt| <= 1s).
    * Track-aware reference crop optimizer reducing storage overhead by >93.7%.
  - IPC & Storage: Lock-free POSIX shared memory (/PeakLedger_shm, 640-byte cache-aligned slots) + SQLite CAS (evidence/ledger.db).

--------------------------------------------------------------------------------
[STEP 1: RECREATING THE BACKEND IN WSL2 / LINUX ENVIRONMENT]
--------------------------------------------------------------------------------
Execute the following commands sequentially to build and verify the backend:

1. Check System Hardware & Toolchain:
   nvidia-smi
   nvcc --version || echo "CUDA compiler nvcc not found"
   gcc --version

2. Install Missing Dependencies (if apt is available):
   sudo apt-get update && sudo apt-get install -y \
       build-essential cmake pkg-config \
       libavcodec-dev libavformat-dev libavutil-dev \
       libssl-dev libsqlite3-dev

3. Compile Backend & Test Suite:
   cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
   make clean
   make -j$(nproc)

4. Verify Compiled Binaries:
   ls -lh bin/forensic_backend bin/test_*

5. Run Automated Master Pipeline:
   ./fresh_run.sh evidence/sample_pristine.mp4 evidence/sample_suspect.mp4 "CASE_2026_01" "CCTV_Terminal_NorthGate"

6. Run Independent Verification Tests:
   ./bin/test_crypto_merkle            # Validates Layer 1 Merkle tree determinism
   ./bin/test_ledger_db                # Validates SQLite CAS schema & queries
   ./bin/test_forensic_attribute_engine # Validates Layer 2 biometric & OCR extractors

--------------------------------------------------------------------------------
[STEP 2: MINIMUM HARDWARE CHECK & FALLBACK PROCEDURES]
--------------------------------------------------------------------------------
Minimum Hardware Requirement for Full GPU Acceleration:
  - NVIDIA GPU with Compute Capability >= 8.6 (Ampere RTX 3050 Laptop / Ada Lovelace / Blackwell)
  - At least 2.5 GB available VRAM (PeakLedger runs in VramProfile::LAPTOP mode)

IF REQUIRED MINIMUM HARDWARE IS NOT PRESENT (e.g. CPU-only, Intel iGPU, or low VRAM/disk):
1. Layer 1 CPU Verification Fallback:
   Layer 1 Bitstream Merkle verification does NOT require a GPU or NVDEC. It runs
   purely on CPU using OpenSSL EVP SHA-256 assembly instructions.
   If nvcc/GPU is unavailable, compile Layer 1 and SQLite standalone:
     g++ -std=c++20 -O3 -I./include tests/test_crypto_merkle.cpp src/crypto_merkle.cpp -lcrypto -lpthread -o bin/test_crypto_merkle
     g++ -std=c++20 -O3 -I./include tests/test_ledger_db.cpp src/ledger_db.cpp src/crypto_merkle.cpp -lsqlite3 -lcrypto -lpthread -o bin/test_ledger_db
     ./bin/test_crypto_merkle
     ./bin/test_ledger_db

2. Purge Heavy Files to Clear Space (Low Disk Space Mode):
   If disk space is constrained on the target machine, execute:
     # Remove heavy serialized TensorRT engine and ONNX model (saves ~25 MB):
     rm -f models/model.engine yolo11n.onnx
     # Remove documentation generator scripts if manual is already built (saves space):
     rm -f scripts/render_architecture_flowchart.py scripts/generate_docx_manual.py
     # Clean intermediate build objects:
     make clean
     # Reset database WAL caches:
     bash scripts/clean_ledger.sh

--------------------------------------------------------------------------------
[STEP 3: AUTONOMOUS EXECUTION GUIDANCE FOR AGY]
--------------------------------------------------------------------------------
- `--dangerously-skip-permissions` is actively enabled in this environment.
- Proactively run necessary terminal commands to compile, test, and diagnose.
- If a build failure occurs due to missing include paths (e.g. CUDA path differences like /usr/local/cuda vs /usr/local/cuda-12.x), inspect paths and update the Makefile or CMakeLists.txt accordingly.
- Keep the user updated with crisp, actionable summaries and verify all deliverables.
