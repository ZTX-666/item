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

    with (
        patch("chitung_center.workflow_engine.workflow_store.append_step", new_callable=AsyncMock) as append_step,
        patch("chitung_center.workflow_engine.workflow_store.update_step", new_callable=AsyncMock) as update_step,
    ):
        append_step.return_value = {"data": {"workflow_step": {"workflow_step_id": "step-1"}}}
        update_step.return_value = {"ok": True}
        reply, tool_results, cards = asyncio.run(WorkflowEngine()._run_visual_patrol(request, "wf-1"))

    assert "视觉巡检页面" in reply
    assert tool_results == []
    assert cards[0].actions[0]["id"] == "open_visual_patrol"
