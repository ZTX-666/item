#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null || { echo "需要 Python 3.10+"; exit 1; }

VENV="$ROOT/.venv"
[[ -d "$VENV" ]] || "$PY" -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

pip install --upgrade pip wheel
if command -v nvidia-smi >/dev/null 2>&1; then
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
else
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
fi
pip install -r requirements.txt

python scripts/download_all_weights.py
python verify_env.py

echo "完成。检测 API: bash run_detect_api.sh | 深度 API: bash run_depth_api.sh"
