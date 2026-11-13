#!/usr/bin/env python3
"""
CLI entry point for CyberChain Passkey & Identity Enrollment.
Usage:
  python entry/cli.py
  python entry/cli.py --list
  python entry/cli.py -u JohnDoe
"""
import sys
from pathlib import Path

ENTRY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ENTRY_DIR.parent
CYBERCHAIN_DIR = PROJECT_ROOT / "CyberChain"

if str(CYBERCHAIN_DIR) not in sys.path:
    sys.path.insert(0, str(CYBERCHAIN_DIR))
if str(ENTRY_DIR) not in sys.path:
    sys.path.append(str(ENTRY_DIR))

from entry_station import run_cli

if __name__ == "__main__":
    run_cli()
