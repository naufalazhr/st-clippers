#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
[ -f .venv/bin/activate ] && source .venv/bin/activate
[ -f models/face_detection_yunet_2023mar.onnx ] || { echo "missing ONNX"; exit 1; }
[ -d fonts ] && [ -n "$(ls -A fonts)" ] || { echo "fonts missing"; exit 1; }
python -m PyInstaller sultanclip.spec --noconfirm
echo "Done: dist/sultanclip-backend/"
