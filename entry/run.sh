#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$DIR/../CyberChain:$DIR:${PYTHONPATH}"
python3 "$DIR/entry_station.py" "$@"
