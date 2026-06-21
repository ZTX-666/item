from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.models import ChatMessageRequest
from chitung_center.workflow_engine import WorkflowEngine


def test_visual_workflow_runs_local_source_when_metadata_contains_source():
    draft = {
        "ok": True,
        "message": "Visual patrol draft generated.",
        "requires_confirmation": True,
        "source": "/tmp/site.jpg",
        "candidates": [{"id": "visual-vlm-test-1", "description": "No hardhat"}],
        "confirm_payload": {"task_id": "vlm-test-1", "image_path": "/tmp/site.jpg"},
    }
    request = ChatMessageRequest(
        message="识别这张照片",
        metadata={"source": "/tmp/site.jpg", "area": "B2", "contractor": "Demo Contractor"},
    )

    with (
        patch("chitung_center.workflow_engine.build_visual_patrol_draft", new_callable=AsyncMock) as build_draft,
        patch("chitung_center.workflow_engine.workflow_store.link_event", new_callable=AsyncMock) as link_event,
    ):
        build_draft.return_value = draft
        link_event.return_value = {"ok": True}
        reply, tool_results, cards = asyncio.run(WorkflowEngine()._run_visual_patrol(request, "wf-1"))

    assert "视觉巡检候选" in reply
    assert tool_results == [draft]
    assert len(cards) == 1
    assert cards[0].card_type == "visual_patrol"
    assert cards[0].data["draft"] == draft
    build_draft.assert_awaited_once()
    link_event.assert_awaited_once()


def test_visual_workflow_keeps_page_card_without_source():
    request = ChatMessageRequest(message="检查摄像头")
    detection = {
        "ok": True,
        "report_id": "video-test-1",
        "summary": {"text": "已按“检查摄像头”完成 1 路摄像头检测，未发现明确目标。"},
    }

    with (
        patch("chitung_center.workflow_engine.run_workbench_video_detection", new_callable=AsyncMock) as run_detection,
        patch("chitung_center.workflow_engine._start_step", new_callable=AsyncMock) as start_step,
        patch("chitung_center.workflow_engine._finish_step", new_callable=AsyncMock) as finish_step,
    ):
        run_detection.return_value = detection
        start_step.return_value = {"workflow_step_id": "step-1"}
        reply, tool_results, cards = asyncio.run(WorkflowEngine()._run_visual_patrol(request, "wf-1"))

    assert "完成 1 路摄像头检测" in reply
    assert tool_results[0]["tool"] == "workbench_video_detection"
    assert tool_results[0]["report_id"] == "video-test-1"
    assert cards[0].card_type == "video_detection_report"
    assert cards[0].actions[0]["id"] == "open_hazard_ledger"
    run_detection.assert_awaited_once()
    start_step.assert_awaited_once()
    finish_step.assert_awaited_once()
