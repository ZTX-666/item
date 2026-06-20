from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.case_workflow_service import draft_rectification_notice
from chitung_center.models import CaseWorkflowRequest


def test_draft_rectification_notice_generates_notice_and_updates_case_status():
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_call_tool(tool_name: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append((tool_name, payload))
        if tool_name == "generate_rectification_notice":
            return {"ok": True, "data": {"notice_text": "整改通知草稿", "case_id": payload["case_id"]}}
        if tool_name == "update_safety_case_status":
            return {"ok": True, "data": {"case_id": payload["case_id"], "status": payload["status"]}}
        raise AssertionError(f"unexpected tool call: {tool_name}")

    with patch(
        "chitung_center.case_workflow_service.toolbox_client.call_tool",
        new=AsyncMock(side_effect=fake_call_tool),
    ) as call_tool:
        result = asyncio.run(
            draft_rectification_notice(
                CaseWorkflowRequest(case_id=42, notes="Human confirmed visual patrol candidate.")
            )
        )

    assert result["ok"] is True
    assert result["notice"] == {"notice_text": "整改通知草稿", "case_id": 42}
    assert len(result["tool_results"]) == 2
    assert call_tool.await_count == 2
    assert calls == [
        ("generate_rectification_notice", {"case_id": 42, "language": "zh-HK", "tone": "formal"}),
        (
            "update_safety_case_status",
            {
                "case_id": 42,
                "status": "rectification_notice_drafted",
                "notes": "Human confirmed visual patrol candidate.",
            },
        ),
    ]
