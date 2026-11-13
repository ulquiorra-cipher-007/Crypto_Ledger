import os
import sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

PPTX_PATH = "CryptoLedger_SIH2026.pptx"
if not os.path.exists(PPTX_PATH):
    print(f"Error: {PPTX_PATH} not found.")
    sys.exit(1)

prs = Presentation(PPTX_PATH)
if len(prs.slides) != 6:
    print(f"Error: Expected exactly 6 slides, found {len(prs.slides)}.")
    sys.exit(1)

# Color Palette Definitions
C_WHITE     = RGBColor(248, 250, 252)
C_MUTED     = RGBColor(148, 163, 184)
C_ACCENT    = RGBColor(0, 255, 204)     # Teal / Cyan Accent
C_AMBER     = RGBColor(251, 191, 36)     # Warning / Highlight
C_RED       = RGBColor(248, 113, 113)    # Problem Alert
C_GREEN     = RGBColor(52, 211, 153)     # Verified Green

def is_protected_shape(shape):
    """Identifies header/footer/border shapes to prevent accidental modification."""
    if not shape.has_text_frame:
        return True
    text = shape.text.strip()
    protected_tokens = [
        "@SIH Idea submission",
        "Crypto Miners",
        "SMART INDIA HACKATHON",
        "SIH26150",
        "Theme-",
        "PS Category-",
        "Team ID-"
    ]
    for token in protected_tokens:
        if token.lower() in text.lower():
            return True
    # Single-digit page numbers
    if text.isdigit() and len(text) <= 2:
        return True
    return False

def clear_and_set_paragraphs(tf, para_data):
    """
    Clears existing text paragraphs and applies formatted runs.
    para_data: list of tuples: (text, font_size, bold, color, bullet, space_after)
    """
    for i in range(len(tf.paragraphs) - 1, 0, -1):
        p_elem = tf.paragraphs[i]._p
        p_elem.getparent().remove(p_elem)
    
    first = True
    for item in para_data:
        text, font_size, bold, color, bullet, space_after = item
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.text = text
        p.font.size = Pt(font_size)
        p.font.bold = bold
        p.font.color.rgb = color
        p.space_after = Pt(space_after)
        if bullet:
            p.level = 0

# ==============================================================================
# SLIDE 2: PROPOSED SOLUTION - The 3 Forensic Questions & Decoupled Architecture
# ==============================================================================
slide2 = prs.slides[1]
for shape in slide2.shapes:
    if is_protected_shape(shape):
        continue
    text = shape.text.strip()
    
    # Left box: Problem / Investigative Breakdown
    if "Problem / Before" in text or "Proprietary filesystems" in text:
        clear_and_set_paragraphs(shape.text_frame, [
            ("INVESTIGATIVE REALITY & CRITICAL FAILURES", 13, True, C_AMBER, False, 6),
            ("• Evidence Tampering Risk:", 11, True, C_WHITE, False, 2),
            ("  Generative AI & video inpainting imperceptibly alter license plates, faces, and traffic signals.", 10, False, C_MUTED, False, 5),
            ("• The Floating-Point Divergence Trap:", 11, True, C_WHITE, False, 2),
            ("  Hashing decoded pixels triggers 100% false alarms across Ampere vs Blackwell GPUs due to FMA rounding.", 10, False, C_MUTED, False, 5),
            ("• Keyframe Blindspots & Vulnerable Audits:", 11, True, C_WHITE, False, 2),
            ("  150-400 ms inter-frame gaps escape I-frame hashing; centralized logs remain mutable by local admins.", 10, False, C_MUTED, False, 4)
        ])
    
    # Right box: The 3 Core Answers
    elif "CyberChain + PeakLedger" in text or "CyberChain trust layer" in text:
        clear_and_set_paragraphs(shape.text_frame, [
            ("CRYPTOLEDGER: THREE INVESTIGATIVE ANSWERS", 13, True, C_ACCENT, False, 6),
            ("1. WHO HANDLED THE EVIDENCE? (Custody)", 11, True, C_WHITE, False, 2),
            ("  FIDO2 biometric passkeys bind examiner identity; EVM smart contracts anchor custody sessions externally.", 10, False, C_MUTED, False, 5),
            ("2. DID THE VIDEO CHANGE? (Integrity)", 11, True, C_WHITE, False, 2),
            ("  Layer 1 Bitstream Merkle Tree seals raw H.264 NAL units (>5.4M pkts/s, 100% CPU/GPU determinism).", 10, False, C_MUTED, False, 5),
            ("3. WHAT EXACTLY CHANGED? (Explanation)", 11, True, C_WHITE, False, 2),
            ("  Layer 2 selectively decodes only divergent intervals via NVDEC for ArcFace, OCR, & signal state auditing.", 10, False, C_MUTED, False, 4)
        ])
    
    # Bottom banner / Core Innovation
    elif "CORE INNOVATION" in text or "BITSTREAM → MERKLE" in text:
        clear_and_set_paragraphs(shape.text_frame, [
            ("ARCHITECTURAL CENTERPIECE: DECOUPLED CRYPTOGRAPHIC & SEMANTIC LAYERS", 11, True, C_ACCENT, False, 3),
            ("Traditional: Video → Decode → AI → Hash  (Fails on hardware floating-point drift)", 10, False, C_RED, False, 2),
            ("CryptoLedger: Video → BITSTREAM HASH → Merkle Root → Selective Decode ONLY on Mismatch → AI Forensic Audit", 10, True, C_GREEN, False, 0)
        ])

# ==============================================================================
# SLIDE 3: TECHNICAL APPROACH - Two-Tier Pipeline & Security Mechanisms
# ==============================================================================
slide3 = prs.slides[2]
for shape in slide3.shapes:
    if is_protected_shape(shape):
        continue
    text = shape.text.strip()
    
    # Left column: Architecture & Implementation Stack
    if "TECHNOLOGIES TO BE USED" in text or "Programming Languages" in text:
        clear_and_set_paragraphs(shape.text_frame, [
            ("PURPOSE-BUILT FORENSIC ARCHITECTURE", 13, True, C_ACCENT, False, 6),
            ("• Layer 1 Cryptographic Core (C++20 / OpenSSL EVP):", 11, True, C_WHITE, False, 2),
            ("  Annex B byte-stream demuxer + pure-integer SHA-256 Merkle Tree. Zero-decode verification.", 10, False, C_MUTED, False, 5),
            ("• Layer 2 Forensic Explainer (CUDA / TensorRT / NVDEC):", 11, True, C_WHITE, False, 2),
            ("  Selective NV12 hardware decode, ArcFace (S>=0.72), Levenshtein OCR (D<=1), HSV attire clustering.", 10, False, C_MUTED, False, 5),
            ("• Trust & Custody Layer (FIDO2 / Anvil EVM / Solidity 0.8.20):", 11, True, C_WHITE, False, 2),
            ("  W3C WebAuthn biometric passkeys + SessionAuditLedger.sol non-repudiable on-chain session state anchoring.", 10, False, C_MUTED, False, 5),
            ("• Persistence & Telemetry:", 11, True, C_WHITE, False, 2),
            ("  ACID SQLite Content-Addressable Storage + Lock-free POSIX IPC ring buffer (60 FPS).", 10, False, C_MUTED, False, 4)
        ])
    
    # Right column: Implementation Methodology
    elif "METHODOLOGY AND PROCESS" in text or "1. Input & OEM Parsing" in text:
        clear_and_set_paragraphs(shape.text_frame, [
            ("7-STAGE VERIFIABLE FORENSIC PIPELINE", 13, True, C_AMBER, False, 5),
            ("1. Read-Only Ingestion: Canonicalizes H.264 Annex B NAL units; original container untouched.", 10, False, C_WHITE, False, 2),
            ("2. Layer 1 Packet Hashing: Leaf = SHA256(NAL || PTS || DTS || Index) across 100% of I/P/B packets.", 10, False, C_WHITE, False, 2),
            ("3. Merkle Tree Sealing: Generates immutable 32-byte Root & O(log N) inclusion proofs.", 10, False, C_WHITE, False, 2),
            ("4. Zero-Decode Audit: Fast-path re-verification at >5.4M packets/sec (>120x real-time speed).", 10, False, C_WHITE, False, 2),
            ("5. Divergence Pinpointing: If roots differ, binary search isolates exact divergent [PTS_start, PTS_end].", 10, False, C_WHITE, False, 2),
            ("6. Selective NVDEC Decode: Hardware decodes ONLY divergent slices into VRAM for attribute diffing.", 10, False, C_WHITE, False, 2),
            ("7. Custody Sealing: SQLTracker hashes session delta; auto-commits to EVM smart contract.", 10, False, C_WHITE, False, 3)
        ])
    
    # Bottom callout
    elif "Raw surveillance video remains" in text or "Blockchain stores" in text:
        clear_and_set_paragraphs(shape.text_frame, [
            ("EVIDENCE SEPARATION PRINCIPLE: Heavy surveillance video stays in local read-only evidence vaults. Blockchain strictly records lightweight cryptographic state proofs, examiner signatures, and session lifecycle logs.", 10, True, C_WHITE, False, 0)
        ])

# ==============================================================================
# SLIDE 4: FEASIBILITY & VIABILITY - Hardware Bounds, Threat Model & Validation
# ==============================================================================
slide4 = prs.slides[3]
for shape in slide4.shapes:
    if is_protected_shape(shape):
        continue
    text = shape.text.strip()
    
    # Main Feasibility & Capabilities
    if "Technical Feasibility" in text or "IMPLEMENTED CAPABILITIES" in text:
        clear_and_set_paragraphs(shape.text_frame, [
            ("ENGINEERING FEASIBILITY & HARDWARE BOUNDARIES", 13, True, C_ACCENT, False, 6),
            ("• Tier 1 Portable Verification (CPU-Agnostic):", 11, True, C_WHITE, False, 2),
            ("  Layer 1 Merkle hashing requires NO GPU. Demuxing and OpenSSL EVP run natively on any standard laptop.", 10, False, C_MUTED, False, 5),
            ("• Tier 2 Forensic Workstation Profile (<2.5 GB VRAM):", 11, True, C_WHITE, False, 2),
            ("  Engineered with VramProfile::LAPTOP: throttled 2-slot double-buffering and direct NV12 ingestion tested on RTX 3050.", 10, False, C_MUTED, False, 5),
            ("• Rigorous Prototype Validation (66/66 Test Suites Passing):", 11, True, C_WHITE, False, 2),
            ("  7/7 C++ core suites (Merkle, CUDA spatial reduction, TensorRT, IPC) + 59/59 Python integration tests.", 10, False, C_MUTED, False, 5),
            ("• Extensible Demuxing: Modular adapters for standard DVR/NVR H.264 streams and multi-stream containers.", 10, False, C_MUTED, False, 4)
        ])
    
    # Challenges, Mitigations & Threat Model
    elif "Key Challenges" in text or "Mitigations" in text:
        clear_and_set_paragraphs(shape.text_frame, [
            ("THREAT MODEL & FORENSIC MITIGATIONS", 13, True, C_AMBER, False, 6),
            ("• Threat Model Boundaries:", 11, True, C_WHITE, False, 2),
            ("  TRUSTED: Secure acquisition station, cryptographic SHA-256 primitives, examiner FIDO2 token.", 10, False, C_MUTED, False, 2),
            ("  UNTRUSTED: Suspect video files, network delivery pipelines, host OS time drift, local filesystem edits.", 10, False, C_MUTED, False, 5),
            ("• Bitwise Integrity vs Semantic Meaning:", 11, True, C_WHITE, False, 2),
            ("  Re-encoding invalidates Layer 1 bitstream hash. System alerts divergence and falls back to Layer 2 semantic similarity.", 10, False, C_MUTED, False, 5),
            ("• Rogue Administrator Mitigation:", 11, True, C_WHITE, False, 2),
            ("  Local SQLite edits detected instantly via EVM smart contract block-hash cross-verification.", 10, False, C_MUTED, False, 4)
        ])

# ==============================================================================
# SLIDE 5: IMPACT AND BENEFITS - Measurable Operational Gains & Legal Framing
# ==============================================================================
slide5 = prs.slides[4]
for shape in slide5.shapes:
    if is_protected_shape(shape):
        continue
    text = shape.text.strip()
    
    # Impact comparisons
    if "CURRENT STATE" in text or "CRYPTOLEDGER • VENDOR-AGNOSTIC" in text:
        clear_and_set_paragraphs(shape.text_frame, [
            ("MEASURABLE OPERATIONAL BREAKTHROUGH FOR INVESTIGATORS", 13, True, C_ACCENT, False, 6),
            ("• Lightning Verification Speed (>120x Real-Time):", 11, True, C_WHITE, False, 2),
            ("  Zero-decode Layer 1 checks 10 hours of video (864k packets) in <160 ms. Instant triage of authentic video.", 10, False, C_MUTED, False, 5),
            ("• >98% Reduction in Forensic GPU Workload:", 11, True, C_WHITE, False, 2),
            ("  By isolating the exact divergent PTS window, selective NVDEC decodes only manipulated frames, saving massive compute.", 10, False, C_MUTED, False, 5),
            ("• >93.7% Reduction in Evidence Storage Footprint:", 11, True, C_WHITE, False, 2),
            ("  Track-Aware Crop State Machine commits visual crops only on track birth or confidence elevation (+0.15).", 10, False, C_MUTED, False, 5),
            ("• Grounded Legal Positioning (BSA 2023 Section 63):", 11, True, C_WHITE, False, 2),
            ("  Produces tamper-proof technical provenance certificates; legal admissibility remains subject to judicial determination.", 10, False, C_MUTED, False, 4)
        ])
    
    # Beneficiaries / Timeline Box
    elif "FORENSIC ANALYTICS" in text or "BENEFICIARIES" in text:
        clear_and_set_paragraphs(shape.text_frame, [
            ("INSTITUTIONAL VALUE FOR FORENSIC LABS & LAW ENFORCEMENT", 12, True, C_AMBER, False, 4),
            ("• State Police Cyber Cells: Instant triage of CCTV evidence from multi-vendor CCTV/DVR sources.", 10, False, C_WHITE, False, 3),
            ("• Forensic Science Laboratories (FSL): Unimpeachable chain-of-custody logs immune to examiner repudiation.", 10, False, C_WHITE, False, 3),
            ("• Judicial Evidentiary Record: Standalone NIST SP 800-86 HTML report with base64 embedded visual evidence.", 10, False, C_WHITE, False, 3),
            ("• Defense & Prosecution: Objective mathematical proof of packet modification without proprietary vendor software.", 10, False, C_WHITE, False, 2)
        ])

# ==============================================================================
# SLIDE 6: RESEARCH AND REFERENCES - Standards, Statutes & Foundations
# ==============================================================================
slide6 = prs.slides[5]
for shape in slide6.shapes:
    if is_protected_shape(shape):
        continue
    text = shape.text.strip()
    
    # References blocks
    if "DVR / Video Forensics" in text or "Digital Forensics & Chain of Custody" in text or "SWGDE" in text:
        clear_and_set_paragraphs(shape.text_frame, [
            ("STATUTORY, CRYPTOGRAPHIC & SCIENTIFIC STANDARDS", 13, True, C_ACCENT, False, 6),
            ("• Bharatiya Sakshya Adhiniyam (BSA) 2023, Section 63:", 11, True, C_WHITE, False, 2),
            ("  Governs electronic record admissibility. Generates deterministic MOP, SHA-256 digests, & custody certificates.", 10, False, C_MUTED, False, 5),
            ("• NIST SP 800-86 & FIPS 180-4 (SHS / SHA-256):", 11, True, C_WHITE, False, 2),
            ("  Federal guidelines for integrating forensic techniques, digital evidence preservation, and secure hashing.", 10, False, C_MUTED, False, 5),
            ("• ITU-T H.264 Annex B & RFC 6962 Merkle Hash Trees:", 11, True, C_WHITE, False, 2),
            ("  Standardizes NAL byte-stream canonicalization and logarithmic O(log N) cryptographic inclusion proofs.", 10, False, C_MUTED, False, 5),
            ("• ArcFace (CVPR 2019) & Levenshtein Metric (1966):", 11, True, C_WHITE, False, 2),
            ("  Tuned cosine threshold (S>=0.72) for cross-compression face verification; edit distance (D<=1) for OCR plate audit.", 10, False, C_MUTED, False, 5),
            ("• W3C WebAuthn / FIDO2 CTAP2 & Solidity 0.8.20 EVM:", 11, True, C_WHITE, False, 2),
            ("  Phishing-resistant examiner authentication and tamper-evident smart contract session custody logging.", 10, False, C_MUTED, False, 4)
        ])
    
    # Bottom summary box
    elif "CryptoLedger integrates" in text or "SWGDE 17-V-002-1.4" in text:
        clear_and_set_paragraphs(shape.text_frame, [
            ("SUMMARY SPECIFICATION: CryptoLedger establishes an integrated, verifiable forensic pipeline bridging read-only bitstream ingestion, pure-integer Merkle verification, selective semantic explanation, and FIDO2/EVM custody anchoring.", 10, True, C_WHITE, False, 0)
        ])

prs.save(PPTX_PATH)
print("Successfully patched CryptoLedger_SIH2026.pptx with all rectifications.")
