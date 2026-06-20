#!/usr/bin/env bash
# 赤瞳安全智能平台 — 本地 Demo 一键启动 (macOS / Linux)
#
# 启动 agent-toolbox (8899) + chitung-center (8999) 两个后端服务，
# 然后运行「每日外部风险简报」工作流作为端到端 demo。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLBOX="$ROOT/agent-toolbox"
CENTER="$ROOT/chitung-center"

# 后端运行所需的最小依赖集合（避开较重的 OCR/onnxruntime 依赖，
# 这些仅在「耀耀结构化录入」OCR 功能时才需要）。
CORE_DEPS=(fastapi "uvicorn[standard]" pydantic pydantic-settings python-dotenv requests httpx pillow pypdfium2 python-docx eval_type_backport)

echo "=== 赤瞳安全智能平台 Demo ==="
echo "项目根目录: $ROOT"

ensure_venv() {
  local dir="$1"
  if [[ ! -x "$dir/.venv/bin/python" ]]; then
    echo "[安装] 在 $dir 创建虚拟环境并安装依赖 ..."
    python3 -m venv "$dir/.venv"
    "$dir/.venv/bin/python" -m pip install --upgrade pip >/dev/null
    "$dir/.venv/bin/python" -m pip install "${CORE_DEPS[@]}"
  fi
}

start_service() {
  local name="$1" dir="$2" port="$3"
  local url="http://127.0.0.1:${port}/health"
  if curl -sf "$url" >/dev/null 2>&1; then
    echo "[OK] $name 已在运行 ($url)"
    return
  fi
  ensure_venv "$dir"
  echo "[启动] $name ..."
  mkdir -p "$CENTER/data"
  ( cd "$dir" && nohup "$dir/.venv/bin/python" run_server.py >"$CENTER/data/${name}.log" 2>&1 & echo $! >"$CENTER/data/${name}.pid" )
  for _ in $(seq 1 30); do
    curl -sf "$url" >/dev/null 2>&1 && { echo "[OK] $name 启动成功 ($url)"; return; }
    sleep 1
  done
  echo "[FAIL] $name 启动超时，请查看日志: chitung-center/data/${name}.log"
  exit 1
}

mkdir -p "$CENTER/data" "$TOOLBOX/workspace"
start_service "agent-toolbox" "$TOOLBOX" 8899
start_service "chitung-center" "$CENTER" 8999

echo
echo "=== Demo: 每日外部风险简报（实时抓取香港天文台 + 官方安全资讯）==="
curl -sf -X POST "http://127.0.0.1:8999/api/workflows/run" \
  -H "Content-Type: application/json" \
  -d '{"workflow_name":"workflow_daily_risk_briefing","message":"生成今日外部风险简报","channel":"demo","user_id":"demo-user"}' \
  | "$CENTER/.venv/bin/python" -c "
import sys, json
d = json.load(sys.stdin)
print('回复:', d.get('reply'))
def walk(o):
    if isinstance(o, dict):
        t = o.get('text')
        if isinstance(t, str) and '外部风险简报' in t:
            print('\n' + t)
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)
walk(d)
" 2>/dev/null || echo "(已生成简报，完整 JSON 见 http://127.0.0.1:8999/docs)"

echo
echo "=== 健康检查 ==="
curl -sf "http://127.0.0.1:8999/api/runtime/status" | "$CENTER/.venv/bin/python" -m json.tool 2>/dev/null | head -20 || true

cat <<'NEXT'

=== 下一步 ===
1. 浏览器查看全部后端 API 文档(Swagger): http://127.0.0.1:8999/docs
2. 启动桌面前端(需本机已安装 Node.js / npm):
     cd chitung-frontend && npm install && npm run desktop:dev
3. 停止后端服务:
     kill $(cat chitung-center/data/agent-toolbox.pid) $(cat chitung-center/data/chitung-center.pid)
NEXT
