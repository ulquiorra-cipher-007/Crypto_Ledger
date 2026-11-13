#!/usr/bin/env python3
"""
Render high-resolution, professionally styled PeakLedger Two-Layer Architecture Flowchart.
Outputs to evidence/peakledger_architecture_flowchart.png
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont

def get_font(size, bold=False, mono=False):
    try:
        if mono:
            font_path = "/usr/share/fonts/truetype/ubuntu/UbuntuSansMono-Italic[wght].ttf"
            if not os.path.exists(font_path):
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
        elif bold:
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if not os.path.exists(font_path):
                font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        else:
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if not os.path.exists(font_path):
                font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
        return ImageFont.truetype(font_path, size)
    except Exception:
        return ImageFont.load_default()

def draw_rounded_rect(draw, xy, rad, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=rad, fill=fill, outline=outline, width=width)

def draw_glow_box(draw, xy, rad, fill, border_color, glow_color, width=2):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle((x1-2, y1-2, x2+2, y2+2), radius=rad+2, outline=glow_color, width=1)
    draw.rounded_rectangle((x1, y1, x2, y2), radius=rad, fill=fill, outline=border_color, width=width)

def draw_arrow(draw, start, end, color=(56, 189, 248), width=2, arrow_size=7):
    x1, y1 = start
    x2, y2 = end
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
    
    if x1 == x2: # Vertical
        if y2 > y1: # Down
            points = [(x2, y2), (x2 - arrow_size, y2 - arrow_size * 1.5), (x2 + arrow_size, y2 - arrow_size * 1.5)]
        else: # Up
            points = [(x2, y2), (x2 - arrow_size, y2 + arrow_size * 1.5), (x2 + arrow_size, y2 + arrow_size * 1.5)]
    elif y1 == y2: # Horizontal
        if x2 > x1: # Right
            points = [(x2, y2), (x2 - arrow_size * 1.5, y2 - arrow_size), (x2 - arrow_size * 1.5, y2 + arrow_size)]
        else: # Left
            points = [(x2, y2), (x2 + arrow_size * 1.5, y2 - arrow_size), (x2 + arrow_size * 1.5, y2 + arrow_size)]
    else:
        angle = math.atan2(y2 - y1, x2 - x1)
        p1 = (x2 - arrow_size * 1.5 * math.cos(angle - math.pi / 6),
              y2 - arrow_size * 1.5 * math.sin(angle - math.pi / 6))
        p2 = (x2 - arrow_size * 1.5 * math.cos(angle + math.pi / 6),
              y2 - arrow_size * 1.5 * math.sin(angle + math.pi / 6))
        points = [(x2, y2), p1, p2]
    draw.polygon(points, fill=color)

def generate_flowchart():
    W, H = 2000, 1150
    img = Image.new("RGB", (W, H), (11, 15, 25))
    draw = ImageDraw.Draw(img)

    # Subtle gradient background
    for y in range(H):
        ratio = y / float(H)
        r = int(11 + 6 * ratio)
        g = int(15 + 10 * ratio)
        b = int(25 + 20 * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Grid background
    for x in range(0, W, 40):
        draw.line([(x, 0), (x, H)], fill=(16, 24, 40), width=1)
    for y in range(0, H, 40):
        draw.line([(0, y), (W, y)], fill=(16, 24, 40), width=1)

    # Fonts
    f_title = get_font(25, bold=True)
    f_subtitle = get_font(13, bold=False)
    f_badge = get_font(11, bold=True)
    f_header = get_font(15, bold=True)
    f_subhead = get_font(12, bold=True)
    f_body = get_font(10, bold=False)
    f_body_b = get_font(10, bold=True)
    f_mono = get_font(9, mono=True)
    f_stat = get_font(10, bold=True)

    # Header Bar
    draw_glow_box(draw, (30, 20, W - 30, 110), 12, (15, 23, 42), (37, 99, 235), (30, 58, 138), width=2)
    
    # Title & Subtitle
    draw.text((50, 32), "PEAKLEDGER CORE", fill=(56, 189, 248), font=f_title)
    draw.text((310, 34), "|  Two-Layer Decoupled Video Forensic Backend Subsystem", fill=(241, 245, 249), font=f_title)
    draw.text((50, 75), "Smart India Hackathon (SIH): High-Speed Bitstream Merkle Verification, AI Deepfake Localization & BSA 2023 Admissibility", fill=(148, 163, 184), font=f_subtitle)

    # Badges on top right (positioned cleanly without overlap)
    badges = [
        ("C++20 / CUDA 12", (16, 185, 129)),
        ("TensorRT 11", (14, 165, 233)),
        ("OpenSSL EVP", (239, 68, 68)),
        ("BSA 2023 Sec 63", (168, 85, 247))
    ]
    bx = W - 50
    for b_text, b_col in reversed(badges):
        tw = int(draw.textlength(b_text, font=f_badge)) + 18
        bx -= tw + 10
        draw_rounded_rect(draw, (bx, 38, bx + tw, 64), 6, (30, 41, 59), outline=b_col, width=1)
        draw.text((bx + 9, 44), b_text, fill=(241, 245, 249), font=f_badge)

    # -------------------------------------------------------------
    # SECTION 1: INGESTION STAGE (Left Column: X 40 to 330)
    # -------------------------------------------------------------
    draw_glow_box(draw, (40, 140, 330, 730), 12, (15, 23, 42), (56, 189, 248), (30, 58, 138), width=2)
    draw.text((60, 155), "SURVEILLANCE INGESTION", fill=(56, 189, 248), font=f_header)
    draw.text((60, 178), "Multi-Resolution Input Feed", fill=(148, 163, 184), font=f_stat)

    v_boxes = [
        ("CCTV Fixed Stream", "1080p FHD @ 30 FPS", (30, 41, 59)),
        ("Traffic 4K Stream", "3840x2160 UHD @ 25 Mbps", (30, 41, 59)),
        ("Mobile / WebRTC", "480p SD / H.264 WhatsApp", (30, 41, 59)),
        ("Police Evidence Store", "MP4 / MKV / Annex B Raw", (30, 41, 59))
    ]
    vy = 215
    for title, desc, bg in v_boxes:
        draw_rounded_rect(draw, (55, vy, 315, vy + 54), 8, bg, outline=(51, 65, 85), width=1)
        draw.text((70, vy + 8), f"▶ {title}", fill=(248, 250, 252), font=f_subhead)
        draw.text((70, vy + 28), desc, fill=(148, 163, 184), font=f_body)
        vy += 68

    draw_glow_box(draw, (55, 510, 315, 710), 10, (23, 37, 84), (59, 130, 246), (30, 58, 138), width=2)
    draw.text((70, 525), "ITU-T H.264 Annex B", fill=(96, 165, 250), font=f_subhead)
    draw.text((70, 545), "Canonical Demuxer Engine", fill=(248, 250, 252), font=f_header)
    draw.text((70, 575), "• 100% Ingestion (I, P, B Frames)", fill=(203, 213, 225), font=f_body)
    draw.text((70, 595), "• Strips Container Jitter & Headers", fill=(203, 213, 225), font=f_body)
    draw.text((70, 615), "• 4-Byte Start Codes (0x00000001)", fill=(203, 213, 225), font=f_body)
    draw.text((70, 635), "• Extracts PTS / DTS Timestamps", fill=(203, 213, 225), font=f_body)
    draw.text((70, 655), "• Zero-Copy Bitstream Dispatch", fill=(203, 213, 225), font=f_body)
    draw.text((70, 680), "RATE: >5.4M Packets / Second", fill=(52, 211, 153), font=f_stat)

    draw_arrow(draw, (185, 487), (185, 510), color=(59, 130, 246), width=2)

    # Split Arrows from Demuxer to Layer 1 and Layer 2
    draw.line([(315, 560), (370, 560), (370, 280), (410, 280)], fill=(14, 165, 233), width=3)
    draw_arrow(draw, (400, 280), (410, 280), color=(14, 165, 233), width=3)
    draw.line([(315, 660), (370, 660), (370, 680), (410, 680)], fill=(16, 185, 129), width=3)
    draw_arrow(draw, (400, 680), (410, 680), color=(16, 185, 129), width=3)

    # -------------------------------------------------------------
    # SECTION 2: LAYER 1 - BITSTREAM MERKLE TREE (Top Row: Y 140 to 450)
    # -------------------------------------------------------------
    draw_glow_box(draw, (410, 140, 1470, 450), 12, (15, 23, 42), (14, 165, 233), (12, 74, 110), width=2)
    draw.text((430, 155), "LAYER 1: BITSTREAM MERKLE TREE CRYPTOGRAPHIC ANCHOR (ZERO-DECODE PIPELINE)", fill=(56, 189, 248), font=f_header)
    draw.text((430, 178), "Pure Integer Determinism • Zero Forensic Blindspots • Cross-GPU / Cross-CPU Identical Hashes", fill=(148, 163, 184), font=f_stat)

    # Box 1.1: Canonical NAL Leaf Hasher
    draw_glow_box(draw, (430, 210, 670, 420), 10, (30, 41, 59), (56, 189, 248), (14, 165, 233), width=1)
    draw.text((445, 225), "Canonical NAL Hasher", fill=(248, 250, 252), font=f_subhead)
    draw.text((445, 245), "OpenSSL EVP SHA-256", fill=(96, 165, 250), font=f_stat)
    draw_rounded_rect(draw, (440, 270, 660, 335), 6, (15, 23, 42), outline=(51, 65, 85), width=1)
    draw.text((448, 280), "H_leaf = SHA256(", fill=(52, 211, 153), font=f_mono)
    draw.text((455, 295), "NAL || PTS_int64 ||", fill=(52, 211, 153), font=f_mono)
    draw.text((455, 310), "DTS || LeafIndex )", fill=(52, 211, 153), font=f_mono)
    draw.text((445, 345), "• Ingests 100% of Packets", fill=(203, 213, 225), font=f_body)
    draw.text((445, 365), "• I-, P-, and B-Frames Bound", fill=(203, 213, 225), font=f_body)
    draw.text((445, 385), "• Eliminates Temporal Splicing", fill=(203, 213, 225), font=f_body)

    draw_arrow(draw, (670, 315), (710, 315), color=(14, 165, 233), width=2)

    # Box 1.2: Balanced Merkle Tree
    draw_glow_box(draw, (710, 210, 950, 420), 10, (30, 41, 59), (56, 189, 248), (14, 165, 233), width=1)
    draw.text((725, 225), "Balanced Binary Tree", fill=(248, 250, 252), font=f_subhead)
    draw.text((725, 245), "O(log N) Cryptographic Inclusion", fill=(96, 165, 250), font=f_stat)
    draw_rounded_rect(draw, (720, 270, 940, 335), 6, (15, 23, 42), outline=(51, 65, 85), width=1)
    draw.text((795, 275), "[ H_root ]", fill=(245, 158, 11), font=f_mono)
    draw.text((775, 292), "┌──────┴──────┐", fill=(148, 163, 184), font=f_mono)
    draw.text((750, 305), "[ H_01 ]     [ H_23 ]", fill=(96, 165, 250), font=f_mono)
    draw.text((735, 320), "┌───┴───┐   ┌───┴───┐", fill=(148, 163, 184), font=f_mono)
    draw.text((725, 345), "• Logarithmic Audit Traversal", fill=(203, 213, 225), font=f_body)
    draw.text((725, 365), "• Immediate Interval Isolation", fill=(203, 213, 225), font=f_body)
    draw.text((725, 385), "• Exact Frame Divergence Pinpoint", fill=(203, 213, 225), font=f_body)

    draw_arrow(draw, (950, 315), (990, 315), color=(14, 165, 233), width=2)

    # Box 1.3: 32-Byte Immutable Root
    draw_glow_box(draw, (990, 210, 1200, 420), 10, (30, 41, 59), (56, 189, 248), (14, 165, 233), width=1)
    draw.text((1005, 225), "Immutable Merkle Root", fill=(248, 250, 252), font=f_subhead)
    draw.text((1005, 245), "32-Byte Master Cryptographic Hash", fill=(96, 165, 250), font=f_stat)
    draw_rounded_rect(draw, (1000, 270, 1190, 335), 6, (15, 23, 42), outline=(51, 65, 85), width=1)
    draw.text((1010, 280), "0x9f83...4c21", fill=(245, 158, 11), font=f_mono)
    draw.text((1010, 298), "Sealed in SQLite &", fill=(148, 163, 184), font=f_mono)
    draw.text((1010, 315), "BSA Sec 63 Affidavit", fill=(52, 211, 153), font=f_mono)
    draw.text((1005, 345), "• Non-Repudiable Evidence", fill=(203, 213, 225), font=f_body)
    draw.text((1005, 365), "• Zero Floating-Point Drift", fill=(203, 213, 225), font=f_body)
    draw.text((1005, 385), "• 100% Cross-GPU Determinism", fill=(203, 213, 225), font=f_body)

    draw_arrow(draw, (1200, 315), (1240, 315), color=(14, 165, 233), width=2)

    # Box 1.4: Zero-Decode Audit
    draw_glow_box(draw, (1240, 210, 1450, 420), 10, (19, 78, 74), (20, 184, 166), (15, 118, 110), width=2)
    draw.text((1255, 225), "Zero-Decode Audit", fill=(248, 250, 252), font=f_subhead)
    draw.text((1255, 245), "Ultra-Rapid Verification", fill=(45, 212, 191), font=f_stat)
    draw_rounded_rect(draw, (1250, 270, 1440, 335), 6, (15, 23, 42), outline=(20, 184, 166), width=1)
    draw.text((1260, 280), "Speed: >100x Real-time", fill=(52, 211, 153), font=f_mono)
    draw.text((1260, 298), "GPU Decode: 0% Wasted", fill=(56, 189, 248), font=f_mono)
    draw.text((1260, 315), "Status: Bitwise Matched", fill=(245, 158, 11), font=f_mono)
    draw.text((1255, 345), "• Clean files verified in sec", fill=(203, 213, 225), font=f_body)
    draw.text((1255, 365), "• Bypasses pixel decoding", fill=(203, 213, 225), font=f_body)
    draw.text((1255, 385), "• Invokes Layer 2 ONLY on Delta", fill=(245, 158, 11), font=f_body_b)

    # -------------------------------------------------------------
    # SECTION 3: LAYER 2 - FORENSIC INTELLIGENCE (Bottom Row: Y 475 to 840)
    # -------------------------------------------------------------
    draw_glow_box(draw, (410, 475, 1470, 840), 12, (15, 23, 42), (16, 185, 129), (6, 78, 59), width=2)
    draw.text((430, 490), "LAYER 2: FORENSIC INTELLIGENCE & MULTI-MODAL ATTRIBUTE ENGINE (CAS LEDGER)", fill=(52, 211, 153), font=f_header)
    draw.text((430, 513), "Decoupled From Verification Hashing • Invoked on Ingestion & Divergence • VRAM Zero Host Copies", fill=(148, 163, 184), font=f_stat)

    # Box 2.1: Hardware NVDEC
    draw_glow_box(draw, (430, 545, 610, 810), 10, (30, 41, 59), (52, 211, 153), (6, 78, 59), width=1)
    draw.text((445, 560), "NVIDIA NVDEC", fill=(248, 250, 252), font=f_subhead)
    draw.text((445, 580), "Hardware Decoder", fill=(52, 211, 153), font=f_stat)
    draw.text((445, 610), "• Direct NV12 Surfaces", fill=(203, 213, 225), font=f_body)
    draw.text((445, 630), "• Zero Host RAM Copy", fill=(203, 213, 225), font=f_body)
    draw.text((445, 650), "• NV12 Pitch: W x H*1.5", fill=(203, 213, 225), font=f_body)
    draw.text((445, 670), "• Native Motion Vectors", fill=(203, 213, 225), font=f_body)
    draw.text((445, 690), "• VRAM Bound Pipelines", fill=(203, 213, 225), font=f_body)
    draw.text((445, 715), "VRAM FOOTPRINT:", fill=(245, 158, 11), font=f_stat)
    draw.text((445, 735), "RTX 3050: < 2.5 GB", fill=(52, 211, 153), font=f_stat)

    draw_arrow(draw, (610, 675), (640, 675), color=(52, 211, 153), width=2)

    # Box 2.2: CUDA Preprocess & TensorRT
    draw_glow_box(draw, (640, 545, 840, 810), 10, (30, 41, 59), (52, 211, 153), (6, 78, 59), width=1)
    draw.text((655, 560), "CUDA & TensorRT", fill=(248, 250, 252), font=f_subhead)
    draw.text((655, 580), "Double-Buffered Engine", fill=(52, 211, 153), font=f_stat)
    draw.text((655, 610), "• Bilinear Preprocessing", fill=(203, 213, 225), font=f_body)
    draw.text((655, 630), "  NV12 -> NCHW Float32", fill=(148, 163, 184), font=f_mono)
    draw.text((655, 650), "• YOLOv8/11 Engine (FP16)", fill=(203, 213, 225), font=f_body)
    draw.text((655, 670), "• 640x640 Feature Pyramids", fill=(203, 213, 225), font=f_body)
    draw.text((655, 690), "• Double-Buffered Streams", fill=(203, 213, 225), font=f_body)
    draw.text((655, 710), "• Zero CPU Pipeline Stalls", fill=(203, 213, 225), font=f_body)
    draw.text((655, 735), "THROUGHPUT: >60 FPS", fill=(52, 211, 153), font=f_stat)

    draw_arrow(draw, (840, 675), (870, 675), color=(52, 211, 153), width=2)

    # Box 2.3: Motion Tracker & Cyclist Pairing
    draw_glow_box(draw, (870, 545, 1050, 810), 10, (30, 41, 59), (52, 211, 153), (6, 78, 59), width=1)
    draw.text((885, 560), "Centroid Tracker", fill=(248, 250, 252), font=f_subhead)
    draw.text((885, 580), "Hungarian Data Association", fill=(52, 211, 153), font=f_stat)
    draw.text((885, 610), "• Multi-Target Tracking", fill=(203, 213, 225), font=f_body)
    draw.text((885, 630), "• Person-Bicycle Pairing", fill=(203, 213, 225), font=f_body)
    draw.text((885, 650), "  IoU Overlap >= 0.40", fill=(148, 163, 184), font=f_mono)
    draw.text((885, 670), "• Cyclist Entity Fusion", fill=(203, 213, 225), font=f_body)
    draw.text((885, 690), "• Trajectory Continuity", fill=(203, 213, 225), font=f_body)
    draw.text((885, 710), "• Track Birth / Death State", fill=(203, 213, 225), font=f_body)
    draw.text((885, 735), "Max Inactive: 10 Frames", fill=(245, 158, 11), font=f_stat)

    draw_arrow(draw, (1050, 675), (1080, 675), color=(52, 211, 153), width=2)

    # Box 2.4: Multi-Modal Attribute Extractors
    draw_glow_box(draw, (1080, 545, 1270, 810), 10, (30, 41, 59), (52, 211, 153), (6, 78, 59), width=1)
    draw.text((1095, 560), "Multi-Modal Intelligence", fill=(248, 250, 252), font=f_subhead)
    draw.text((1095, 580), "Biometrics, OCR & States", fill=(52, 211, 153), font=f_stat)
    draw.text((1095, 610), "• ArcFace 512-D Face (S>=0.72)", fill=(248, 250, 252), font=f_body_b)
    draw.text((1095, 630), "  Resilient to 480p CCTV downscale", fill=(148, 163, 184), font=f_mono)
    draw.text((1095, 650), "• License OCR (Levenshtein D<=1)", fill=(248, 250, 252), font=f_body_b)
    draw.text((1095, 670), "  Glare/blur tolerant plate audit", fill=(148, 163, 184), font=f_mono)
    draw.text((1095, 690), "• Traffic Signal & Countdown", fill=(248, 250, 252), font=f_body_b)
    draw.text((1095, 710), "  RED/AMBER/GRN, |dt|<=1s", fill=(148, 163, 184), font=f_mono)
    draw.text((1095, 730), "• Pedestrian Clothing Palette", fill=(248, 250, 252), font=f_body_b)
    draw.text((1095, 750), "  Torso/Lower 10 HSV Bins", fill=(148, 163, 184), font=f_mono)

    draw_arrow(draw, (1270, 675), (1300, 675), color=(52, 211, 153), width=2)

    # Box 2.5: Track-Aware Crop Optimizer
    draw_glow_box(draw, (1300, 545, 1450, 810), 10, (19, 78, 74), (20, 184, 166), (15, 118, 110), width=2)
    draw.text((1315, 560), "Crop Optimizer", fill=(248, 250, 252), font=f_subhead)
    draw.text((1315, 580), "Event-Driven Storage", fill=(45, 212, 191), font=f_stat)
    draw.text((1315, 610), "• Event Commits Only:", fill=(203, 213, 225), font=f_body)
    draw.text((1315, 630), "  1. Track Birth", fill=(52, 211, 153), font=f_stat)
    draw.text((1315, 650), "  2. Conf Jump >= +0.15", fill=(52, 211, 153), font=f_stat)
    draw.text((1315, 675), "• Intermediate Frames:", fill=(203, 213, 225), font=f_body)
    draw.text((1315, 695), "  Lightweight BBox only", fill=(148, 163, 184), font=f_mono)
    draw.text((1315, 720), "STORAGE SAVINGS:", fill=(245, 158, 11), font=f_stat)
    draw.text((1315, 740), ">93.7% Reduction!", fill=(52, 211, 153), font=f_header)

    # -------------------------------------------------------------
    # SECTION 4: STORAGE, IPC & DELIVERABLES (Right Column: X 1510 to 1960)
    # -------------------------------------------------------------
    draw_glow_box(draw, (1510, 140, 1960, 840), 12, (15, 23, 42), (168, 85, 247), (88, 28, 135), width=2)
    draw.text((1530, 155), "INTEGRATION, IPC & EVIDENCE", fill=(192, 132, 252), font=f_header)
    draw.text((1530, 178), "Lock-Free POSIX SHM • ACID SQLite • Legal Compliance", fill=(148, 163, 184), font=f_stat)

    # Interface 1: Lock-Free Shared Memory Ring Buffer
    draw_glow_box(draw, (1530, 210, 1940, 370), 10, (30, 41, 59), (168, 85, 247), (88, 28, 135), width=1)
    draw.text((1545, 222), "Lock-Free POSIX Shared Memory", fill=(248, 250, 252), font=f_subhead)
    draw.text((1545, 240), "IPC Channel: /PeakLedger_shm (164,608 Bytes)", fill=(192, 132, 252), font=f_stat)
    draw.text((1545, 265), "• 256 Slots of 640-Byte Cache-Aligned TelemetryFrame", fill=(203, 213, 225), font=f_body)
    draw.text((1545, 285), "• Atomic acquire/release counters (Zero False Sharing)", fill=(203, 213, 225), font=f_body)
    draw.text((1545, 305), "• Live 32x16 Macro-Grid Residual Energy Heatmaps", fill=(203, 213, 225), font=f_body)
    draw.text((1545, 325), "• 60+ FPS Live Video Telemetry to PyQt6 / Web UI", fill=(52, 211, 153), font=f_stat)
    draw.text((1545, 345), "• Sub-Microsecond Inter-Process Latency (< 0.8 us)", fill=(56, 189, 248), font=f_stat)

    # Interface 2: ACID SQLite Content-Addressable Database
    draw_glow_box(draw, (1530, 390, 1940, 560), 10, (30, 41, 59), (168, 85, 247), (88, 28, 135), width=1)
    draw.text((1545, 402), "ACID SQLite Forensic CAS Ledger", fill=(248, 250, 252), font=f_subhead)
    draw.text((1545, 420), "evidence/ledger.db (WAL Mode, synchronous=NORMAL)", fill=(192, 132, 252), font=f_stat)
    draw.text((1545, 445), "• forensic_frame_metadata (ArcFace, OCR, Signals)", fill=(203, 213, 225), font=f_body)
    draw.text((1545, 465), "• idx_metadata_video_pts on (video_id, pts)", fill=(148, 163, 184), font=f_mono)
    draw.text((1545, 485), "• idx_metadata_video_track on (video_id, track_id)", fill=(148, 163, 184), font=f_mono)
    draw.text((1545, 505), "• Storage: ~24.3 MB / Hour (1080p) -> ~1.1% Video Size", fill=(52, 211, 153), font=f_stat)
    draw.text((1545, 525), "• Ultra-Lean on 4K Streams: ~0.23% Video Size", fill=(56, 189, 248), font=f_stat)

    # Interface 3: Courtroom Deliverables & Legal Compliance
    draw_glow_box(draw, (1530, 580, 1940, 810), 10, (19, 78, 74), (20, 184, 166), (15, 118, 110), width=2)
    draw.text((1545, 595), "Courtroom Admissible Deliverables", fill=(248, 250, 252), font=f_subhead)
    draw.text((1545, 615), "Zero-Dependency Standalone Artifacts", fill=(45, 212, 191), font=f_stat)
    draw.text((1545, 640), "1. Standalone HTML Dossier (Forensic_Report.html):", fill=(248, 250, 252), font=f_body_b)
    draw.text((1560, 658), "Self-contained single HTML with embedded base64 evidence", fill=(148, 163, 184), font=f_mono)
    draw.text((1545, 680), "2. Machine Audit Log (tamper_audit_report.json):", fill=(248, 250, 252), font=f_body_b)
    draw.text((1560, 698), "Exact divergent intervals [PTS_start, PTS_end] & deltas", fill=(148, 163, 184), font=f_mono)
    draw.text((1545, 725), "LEGAL ADMISSIBILITY COMPLIANCE:", fill=(245, 158, 11), font=f_stat)
    draw.text((1545, 745), "✓ Bharatiya Sakshya Adhiniyam 2023, Section 63", fill=(52, 211, 153), font=f_stat)
    draw.text((1545, 765), "✓ Indian Evidence Act Section 65B & NIST SP 800-86", fill=(52, 211, 153), font=f_stat)
    draw.text((1545, 785), "✓ US Federal Rules of Evidence Rule 902(13) / 902(14)", fill=(52, 211, 153), font=f_stat)

    # Connecting arrows from Layer 1 / Layer 2 to Section 4
    draw.line([(1450, 315), (1480, 315), (1480, 290), (1530, 290)], fill=(14, 165, 233), width=2)
    draw_arrow(draw, (1515, 290), (1530, 290), color=(14, 165, 233), width=2)

    draw.line([(1450, 675), (1480, 675), (1480, 480), (1530, 480)], fill=(52, 211, 153), width=2)
    draw_arrow(draw, (1515, 480), (1530, 480), color=(52, 211, 153), width=2)

    draw.line([(1450, 740), (1480, 740), (1480, 695), (1530, 695)], fill=(20, 184, 166), width=2)
    draw_arrow(draw, (1515, 695), (1530, 695), color=(20, 184, 166), width=2)

    # -------------------------------------------------------------
    # SECTION 5: FOOTER - TWO-TIER VERIFICATION WORKFLOW SUMMARY (Y 865 to 1110)
    # -------------------------------------------------------------
    draw_glow_box(draw, (40, 865, W - 40, 1110), 12, (15, 23, 42), (37, 99, 235), (30, 58, 138), width=2)
    draw.text((60, 880), "TWO-TIER SELECTIVE FORENSIC VERIFICATION LOGIC & ADVANTAGE", fill=(56, 189, 248), font=f_header)
    
    wf_cols = [
        ("Tier 1: Zero-Decode Bitstream Audit", 
         "• Demuxer extracts canonical NAL units directly from file.\n• Computes SHA-256 leaf hashes on raw compressed bitstream.\n• Reconstructs candidate Merkle Root in milliseconds.\n• Authentic files validated with ZERO GPU decoding energy!\n• Throughput: 5.4M packets/sec (>100x playback speed).",
         (14, 165, 233)),
        ("Tier 2: Divergence Isolation & Selective Decoding", 
         "• Triggered ONLY when candidate Merkle Root mismatch occurs.\n• Binary Merkle tree isolates exact divergent interval [PTS_a, PTS_b].\n• NVDEC hardware decodes ONLY divergent suspect frames into VRAM.\n• Eliminates >98% GPU compute during forensic incident analysis.\n• Compares Layer 2 ArcFace, OCR, Signals against baseline.",
         (245, 158, 11)),
        ("Forensic Anomaly Attribution & Verdict", 
         "• Face Swap: S_cosine < 0.72 flags deepfake identity substitution.\n• Plate Alteration: Levenshtein D >= 2 flags vehicle forgery.\n• Traffic Signal: RED to GREEN state morph exposed.\n• Clothing Palette: Detects apparel color shift across intervals.\n• Exports signed HTML & JSON legal dossiers automatically.",
         (52, 211, 153)),
        ("Hardware-Agnostic Laptop Feasibility", 
         "• Tested & optimized for budget NVIDIA RTX 3050 mobile laptops.\n• Laptop VRAM Profile confines footprint to < 2.5 GB memory.\n• 100% bitwise determinism: 0% false alarms across Ampere & Ada.\n• Standalone C++ backend + Python PyQt6 analyst workstation.\n• Fully cross-compilable for native Windows & WSL2 deployment.",
         (168, 85, 247))
    ]
    
    col_w = (W - 120) // 4
    for idx, (w_title, w_desc, w_col) in enumerate(wf_cols):
        cx = 60 + idx * (col_w + 10)
        draw_rounded_rect(draw, (cx, 915, cx + col_w, 1090), 8, (30, 41, 59), outline=w_col, width=1)
        draw.text((cx + 12, 925), w_title, fill=w_col, font=f_subhead)
        lines = w_desc.split('\n')
        ly = 952
        for line in lines:
            draw.text((cx + 12, ly), line, fill=(203, 213, 225), font=f_body)
            ly += 22

    # Save image
    out_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(out_dir)
    target_path = os.path.join(project_root, "evidence", "peakledger_architecture_flowchart.png")
    img.save(target_path, "PNG", quality=95)
    print(f"Flowchart successfully updated at: {target_path}")

if __name__ == "__main__":
    generate_flowchart()
