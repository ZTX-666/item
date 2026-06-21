from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from chitung_center.config import settings
from chitung_center.models import ReportGenerateRequest
from chitung_center.toolbox_client import toolbox_client


async def generate_report_file(request: ReportGenerateRequest) -> dict[str, Any]:
    if request.report_type == "community":
        result = await toolbox_client.call_tool("generate_report", {})
        return {
            "ok": bool(result.get("ok")),
            "message": result.get("summary") or "社区报告已生成。",
            "report_type": request.report_type,
            "output_path": _tool_data(result).get("output_path"),
            "files": result.get("files", []),
            "tool_result": result,
        }

    hazards = await toolbox_client.call_tool(
        "query_safety_cases",
        {"limit": 20, "case_id": request.case_id} if request.case_id else {"limit": 20},
    )
    items = _tool_data(hazards).get("items", [])
    title = request.title or ("整改报告" if request.report_type == "rectification" else "每日安全日报")
    body = _render_report_markdown(title, request.report_type, items if isinstance(items, list) else [])
    out_path = _report_dir() / f"{request.report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    out_path.write_text(body, encoding="utf-8")
    return {
        "ok": True,
        "message": f"{title}已生成。",
        "report_type": request.report_type,
        "output_path": str(out_path),
        "files": [{"path": str(out_path), "name": out_path.name, "kind": "report", "mime_type": "text/markdown"}],
    }


def _render_report_markdown(title: str, report_type: str, items: list[dict[str, Any]]) -> str:
    lines = [
        f"# {title}",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 报告类型：{report_type}",
        f"- 涉及隐患：{len(items)} 条",
        "",
        "## 隐患摘要",
    ]
    if not items:
        lines.append("- 暂无可汇总隐患。")
    for item in items[:20]:
        lines.append(
            f"- #{item.get('id')} [{item.get('status') or 'unknown'}] "
            f"{item.get('area') or '未分区'} · {item.get('risk_level') or '未评级'} · {item.get('description') or '无描述'}"
        )
    lines.extend(
        [
            "",
            "## 建议动作",
            "- 对高风险和超期隐患优先发送整改通知。",
            "- 整改完成后上传复查照片并由安全主任确认关闭。",
            "- 将本报告作为人工审核草稿，确认后再对外发送。",
        ]
    )
    return "\n".join(lines)


def _report_dir() -> Path:
    path = settings.chitung_data_dir / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _tool_data(result: dict[str, Any]) -> dict[str, Any]:
    data = result.get("data")
    return data if isinstance(data, dict) else {}
