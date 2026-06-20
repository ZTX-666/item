#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/.venv/bin/activate"
PORT="${PORT:-8080}"
exec python -m uvicorn hiagent_api:app --host 0.0.0.0 --port "$PORT"
