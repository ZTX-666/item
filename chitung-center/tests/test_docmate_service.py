from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.app import app
from chitung_center import docmate_service
from chitung_center.config import settings
from chitung_center.llm_gateway import llm_gateway


def test_generate_changeset_uses_llm_before_toolbox_generate(monkeypatch):
    monkeypatch.setattr(settings, "llm_base_url", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
    monkeypatch.setattr(settings, "llm_api_key", "glm-secret")
    monkeypatch.setattr(settings, "llm_model", "glm-5.1")

    async def fake_toolbox_call(tool_name: str, payload: dict[str, object]) -> dict[str, object]:
        if tool_name == "docmate_read_docx":
            return {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "doc_id": "doc-llm-1",
                    "structure": {
                        "paragraphs": [
                            {"index": 0, "text": "旧标题", "style": "Title", "type": "paragraph"},
                            {"index": 1, "text": "施工现场保持整洁。", "style": "Normal", "type": "paragraph"},
                        ],
                        "tables": [],
                        "image_count": 0,
                    },
                    "source_path": "/tmp/source.docx",
                },
            }
        raise AssertionError(f"LLM-first changeset should not call toolbox {tool_name}")

    async def fake_complete_document_json(system_prompt: str, user_text: str) -> dict[str, object]:
        assert "DocMate" in system_prompt
        assert "change_type" in system_prompt
        assert "旧标题" in user_text
        return {
            "action": "generate_changes",
            "changes": [
                {
                    "change_id": "chg-title",
                    "change_type": "text_replace",
                    "target": {"paragraph_id": "P1"},
                    "old_content": "旧标题",
                    "new_content": "新标题",
                    "reason": "用户要求更新标题",
                    "risk_level": "low",
                    "confidence": 0.91,
                }
            ],
        }

    monkeypatch.setattr(docmate_service.toolbox_client, "call_tool", fake_toolbox_call)
    monkeypatch.setattr(llm_gateway, "complete_document_json", AsyncMock(side_effect=fake_complete_document_json))
    monkeypatch.setattr(
        llm_gateway,
        "complete_json",
        AsyncMock(side_effect=AssertionError("DocMate must use document JSON completion")),
    )

    read_result = asyncio.run(docmate_service.read_docx("/tmp/source.docx"))
    result = asyncio.run(docmate_service.generate_changeset("doc-llm-1", "把旧标题改成新标题"))

    assert read_result["ok"] is True
    assert result["ok"] is True
    assert result["data"]["generator"] == "llm"
    assert result["data"]["changeset_id"].startswith("cs_")
    assert result["data"]["preview_cards"][0]["change_id"] == "chg-title"
    assert result["data"]["changes"][0]["new_content"] == "新标题"


def test_commit_changeset_delegates_apply_and_registers_download(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "llm_base_url", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
    monkeypatch.setattr(settings, "llm_api_key", "glm-secret")
    monkeypatch.setattr(settings, "llm_model", "glm-5.1")

    output_path = tmp_path / "source_modified.docx"
    output_path.write_bytes(b"committed-docx")

    async def fake_complete_document_json(_system_prompt: str, _user_text: str) -> dict[str, object]:
        return {
            "action": "generate_changes",
            "changes": [
                {
                    "change_id": "chg-commit",
                    "change_type": "text_replace",
                    "target": {"paragraph_id": "P1"},
                    "old_content": "旧",
                    "new_content": "新",
                    "reason": "替换文字",
                    "risk_level": "medium",
                }
            ],
        }

    async def fake_toolbox_call(tool_name: str, payload: dict[str, object]) -> dict[str, object]:
        if tool_name == "docmate_apply_changeset":
            assert payload["accepted_change_ids"] == ["chg-commit"]
            return {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "output_path": str(output_path),
                    "backup_path": str(tmp_path / "source_backup.docx"),
                    "applied": 1,
                },
            }
        raise AssertionError(f"unexpected toolbox call: {tool_name}")

    monkeypatch.setattr(llm_gateway, "complete_document_json", AsyncMock(side_effect=fake_complete_document_json))
    monkeypatch.setattr(docmate_service.toolbox_client, "call_tool", fake_toolbox_call)

    generated = asyncio.run(docmate_service.generate_changeset("doc-commit-1", "把旧改成新"))
    changeset_id = generated["data"]["changeset_id"]
    committed = asyncio.run(docmate_service.commit_changeset(changeset_id, ["chg-commit"]))

    assert committed["ok"] is True
    assert committed["data"]["status"] == "committed"
    assert committed["data"]["download_url"].startswith("/api/docmate/download/")
    file_id = committed["data"]["file_id"]
    assert docmate_service.resolve_download_file(file_id) == output_path


def test_retry_changeset_regenerates_with_feedback(monkeypatch):
    monkeypatch.setattr(settings, "llm_base_url", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
    monkeypatch.setattr(settings, "llm_api_key", "glm-secret")
    monkeypatch.setattr(settings, "llm_model", "glm-5.1")
    prompts: list[str] = []

    async def fake_complete_document_json(_system_prompt: str, user_text: str) -> dict[str, object]:
        prompts.append(user_text)
        suffix = len(prompts)
        return {
            "action": "generate_changes",
            "changes": [
                {
                    "change_id": f"chg-retry-{suffix}",
                    "change_type": "text_replace",
                    "target": {"paragraph_id": "P1"},
                    "old_content": "旧",
                    "new_content": f"新{suffix}",
                    "reason": "重试生成",
                    "risk_level": "low",
                }
            ],
        }

    monkeypatch.setattr(llm_gateway, "complete_document_json", AsyncMock(side_effect=fake_complete_document_json))

    first = asyncio.run(docmate_service.generate_changeset("doc-retry-1", "润色第一段"))
    retried = asyncio.run(docmate_service.retry_changeset(first["data"]["changeset_id"], feedback="请保留原段落语气"))

    assert retried["ok"] is True
    assert retried["data"]["retried_from"] == first["data"]["changeset_id"]
    assert retried["data"]["changeset_id"] != first["data"]["changeset_id"]
    assert "请保留原段落语气" in prompts[-1]


def test_docmate_upload_and_download_api(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "chitung_data_dir", tmp_path)

    upload = TestClient(app).post(
        "/api/docmate/upload",
        files={
            "file": (
                "sample.docx",
                b"docx-bytes",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert upload.status_code == 200
    payload = upload.json()
    assert payload["ok"] is True
    stored_path = Path(payload["file_path"])
    assert stored_path.exists()
    assert stored_path.read_bytes() == b"docx-bytes"

    download = TestClient(app).get(payload["download_url"])

    assert download.status_code == 200
    assert download.content == b"docx-bytes"
