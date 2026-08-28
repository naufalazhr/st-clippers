#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
# Windows venvs use Scripts/, POSIX uses bin/. Without this the script fell
# through to whatever "python" happened to be on PATH and failed confusingly.
if [ -f .venv/Scripts/activate ]; then
  # shellcheck disable=SC1091
  source .venv/Scripts/activate
elif [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
python -c "import PyInstaller" 2>/dev/null || {
  echo "PyInstaller not available to $(command -v python)."
  echo "Create the venv first: python -m venv .venv && python -m pip install -r requirements.txt pyinstaller"
  exit 1
}
[ -f models/face_detection_yunet_2023mar.onnx ] || { echo "missing ONNX"; exit 1; }
[ -d fonts ] && [ -n "$(ls -A fonts)" ] || { echo "fonts missing"; exit 1; }
python -m PyInstaller sultanclip.spec --noconfirm
echo "Done: dist/sultanclip-backend/"
