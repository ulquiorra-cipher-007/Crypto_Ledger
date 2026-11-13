# Script to update generate_docx_manual.py with comprehensive CyberChain & PeakLedger integration
import os
import sys

script_path = r"C:\Users\ASUS\Desktop\crypto_ledger\peakledger\scripts\generate_docx_manual.py"
with open(script_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update Title and Executive Summary
old_cover_sub = 'r_sub = sub_p.add_run("Two-Layer Decoupled Forensic Architecture, Bitstream Merkle Cryptography & Deep Learning Forensic Pipeline Engineering Manual")'
new_cover_sub = 'r_sub = sub_p.add_run("Two-Layer Decoupled Forensic Core (C++20/CUDA) & Zero-Trust Hardware Passkey EVM Blockchain Custody Governance Manual")'

old_cover_meta = 'r_meta = meta_p.add_run("Version 2.5-Production | Decoupled Bitstream Merkle Verification Engine | NVIDIA CUDA & TensorRT Core")'
new_cover_meta = 'r_meta = meta_p.add_run("Version 3.0-Production | Decoupled Bitstream Merkle Engine + Zero-Trust Hardware Passkey Blockchain Custody Platform")'

code = code.replace(old_cover_sub, new_cover_sub)
code = code.replace(old_cover_meta, new_cover_meta)

print("Cover metadata updated.")
