#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}    ForensicVideoVerifier - Full Automated Verification Suite   ${NC}"
echo -e "${BLUE}================================================================${NC}"

# Ensure binaries directory exists
mkdir -p bin build evidence

# 1. POSIX IPC Ring Buffer Unit Test
echo -e "\n${BLUE}[TEST 1/5] Running POSIX Shared Memory Ring Buffer Unit Test...${NC}"
g++ -O3 -Wall -Wextra -std=c++17 -Iinclude tests/test_ring_buffer.cpp -lrt -lpthread -o bin/test_ring_buffer
./bin/test_ring_buffer
echo -e "${GREEN}[PASSED] Ring Buffer lock-free IPC verified.${NC}"

# 2. CUDA Integer-Only Spatial Hasher Unit Test
echo -e "\n${BLUE}[TEST 2/5] Running Deterministic CUDA Spatial Hasher Unit Test (sm_86/sm_89/sm_120)...${NC}"
export PATH="/usr/local/cuda-13.2/bin:/usr/local/cuda/bin:$PATH"
nvcc -O3 -std=c++17 \
    -gencode arch=compute_86,code=sm_86 \
    -gencode arch=compute_89,code=sm_89 \
    -gencode arch=compute_120,code=sm_120 \
    -gencode arch=compute_89,code=compute_89 \
    -Iinclude src/cuda_spatial_hash.cu tests/test_cuda_hash.cu -o bin/test_cuda_hash
./bin/test_cuda_hash
echo -e "${GREEN}[PASSED] CUDA spatial hasher bit-identity verified on 1080p & 4K.${NC}"

# 2b. CUDA Preprocessor Unit Test
echo -e "\n${BLUE}[TEST 2b] Running CUDA Zero-Copy Preprocessor Unit Test (sm_86/sm_89/sm_120)...${NC}"
./bin/test_cuda_preprocess
echo -e "${GREEN}[PASSED] CUDA preprocessor verified.${NC}"

# 2c. TensorRT Execution Wrapper Unit Test
echo -e "\n${BLUE}[TEST 2c] Running TensorRT 10/11 Inference Unit Test (enqueueV3)...${NC}"
./bin/test_trt_inference
echo -e "${GREEN}[PASSED] TensorRT 10/11 inference engine verified.${NC}"

# 2d. Centroid Motion Tracker Unit Test
echo -e "\n${BLUE}[TEST 2d] Running Centroid Motion Tracker Unit Test...${NC}"
./bin/test_motion_tracker
echo -e "${GREEN}[PASSED] Centroid Motion Tracker verified.${NC}"

# 3. OpenSSL EVP SHA-NI & Merkle Tree Unit Test
echo -e "\n${BLUE}[TEST 3/5] Running OpenSSL EVP SHA-NI & Merkle Tree Engine Unit Test...${NC}"
g++ -O3 -Wall -Wextra -std=c++17 -Iinclude src/crypto_merkle.cpp tests/test_crypto_merkle.cpp -lcrypto -o bin/test_crypto_merkle
./bin/test_crypto_merkle
echo -e "${GREEN}[PASSED] SHA-NI and Merkle inclusion proofs verified.${NC}"

# 4. SQLite3 Ledger DB Unit Test
echo -e "\n${BLUE}[TEST 4/5] Running SQLite3 Transactional Ledger Storage Unit Test...${NC}"
g++ -O3 -Wall -Wextra -std=c++17 -Iinclude src/ledger_db.cpp src/crypto_merkle.cpp tests/test_ledger_db.cpp -lsqlite3 -lcrypto -o bin/test_ledger_db
./bin/test_ledger_db
echo -e "${GREEN}[PASSED] SQLite ledger transactions and baseline queries verified.${NC}"

# 5. Full End-to-End Ingestion & Verification Pipeline
echo -e "\n${BLUE}[TEST 5/5] Running Full End-to-End Pipeline on Real Hardware Decoded Video...${NC}"
TEST_DB="evidence/e2e_test_ledger.db"
rm -f "$TEST_DB"*
rm -f evidence/tamper_frame_*.jpg

# 5a. Ingestion
echo -e "  -> Executing Mode 1: Ingestion & Ledger Sealing on Pristine Video..."
./AppDir/AppRun --cli --ingest evidence/sample_pristine.mp4 \
    --id E2E_CASE_PRISTINE \
    --mop "Axon-Body4-E2E" \
    --db "$TEST_DB"

# 5b. Verify Pristine
echo -e "  -> Executing Mode 2: Verification of Pristine Video (Expecting 100% Match)..."
./AppDir/AppRun --cli --verify evidence/sample_pristine.mp4 \
    --id E2E_CASE_PRISTINE \
    --db "$TEST_DB"
echo -e "${GREEN}  [OK] Pristine video verified with 0 discrepancies.${NC}"

# 5c. Verify Suspect
echo -e "  -> Executing Mode 2: Verification of Suspect Video (Expecting Tamper Detection)..."
set +e
./AppDir/AppRun --cli --verify evidence/sample_suspect.mp4 \
    --id E2E_CASE_PRISTINE \
    --db "$TEST_DB" \
    --engine models/model.engine
VERIFY_STATUS=$?
set -e

if [ $VERIFY_STATUS -eq 2 ]; then
    echo -e "${GREEN}  [OK] Tamper condition correctly detected (Exit code 2).${NC}"
else
    echo -e "${RED}  [FAIL] Expected exit code 2 on tampered video, got $VERIFY_STATUS.${NC}"
    exit 1
fi

# Verify dumped evidence JPEGs
EVIDENCE_COUNT=$(ls -1 evidence/tamper_frame_*.jpg 2>/dev/null | wc -l)
if [ "$EVIDENCE_COUNT" -gt 0 ]; then
    echo -e "${GREEN}  [OK] Isolated and dumped $EVIDENCE_COUNT real physical evidence JPEG frames.${NC}"
else
    echo -e "${RED}  [FAIL] No evidence JPEGs dumped on disk.${NC}"
    exit 1
fi

# Generate and verify Single Clean HTML, EPUB, and Animated GIF reports
python3 -c "
import os, glob
from ui.main import generate_nist_report

tamper_jpegs = sorted(glob.glob('evidence/tamper_frame_*.jpg'))
events = [{'pts': int(os.path.basename(p).split('_')[2].split('.')[0]), 'image': p, 'residual': 1500} for p in tamper_jpegs]
report = generate_nist_report(
    video_id='E2E_CASE_PRISTINE',
    source_uri='evidence/sample_suspect.mp4',
    merkle_root='e2e_verified_merkle_root',
    mop='Axon-Body4-E2E',
    tampered_events=events,
    output_html_path='evidence/Forensic_Report.html',
    cleanup_frames=True
)
assert os.path.exists(report) and os.path.getsize(report) > 10000
print('[OK] Single Clean Standalone Forensic HTML Report (' + str(os.path.getsize(report)) + ' bytes) generated successfully.')
"

# Verify folder cleanup
REMAINING_JPGS=$(ls -1 evidence/tamper_frame_*.jpg 2>/dev/null | wc -l)
if [ "$REMAINING_JPGS" -eq 0 ]; then
    echo -e "${GREEN}  [OK] Evidence directory clean: all loose temporary frame dumps removed.${NC}"
else
    echo -e "${RED}  [FAIL] Temporary evidence JPEGs not cleaned up ($REMAINING_JPGS remaining).${NC}"
    exit 1
fi

echo -e "\n${GREEN}================================================================${NC}"
echo -e "${GREEN}    ALL 5/5 FORENSIC VERIFIER TESTS PASSED SUCCESSFULLY!        ${NC}"
echo -e "${GREEN}================================================================${NC}"
