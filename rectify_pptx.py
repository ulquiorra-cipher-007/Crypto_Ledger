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
C_AMBER     = RGBColor(251, 191, 36)     # Warning / Highlight Gold
C_RED       = RGBColor(248, 113, 113)    # Problem Alert Red
C_GREEN     = RGBColor(52, 211, 153)     # Verified Green

def set_shape_text(shape, runs_data, align=PP_ALIGN.LEFT):
    """
    Sets clean paragraphs and runs into a shape's text frame.
    runs_data: list of paragraphs.
      Each paragraph can be:
        - A string: rendered as a single run (size 10, normal, white)
        - A tuple (text, size, bold, color, space_after)
        - A list of run tuples: [(text, size, bold, color), ...] for multi-style paragraphs,
          with optional space_after on the last element or paragraph level.
    """
    tf = shape.text_frame
    tf.word_wrap = True
    
    # Remove existing paragraphs except the first
    for i in range(len(tf.paragraphs) - 1, 0, -1):
        p_elem = tf.paragraphs[i]._p
        p_elem.getparent().remove(p_elem)
    
    first = True
    for p_info in runs_data:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        
        # Clear any existing runs in p
        p.text = ""
        
        if isinstance(p_info, str):
            r = p.add_run()
            r.text = p_info
            r.font.size = Pt(10)
            r.font.color.rgb = C_WHITE
            p.space_after = Pt(2)
        elif isinstance(p_info, tuple):
            text, size, bold, color, space_after = p_info
            r = p.add_run()
            r.text = text
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = color
            p.space_after = Pt(space_after)
        elif isinstance(p_info, list):
            # Multiple runs in one paragraph, e.g. bold bullet title + normal description
            # Last item can be space_after float/int if len % 2 == 1 or explicit
            space_after = 3
            runs_list = p_info
            if len(p_info) > 0 and isinstance(p_info[-1], (int, float)):
                space_after = p_info[-1]
                runs_list = p_info[:-1]
            p.space_after = Pt(space_after)
            for item in runs_list:
                text, size, bold, color = item
                r = p.add_run()
                r.text = text
                r.font.size = Pt(size)
                r.font.bold = bold
                r.font.color.rgb = color

# ==============================================================================
# SLIDE 2: PROPOSED SOLUTION - The 3 Forensic Questions & Decoupled Architecture
# ==============================================================================
slide2 = prs.slides[1]

# Shape 6 (Text 2): Left Top Title
set_shape_text(slide2.shapes[6], [
    ("INVESTIGATIVE REALITY & CRITICAL FAILURES", 11.5, True, C_AMBER, 0)
])

# Shape 7 (Text 3): Left Top Body
set_shape_text(slide2.shapes[7], [
    [
        ("• Evidence Tampering Risk: ", 9.5, True, C_WHITE),
        ("Generative AI & inpainting imperceptibly alter license plates, faces, and traffic signals.", 9, False, C_MUTED),
        3
    ],
    [
        ("• Floating-Point Drift Trap: ", 9.5, True, C_WHITE),
        ("Hashing decoded pixels triggers false alarms across Ampere vs. Blackwell GPUs due to FMA rounding.", 9, False, C_MUTED),
        3
    ],
    [
        ("• Keyframe Blindspots & Mutable Logs: ", 9.5, True, C_WHITE),
        ("150–400 ms inter-frame gaps escape I-frame hashing; centralized logs remain mutable by admins.", 9, False, C_MUTED),
        0
    ]
])

# Shape 9 (Text 5): Left Middle Title
set_shape_text(slide2.shapes[9], [
    ("CRYPTOLEDGER: THREE INVESTIGATIVE ANSWERS", 11.5, True, C_ACCENT, 0)
])

# Shape 10 (Text 6): Left Middle Body
set_shape_text(slide2.shapes[10], [
    [
        ("1. WHO HANDLED IT? (Custody): ", 9.5, True, C_WHITE),
        ("FIDO2 biometric passkeys bind examiner identity; EVM smart contract (SessionAuditLedger.sol) anchors sessions.", 9, False, C_MUTED),
        3
    ],
    [
        ("2. DID IT CHANGE? (Integrity): ", 9.5, True, C_WHITE),
        ("Layer 1 Bitstream Merkle Tree seals raw H.264 NAL units (>5.4M pkts/s, 100% CPU/GPU determinism).", 9, False, C_MUTED),
        3
    ],
    [
        ("3. WHAT CHANGED? (Explanation): ", 9.5, True, C_WHITE),
        ("Layer 2 selectively decodes only divergent intervals via NVDEC for ArcFace (S>=0.72), OCR, & signal state auditing.", 9, False, C_MUTED),
        0
    ]
])

# Shape 21 (TextBox 21): Diagram Title above footer banner
set_shape_text(slide2.shapes[21], [
    ("CORE INNOVATION  •  DECOUPLED BITSTREAM FORENSIC PIPELINE", 10.5, True, C_ACCENT, 0)
], align=PP_ALIGN.CENTER)

# Shape 22 (Rounded Rectangle 17): Diagram Footer Banner
set_shape_text(slide2.shapes[22], [
    ("BITSTREAM → MERKLE → DIVERGENCE → SELECTIVE NVDEC → SQL DIGEST → EVM PROOF", 9.5, True, C_WHITE, 0)
], align=PP_ALIGN.CENTER)

# Shape 12 (Text 8): Bottom Right Architectural Centerpiece Banner
set_shape_text(slide2.shapes[12], [
    ("ARCHITECTURAL CENTERPIECE: DECOUPLED CRYPTOGRAPHIC & SEMANTIC LAYERS", 10.5, True, C_ACCENT, 2),
    ("Traditional: Video → Decode → AI → Hash  (Fails on hardware floating-point drift across GPUs)", 9, False, C_RED, 2),
    ("CryptoLedger: Video → BITSTREAM HASH → Merkle Root → Selective Decode ONLY on Mismatch → AI Audit", 9, True, C_GREEN, 0)
])

# Flowchart nodes on left (Shapes 13, 14, 15, 18, 19, 20)
set_shape_text(slide2.shapes[13], [("MULTI-VENDOR\nDVR/NVR", 9.5, True, C_WHITE, 0)], align=PP_ALIGN.CENTER)
set_shape_text(slide2.shapes[15], [("CYBERCHAIN\nTRUST LAYER", 9.5, True, C_WHITE, 0)], align=PP_ALIGN.CENTER)
set_shape_text(slide2.shapes[14], [("PEAKLEDGER\nFORENSIC CORE", 9.5, True, C_WHITE, 0)], align=PP_ALIGN.CENTER)
set_shape_text(slide2.shapes[18], [("LAYER 1\nMERKLE", 9, True, C_WHITE, 0)], align=PP_ALIGN.CENTER)
set_shape_text(slide2.shapes[19], [("LAYER 2\nGPU AI/ML", 9, True, C_WHITE, 0)], align=PP_ALIGN.CENTER)
set_shape_text(slide2.shapes[20], [("EVM CUSTODY\nPROOF", 9, True, C_WHITE, 0)], align=PP_ALIGN.CENTER)


# ==============================================================================
# SLIDE 3: TECHNICAL APPROACH - Two-Tier Pipeline & Security Mechanisms
# ==============================================================================
slide3 = prs.slides[2]

# Shape 7 (TextBox 2): Top Section Header
set_shape_text(slide3.shapes[7], [
    ("1. TECHNOLOGIES TO BE USED & ARCHITECTURAL STACK", 11.5, True, C_ACCENT, 0)
])

# Tech Card 1
set_shape_text(slide3.shapes[9], [("Programming Languages", 10, True, C_WHITE, 0)])
set_shape_text(slide3.shapes[10], [
    ("• Python 3.12 (CyberChain & UI)", 8.5, False, C_MUTED, 1),
    ("• C++20 / CUDA C++ (Core)", 8.5, False, C_MUTED, 1),
    ("• Solidity 0.8.20 (EVM Contracts)", 8.5, False, C_MUTED, 1),
    ("• Shell / Batch scripting", 8.5, False, C_MUTED, 0)
])

# Tech Card 2
set_shape_text(slide3.shapes[12], [("Frameworks & Libraries", 10, True, C_WHITE, 0)])
set_shape_text(slide3.shapes[13], [
    ("• PyQt6 (Examiner / Admin UI)", 8.5, False, C_MUTED, 1),
    ("• Web3.py & Foundry Anvil", 8.5, False, C_MUTED, 1),
    ("• FFmpeg libavformat / libavcodec", 8.5, False, C_MUTED, 0)
])

# Tech Card 3
set_shape_text(slide3.shapes[15], [("Databases & Storage", 10, True, C_WHITE, 0)])
set_shape_text(slide3.shapes[16], [
    ("• SQLite3 WAL (cyberchain.db)", 8.5, False, C_MUTED, 1),
    ("• Lock-free POSIX Shared Memory", 8.5, False, C_MUTED, 1),
    ("• Content-addressable CAS storage", 8.5, False, C_MUTED, 0)
])

# Tech Card 4
set_shape_text(slide3.shapes[18], [("Forensics & Processing", 10, True, C_WHITE, 0)])
set_shape_text(slide3.shapes[19], [
    ("• H.264 Annex B NAL demuxing", 8.5, False, C_MUTED, 1),
    ("• OpenSSL EVP SHA-256 Merkle", 8.5, False, C_MUTED, 1),
    ("• NVDEC (NV12) + TensorRT", 8.5, False, C_MUTED, 1),
    ("• ArcFace (512-D) + Levenshtein OCR", 8.5, False, C_MUTED, 0)
])

# Tech Card 5
set_shape_text(slide3.shapes[21], [("Blockchain & Security", 10, True, C_WHITE, 0)])
set_shape_text(slide3.shapes[22], [
    ("• W3C WebAuthn / FIDO2 Passkeys", 8.5, False, C_MUTED, 1),
    ("• Strict RBAC (Admin vs Examiner)", 8.5, False, C_MUTED, 1),
    ("• SessionAuditLedger.sol EVM custody", 8.5, False, C_MUTED, 0)
])

# Tech Card 6
set_shape_text(slide3.shapes[24], [("DevOps & Environment", 10, True, C_WHITE, 0)])
set_shape_text(slide3.shapes[25], [
    ("• Git / GitHub version control", 8.5, False, C_MUTED, 1),
    ("• Ubuntu Linux & Windows MSVC", 8.5, False, C_MUTED, 1),
    ("• VramProfile::LAPTOP (<2.5 GB)", 8.5, False, C_MUTED, 0)
])

# Shape 27 (TextBox 27): Methodology Section Header
set_shape_text(slide3.shapes[27], [
    ("2. METHODOLOGY AND PROCESS: 7-STAGE VERIFIABLE FORENSIC PIPELINE", 11.5, True, C_AMBER, 0)
])

# 7 Process Steps
set_shape_text(slide3.shapes[31], [("1. Input Demuxing", 9.5, True, C_WHITE, 0)])
set_shape_text(slide3.shapes[32], [
    ("• FFmpeg demuxes raw stream", 8.5, False, C_MUTED, 1),
    ("• H.264 Annex B canonicalized", 8.5, False, C_MUTED, 0)
])

set_shape_text(slide3.shapes[37], [("2. Read-Only Ingest", 9.5, True, C_WHITE, 0)])
set_shape_text(slide3.shapes[38], [
    ("• Original source untouched", 8.5, False, C_MUTED, 1),
    ("• Examiner custody session begins", 8.5, False, C_MUTED, 0)
])

set_shape_text(slide3.shapes[43], [("3. Layer 1 Sealing", 9.5, True, C_WHITE, 0)])
set_shape_text(slide3.shapes[44], [
    ("• SHA256(NAL||PTS||DTS||Idx)", 8.5, False, C_MUTED, 1),
    ("• All I/P/B packets Merkle sealed", 8.5, False, C_MUTED, 0)
])

set_shape_text(slide3.shapes[49], [("4. Zero-Decode Audit", 9.5, True, C_WHITE, 0)])
set_shape_text(slide3.shapes[50], [
    ("• >5.4M pkts/s audit (>120x speed)", 8.5, False, C_MUTED, 1),
    ("• Binary search locates divergence", 8.5, False, C_MUTED, 0)
])

set_shape_text(slide3.shapes[55], [("5. Layer 2 Deep Audit", 9.5, True, C_WHITE, 0)])
set_shape_text(slide3.shapes[56], [
    ("• Selective NVDEC decoding", 8.5, False, C_MUTED, 1),
    ("• ArcFace (S>=0.72), OCR (D<=1)", 8.5, False, C_MUTED, 0)
])

set_shape_text(slide3.shapes[61], [("6. Custody Anchoring", 9.5, True, C_WHITE, 0)])
set_shape_text(slide3.shapes[62], [
    ("• SQLTracker builds delta proof", 8.5, False, C_MUTED, 1),
    ("• recordSessionLogout on EVM", 8.5, False, C_MUTED, 0)
])

set_shape_text(slide3.shapes[67], [("7. NIST Reporting", 9.5, True, C_WHITE, 0)])
set_shape_text(slide3.shapes[68], [
    ("• Standalone NIST SP 800-86 HTML", 8.5, False, C_MUTED, 1),
    ("• Base64 evidence & Merkle proofs", 8.5, False, C_MUTED, 0)
])

# Bottom Callout: Evidence Separation Principle
set_shape_text(slide3.shapes[90], [
    ("EVIDENCE SEPARATION PRINCIPLE: Heavy surveillance video stays in local read-only evidence vaults. Blockchain strictly records lightweight cryptographic state proofs, examiner signatures, and session lifecycle logs.", 9, True, C_WHITE, 0)
])


# ==============================================================================
# SLIDE 4: FEASIBILITY & VIABILITY - Hardware Bounds, Threat Model & Validation
# ==============================================================================
slide4 = prs.slides[3]

# Left Top: Technical Feasibility
set_shape_text(slide4.shapes[8], [("TECHNICAL FEASIBILITY & HARDWARE BOUNDARIES", 11, True, C_ACCENT, 0)])
set_shape_text(slide4.shapes[9], [
    ("• Tier 1 Portable (CPU-Agnostic): Layer 1 Merkle hashing requires zero GPU; demuxing & OpenSSL EVP run natively on standard laptops.", 8.5, False, C_WHITE, 3),
    ("• Tier 2 Forensic Profile (<2.5 GB VRAM): VramProfile::LAPTOP uses throttled double-buffering & direct NV12 ingestion tested on RTX 3050.", 8.5, False, C_WHITE, 0)
])

# Left Bottom: Threat Model
set_shape_text(slide4.shapes[11], [("THREAT MODEL & FORENSIC BOUNDARIES", 11, True, C_AMBER, 0)])
set_shape_text(slide4.shapes[12], [
    ("• TRUSTED: Secure acquisition station, SHA-256 cryptographic primitives, examiner FIDO2 biometric token.", 8.5, False, C_WHITE, 3),
    ("• UNTRUSTED: Suspect video files, network pipelines, host OS clock drift, local filesystem modifications.", 8.5, False, C_WHITE, 0)
])

# Right Top: Implemented Capabilities
set_shape_text(slide4.shapes[13], [("IMPLEMENTED CAPABILITIES & VALIDATION", 11, True, C_ACCENT, 0)])
set_shape_text(slide4.shapes[14], [
    ("• Multi-Vendor Ingestion: Extensible C++20 adapters support standard DVR/NVR H.264 streams & containers.", 9, False, C_WHITE, 2),
    ("• Dual-Layer Verification: Layer 1 bitstream Merkle (>5.4M pkts/s) + Layer 2 selective NVDEC/AI audit.", 9, False, C_WHITE, 2),
    ("• Non-Repudiable Custody: FIDO2 WebAuthn + SessionAuditLedger.sol on-chain session state anchoring.", 9, False, C_WHITE, 2),
    ("• 100% Test Pass Rate: 66/66 automated test suites passing (7/7 C++ core + 59/59 Python integration).", 9, False, C_WHITE, 0)
])

# Right Bottom: Key Mitigations
set_shape_text(slide4.shapes[16], [("KEY FORENSIC MITIGATIONS", 11, True, C_AMBER, 0)])
set_shape_text(slide4.shapes[17], [
    ("• Bitwise vs Semantic Divergence: Re-encoding alerts Layer 1 mismatch, falls back to Layer 2 semantic similarity.", 9, False, C_WHITE, 2),
    ("• Rogue Admin Defense: Local SQLite tampering detected instantly via EVM smart contract block-hash verification.", 9, False, C_WHITE, 2),
    ("• Floating-Point Safety: Bitstream hashing operates on pure-integer byte streams, eliminating GPU drift.", 9, False, C_WHITE, 2),
    ("• Non-Keyframe Dilemma: 100% of I, P, and B packets hashed, eliminating inter-frame blindspots.", 9, False, C_WHITE, 0)
])

# Bottom Banner
set_shape_text(slide4.shapes[19], [
    ("Validated Prototype: 5–6 OEM stream adapters + 66/66 automated test suites passing (7 C++ core + 59 Python integration).", 9.5, True, C_GREEN, 0)
], align=PP_ALIGN.CENTER)


# ==============================================================================
# SLIDE 5: IMPACT AND BENEFITS - Measurable Operational Gains & Legal Framing
# ==============================================================================
slide5 = prs.slides[4]

# Left Top: Current State
set_shape_text(slide5.shapes[6], [("CURRENT FORENSIC STATE & BOTTLENECKS", 10.5, True, C_RED, 0)])
set_shape_text(slide5.shapes[7], [
    ("• Fragmented vendor tools & proprietary codecs delay investigations.", 9, False, C_MUTED, 2),
    ("• Keyframe-only hashing creates 150–400ms blindspots; mutable local logs risk repudiation.", 9, False, C_MUTED, 0)
])

# Left Middle: CryptoLedger Operational Breakthrough
set_shape_text(slide5.shapes[8], [("CRYPTOLEDGER: MEASURABLE OPERATIONAL BREAKTHROUGH", 10.5, True, C_ACCENT, 0)])
set_shape_text(slide5.shapes[9], [
    ("• Lightning Verification Speed (>120x Real-Time): Zero-decode Layer 1 checks 10 hrs (864k pkts) in <160 ms.", 9, False, C_WHITE, 2),
    ("• >98% GPU Workload Reduction: Selective NVDEC hardware decodes ONLY divergent slices.", 9, False, C_WHITE, 2),
    ("• >93.7% Storage Footprint Reduction: Track-Aware Crop state machine commits crops on key events.", 9, False, C_WHITE, 2),
    ("• Grounded Legal Custody (BSA 2023 Sec 63): FIDO2 biometrics + EVM smart contract provenance.", 9, False, C_WHITE, 0)
])

# Left Bottom: Beneficiaries & Legal Positioning
set_shape_text(slide5.shapes[10], [("INSTITUTIONAL VALUE FOR FORENSIC LABS & LEAs", 10.5, True, C_AMBER, 0)])
set_shape_text(slide5.shapes[16], [
    ("• State Police Cyber Cells & FSL: Instant triage of CCTV evidence from multi-vendor sources.", 8.5, False, C_WHITE, 1),
    ("• Defense & Prosecution: Objective mathematical proof of packet alteration without vendor software.", 8.5, False, C_WHITE, 1),
    ("• Judicial Evidentiary Record: Standalone NIST SP 800-86 HTML report with base64 embedded visual evidence.", 8.5, False, C_WHITE, 0)
])

# Right Stat Badges
set_shape_text(slide5.shapes[12], [(">120x\nSPEED", 10, True, C_WHITE, 0)], align=PP_ALIGN.CENTER)
set_shape_text(slide5.shapes[13], [(">98%\nGPU SAVING", 10, True, C_WHITE, 0)], align=PP_ALIGN.CENTER)
set_shape_text(slide5.shapes[14], [("100%\nCUSTODY", 10, True, C_WHITE, 0)], align=PP_ALIGN.CENTER)

# Stat Footer Note
set_shape_text(slide5.shapes[15], [
    ("Scales: portable laptop GPU profile (<2.5 GB VRAM) → forensic laboratory / server deployment", 8.5, False, C_MUTED, 0)
], align=PP_ALIGN.CENTER)


# ==============================================================================
# SLIDE 6: RESEARCH AND REFERENCES - Standards, Statutes & Foundations
# ==============================================================================
slide6 = prs.slides[5]

# Card 1 (Top Left): DVR / Video Forensics
set_shape_text(slide6.shapes[6], [("DVR / Video Forensics", 10.5, True, C_ACCENT, 0)])
set_shape_text(slide6.shapes[7], [
    ("• SWGDE 17-V-002-1.4: Best Practices for Data Acquisition from Digital Video Recorders", 8.5, False, C_WHITE, 2),
    ("• NIST OSAC: Forensic Science Standards Registry for Video Analysis & Integrity", 8.5, False, C_WHITE, 2),
    ("• ITU-T H.264 Annex B: Canonical NAL byte-stream demuxing and start code standardization", 8.5, False, C_WHITE, 0)
])

# Card 2 (Bottom Left): Digital Forensics & Chain of Custody
set_shape_text(slide6.shapes[8], [("Digital Forensics & Chain of Custody", 10.5, True, C_AMBER, 0)])
set_shape_text(slide6.shapes[9], [
    ("• Bharatiya Sakshya Adhiniyam (BSA) 2023, Section 63: Electronic record admissibility", 8.5, False, C_WHITE, 2),
    ("• Indian Evidence Act Section 65B: Electronic evidence certification standards", 8.5, False, C_WHITE, 2),
    ("• NIST SP 800-86: Guide to Integrating Forensic Techniques into Incident Response", 8.5, False, C_WHITE, 0)
])

# Card 3 (Top Right): Cryptography & Blockchain
set_shape_text(slide6.shapes[10], [("Cryptography & Blockchain", 10.5, True, C_ACCENT, 0)])
set_shape_text(slide6.shapes[11], [
    ("• FIDO2 / W3C WebAuthn CTAP2: Phishing-resistant biometric passkeys (ES256/RS256)", 8.5, False, C_WHITE, 2),
    ("• Solidity 0.8.20 EVM: SessionAuditLedger.sol non-repudiable on-chain session custody", 8.5, False, C_WHITE, 2),
    ("• RFC 6962 & FIPS 180-4: SHA-256 Merkle trees with O(log N) cryptographic inclusion proofs", 8.5, False, C_WHITE, 0)
])

# Card 4 (Bottom Right): Video Analytics & Hardware Acceleration
set_shape_text(slide6.shapes[12], [("Video Analytics & Hardware Acceleration", 10.5, True, C_AMBER, 0)])
set_shape_text(slide6.shapes[13], [
    ("• NVIDIA NVDEC & TensorRT: Zero-copy hardware decoding into GPU VRAM (NV12)", 8.5, False, C_WHITE, 2),
    ("• ArcFace (CVPR 2019): 512-D deep facial embeddings with cosine threshold S >= 0.72", 8.5, False, C_WHITE, 2),
    ("• Levenshtein Distance (1966): Dynamic programming alphanumeric OCR plate audit (D <= 1)", 8.5, False, C_WHITE, 2),
    ("• OpenSSL EVP & POSIX SHM: High-speed lock-free IPC telemetry at 60 FPS", 8.5, False, C_WHITE, 0)
])

# Summary Box
set_shape_text(slide6.shapes[15], [
    ("SUMMARY SPECIFICATION: CryptoLedger establishes an integrated, verifiable forensic pipeline bridging read-only bitstream ingestion, pure-integer Merkle verification, selective semantic explanation, and FIDO2/EVM custody anchoring.", 9, True, C_WHITE, 0)
])

# Footer Pill
set_shape_text(slide6.shapes[16], [
    ("SWGDE 17-V-002-1.4 • NIST SP 800-86 • NIST FIPS 180-4 • BSA 2023 Sec 63 • W3C WebAuthn • RFC 6962", 8.5, True, C_ACCENT, 0)
], align=PP_ALIGN.CENTER)

prs.save(PPTX_PATH)
print("SUCCESS: Rectified CryptoLedger_SIH2026.pptx with clean, perfectly proportioned layouts!")
