#!/usr/bin/env python3
"""Demo preflight checks for Chitung platform (Version4)."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / "chitung-center"
DATA = CENTER / "data"

CHECKS: list[tuple[str, bool, str]] = []
WARNINGS: list[str] = []


def record(name: str, ok: bool, detail: str) -> None:
    CHECKS.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}: {detail}")


def warn(message: str) -> None:
    WARNINGS.append(message)
    print(f"[WARN] {message}")


def fetch_json(url: str, timeout: float = 8.0, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        parsed = json.loads(body)
        return parsed if isinstance(parsed, dict) else {"raw": parsed}


def check_file(path: Path, label: str) -> None:
    record(label, path.exists(), str(path))


def check_http(name: str, url: str, timeout: float = 6.0) -> dict[str, Any] | None:
    try:
        payload = fetch_json(url, timeout=timeout)
        record(name, True, url)
        return payload
    except Exception as exc:  # noqa: BLE001
        record(name, False, f"{url} ({exc})")
        return None


def main() -> int:
    print("=" * 60)
    print("赤瞳平台 · 演示前自检 (Version4)")
    print("=" * 60)

    # 1) Core services
    toolbox = check_http("agent-toolbox 健康检查", "http://127.0.0.1:8899/health")
    center = check_http("chitung-center 健康检查", "http://127.0.0.1:8999/health", timeout=12)
    check_http("CCTV gateway 健康检查", "http://127.0.0.1:3457/api/health")
    try:
        urllib.request.urlopen("http://127.0.0.1:5173/", timeout=4)
        record("前端 Vite 页面", True, "http://127.0.0.1:5173")
    except Exception as exc:  # noqa: BLE001
        record("前端 Vite 页面", False, f"http://127.0.0.1:5173 ({exc})")

    # 2) LLM
    llm_ok = bool(center and center.get("llm_configured"))
    record("LLM 已配置", llm_ok, "可在 系统设置 中检查 API Key / 模型")
    if not llm_ok:
        warn("未配置 LLM 时，知识库问答、AI 助手、工作流智能回复会降级或失败。")

    # 3) Local data files
    check_file(DATA / "chitung_platform.db", "SQLite 数据库")
    check_file(DATA / "rag_meta.json", "RAG 元数据")
    check_file(DATA / "rag_uploads" / "builtin-safety-management-rules.pdf", "内置安全管理汇编 PDF")
    check_file(CENTER / ".env", "chitung-center .env")
    check_file(ROOT / "agent-toolbox" / ".env", "agent-toolbox .env")

    # 4) RAG builtin
    try:
        meta = json.loads((DATA / "rag_meta.json").read_text(encoding="utf-8"))
        builtin = meta.get("builtin-safety-management-rules")
        if isinstance(builtin, dict):
            chunks = int(builtin.get("chunk_count") or 0)
            record(
                "内置 RAG 文档",
                chunks >= 100,
                f"{builtin.get('file_name', 'unknown')} · {chunks} 分块",
            )
        else:
            record("内置 RAG 文档", False, "缺少 builtin-safety-management-rules")
    except Exception as exc:  # noqa: BLE001
        record("内置 RAG 文档", False, str(exc))

    # 5) Diagnostics
    diagnostics = check_http("系统诊断接口", "http://127.0.0.1:8999/api/system/diagnostics", timeout=15)
    if diagnostics:
        db_ok = bool((diagnostics.get("center") or {}).get("database", {}).get("ok"))
        record("数据库诊断", db_ok, "schema / journal_mode")
        rag_count = int(((diagnostics.get("rag") or {}).get("document_count")) or 0)
        record("RAG 文档数量", rag_count > 0, f"{rag_count} 个文档")
        wacli = ((diagnostics.get("dependencies") or {}).get("commands") or {}).get("wacli") or {}
        wacli_ok = bool(wacli.get("available"))
        record("WhatsApp wacli", wacli_ok, "演示 WhatsApp 发送时需要")
        if not wacli_ok:
            warn("WhatsApp 演示可改为展示界面流程，或提前配置 wacli。")

    # 6) Smoke API calls (only if center is up)
    if center:
        try:
            docs = fetch_json("http://127.0.0.1:8999/api/rag/documents?collection=safety", timeout=20)
            items = docs.get("items") if isinstance(docs.get("items"), list) else []
            record("RAG 列表 API", docs.get("ok") is True and len(items) > 0, f"{len(items)} 条")
        except Exception as exc:  # noqa: BLE001
            record("RAG 列表 API", False, str(exc))

        if llm_ok:
            try:
                answer = fetch_json(
                    "http://127.0.0.1:8999/api/rag/ask",
                    timeout=90,
                    method="POST",
                    payload={"query": "临边作业有哪些要求？", "top_k": 3, "collection": "safety"},
                )
                text = str(answer.get("answer") or "").strip()
                record("RAG 问答 API", bool(text), f"回答长度 {len(text)} 字")
            except Exception as exc:  # noqa: BLE001
                record("RAG 问答 API", False, str(exc))
                warn("RAG 问答失败时，演示可改用「仅检索原文」。")

        try:
            runtime = fetch_json("http://127.0.0.1:8999/api/runtime/status", timeout=10)
            record("运行时状态 API", runtime.get("ok") is not False, "workbench / toolbox 联通")
        except Exception as exc:  # noqa: BLE001
            record("运行时状态 API", False, str(exc))

    if toolbox:
        tools = toolbox.get("tools") if isinstance(toolbox.get("tools"), dict) else {}
        ready = [
            name
            for name, item in tools.items()
            if isinstance(item, dict) and (item.get("available") or item.get("ok"))
        ]
        record("agent-toolbox 工具就绪", len(ready) > 0, ", ".join(ready[:8]) or "无")

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok, _ in CHECKS if ok)
    failed = sum(1 for _, ok, _ in CHECKS if not ok)
    print(f"结果: {passed} 通过 / {failed} 失败 / {len(CHECKS)} 项")
    if WARNINGS:
        print("\n建议:")
        for item in WARNINGS:
            print(f"  - {item}")
    if failed:
        print("\n若服务未启动，请先双击: scripts\\启动赤瞳平台.bat")
        print("演示前 30 分钟建议完整重启一次电脑后再启动平台。")
        return 1
    print("\n环境就绪。建议再手动走一遍演示脚本中的每个页面。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
