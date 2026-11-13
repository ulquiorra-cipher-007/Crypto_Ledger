#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$DIR:${PYTHONPATH}"
export PATH="$HOME/.foundry/bin:$PATH"
echo "[*] Launching CyberChain Admin Console..."
python3 "$DIR/admin_app.py" "$@"
