#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/.venv/bin/activate"
PORT="${DEPTH_PORT:-8090}"
exec python -m uvicorn depth_api:app --host 0.0.0.0 --port "$PORT"
