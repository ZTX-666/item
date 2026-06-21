from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.models import WorkbenchVideoDetectionRequest
from chitung_center.workbench_video_detection_service import (
    _fallback_refined_prompt,
    _build_aggregate_summary,
    list_video_detection_reports,
    preview_workbench_detection_prompt,
    run_workbench_video_detection,
)


def test_workbench_video_detection_refines_prompt_runs_guardian_and_persists(tmp_path, monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "chitung_center.workbench_video_detection_service._report_store_path",
        lambda: tmp_path / "reports.json",
    )
    monkeypatch.setattr(
        "chitung_center.workbench_video_detection_service.get_app_config",
        lambda: {
            "cameras": [
                {"id": "cam-1", "name": "施工區域01", "area": "施工區域", "enabled": True},
            ]
        },
    )

    async def fake_refine(direction: str, cameras: list[dict[str, object]]) -> dict[str, object]:
        captured["direction"] = direction
        captured["camera"] = cameras[0]["id"]
        return {
            "original_direction": direction,
            "refined_prompt": "重点检查未戴安全帽、未穿反光衣，并结合高处作业制度判断风险。",
            "policy_context": ["进入施工区必须佩戴安全帽。"],
        }

    async def fake_run_guardian_patrol(**kwargs):
        captured.update(kwargs)
        return {
            "ok": True,
            "audit_id": "audit-1",
            "report": {
                "patrol_id": "patrol-1",
                "timestamp": "2026-06-21T10:00:00",
                "cameras": [
                    {
                        "camera_id": "cam-1",
                        "camera_name": "施工區域01",
                        "area": "施工區域",
                        "success": True,
                        "snapshot_url": "/api/visual/patrol-files/patrol-1/cam-1_snapshot.jpg",
                        "annotated_url": "/api/visual/patrol-files/patrol-1/cam-1_annotated.jpg",
                        "snapshot_path": "/tmp/cam-1_snapshot.jpg",
                        "annotated_path": "/tmp/cam-1_annotated.jpg",
                        "detections": [
                            {
                                "bbox": [10, 20, 100, 160],
                                "label": "未戴安全帽",
                                "confidence": 0.91,
                                "source": "hybrid",
                                "severity": "high",
                                "description": "作业人员未佩戴安全帽。",
                                "suggested_action": "立即提醒并复核 PPE。",
                            }
                        ],
                        "source_mix": "hybrid",
                    }
                ],
            },
        }

    monkeypatch.setattr("chitung_center.workbench_video_detection_service.refine_detection_prompt", fake_refine)
    monkeypatch.setattr("chitung_center.workbench_video_detection_service.run_guardian_patrol", fake_run_guardian_patrol)

    result = asyncio.run(
        run_workbench_video_detection(
            WorkbenchVideoDetectionRequest(
                detection_direction="检查未戴安全帽",
                camera_id="cam-1",
                vlm_enabled=True,
            )
        )
    )

    assert result["ok"] is True
    assert captured["inspection_prompt"] == "重点检查未戴安全帽、未穿反光衣，并结合高处作业制度判断风险。"
    assert captured["camera_id"] == "cam-1"
    assert result["summary"]["severity"] == "high"
    assert result["summary"]["detection_count"] == 1
    assert "未戴安全帽" in result["summary"]["text"]
    assert result["annotated_url"].endswith("cam-1_annotated.jpg")

    stored = json.loads((tmp_path / "reports.json").read_text(encoding="utf-8"))
    assert stored[0]["report_id"] == result["report_id"]
    assert stored[0]["refined_prompt"] == "重点检查未戴安全帽、未穿反光衣，并结合高处作业制度判断风险。"

    listed = list_video_detection_reports(limit=5)
    assert listed["items"][0]["report_id"] == result["report_id"]
    assert listed["items"][0]["camera_name"] == "施工區域01"


def test_workbench_video_detection_fails_when_real_frame_capture_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "chitung_center.workbench_video_detection_service._report_store_path",
        lambda: tmp_path / "reports.json",
    )
    monkeypatch.setattr(
        "chitung_center.workbench_video_detection_service.get_app_config",
        lambda: {"cameras": [{"id": "cam-1", "name": "施工區域01", "area": "施工區域", "enabled": True}]},
    )

    async def fake_run_guardian_patrol(**_kwargs):
        return {
            "ok": True,
            "audit_id": "audit-1",
            "report": {
                "patrol_id": "patrol-1",
                "timestamp": "2026-06-21T10:00:00",
                "cameras": [
                    {
                        "camera_id": "cam-1",
                        "camera_name": "施工區域01",
                        "area": "施工區域",
                        "success": False,
                        "snapshot_source": "failed",
                        "fallback_used": False,
                        "error": "真实摄像头抽帧失败，未使用本地回退图",
                        "detections": [],
                    }
                ],
            },
        }

    monkeypatch.setattr("chitung_center.workbench_video_detection_service.run_guardian_patrol", fake_run_guardian_patrol)

    result = asyncio.run(
        run_workbench_video_detection(
            WorkbenchVideoDetectionRequest(
                detection_direction="检查未戴安全帽",
                camera_id="cam-1",
                refined_prompt="检查未戴安全帽",
                vlm_enabled=False,
            )
        )
    )

    assert result["ok"] is False
    assert "真实摄像头抽帧失败" in result["error"]
    assert result["camera_errors"] == [
        {"camera_id": "cam-1", "error": "真实摄像头抽帧失败，未使用本地回退图"}
    ]
    assert not (tmp_path / "reports.json").exists()


def test_workbench_prompt_preview_returns_editable_prompt_for_selected_cameras(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "chitung_center.workbench_video_detection_service.get_app_config",
        lambda: {
            "cameras": [
                {"id": "cam-1", "name": "施工區域01", "area": "施工區域", "enabled": True},
                {"id": "cam-2", "name": "崗亭01", "area": "崗亭", "enabled": True},
            ]
        },
    )

    async def fake_refine(direction: str, cameras: list[dict[str, object]]) -> dict[str, object]:
        captured["direction"] = direction
        captured["camera_ids"] = [camera["id"] for camera in cameras]
        return {
            "original_direction": direction,
            "refined_prompt": "请重点检查施工區域、崗亭两路画面中的 PPE 和机械靠近人员风险。",
            "policy_context": ["进入施工区必须佩戴安全帽。"],
            "source": "llm",
        }

    monkeypatch.setattr("chitung_center.workbench_video_detection_service.refine_detection_prompt", fake_refine)

    result = asyncio.run(
        preview_workbench_detection_prompt(
            WorkbenchVideoDetectionRequest(
                detection_direction="检查 PPE 和机械靠近人员",
                camera_ids=["cam-1", "cam-2"],
            )
        )
    )

    assert result["ok"] is True
    assert captured["camera_ids"] == ["cam-1", "cam-2"]
    assert result["camera_ids"] == ["cam-1", "cam-2"]
    assert result["refined_prompt"] == "请重点检查施工區域、崗亭两路画面中的 PPE 和机械靠近人员风险。"
    assert result["prompt_source"] == "llm"
    assert result["policy_context"] == ["进入施工区必须佩戴安全帽。"]


def test_workbench_video_detection_runs_multiple_cameras_with_user_prompt(tmp_path, monkeypatch):
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "chitung_center.workbench_video_detection_service._report_store_path",
        lambda: tmp_path / "reports.json",
    )
    monkeypatch.setattr(
        "chitung_center.workbench_video_detection_service.get_app_config",
        lambda: {
            "cameras": [
                {"id": "cam-1", "name": "施工區域01", "area": "施工區域", "enabled": True},
                {"id": "cam-2", "name": "崗亭01", "area": "崗亭", "enabled": True},
            ]
        },
    )

    async def fake_refine(direction: str, cameras: list[dict[str, object]]) -> dict[str, object]:
        raise AssertionError("user edited prompt should be used without re-refining")

    async def fake_run_guardian_patrol(**kwargs):
        calls.append(kwargs)
        camera_id = str(kwargs["camera_id"])
        return {
            "ok": True,
            "audit_id": f"audit-{camera_id}",
            "report": {
                "patrol_id": f"patrol-{camera_id}",
                "cameras": [
                    {
                        "camera_id": camera_id,
                        "camera_name": "施工區域01" if camera_id == "cam-1" else "崗亭01",
                        "area": "施工區域" if camera_id == "cam-1" else "崗亭",
                        "success": True,
                        "snapshot_url": f"/api/visual/patrol-files/patrol-{camera_id}/{camera_id}_snapshot.jpg",
                        "annotated_url": f"/api/visual/patrol-files/patrol-{camera_id}/{camera_id}_annotated.jpg",
                        "detections": [
                            {
                                "bbox": [10, 20, 80, 120],
                                "label": "未戴安全帽" if camera_id == "cam-1" else "人员靠近机械",
                                "confidence": 0.86,
                                "severity": "high" if camera_id == "cam-1" else "medium",
                                "description": f"{camera_id} 检出风险。",
                                "suggested_action": "现场复核并提醒整改。",
                            }
                        ],
                    }
                ],
            },
        }

    monkeypatch.setattr("chitung_center.workbench_video_detection_service.refine_detection_prompt", fake_refine)
    monkeypatch.setattr("chitung_center.workbench_video_detection_service.run_guardian_patrol", fake_run_guardian_patrol)

    result = asyncio.run(
        run_workbench_video_detection(
            WorkbenchVideoDetectionRequest(
                detection_direction="检查 PPE 和机械靠近人员",
                camera_ids=["cam-1", "cam-2"],
                refined_prompt="用户确认后的提示词：重点检查 PPE、机械回转半径和人员距离。",
            )
        )
    )

    assert result["ok"] is True
    assert [call["camera_id"] for call in calls] == ["cam-1", "cam-2"]
    assert {call["inspection_prompt"] for call in calls} == {"用户确认后的提示词：重点检查 PPE、机械回转半径和人员距离。"}
    assert result["camera_count"] == 2
    assert result["summary"]["detection_count"] == 2
    assert result["summary"]["severity"] == "high"
    assert [camera["camera_id"] for camera in result["cameras"]] == ["cam-1", "cam-2"]
    assert result["refined_prompt"] == "用户确认后的提示词：重点检查 PPE、机械回转半径和人员距离。"

    stored = json.loads((tmp_path / "reports.json").read_text(encoding="utf-8"))
    assert stored[0]["camera_count"] == 2
    assert len(stored[0]["cameras"]) == 2


def test_workbench_video_detection_persists_sqlite_row_per_camera(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "chitung_center.workbench_video_detection_service._report_store_path",
        lambda: tmp_path / "reports.json",
    )
    monkeypatch.setattr(
        "chitung_center.workbench_video_detection_service.get_app_config",
        lambda: {
            "cameras": [
                {"id": "cam-1", "name": "施工區域01", "area": "施工區域", "enabled": True},
                {"id": "cam-2", "name": "出入口02", "area": "出入口", "enabled": True},
            ]
        },
    )

    async def fake_run_guardian_patrol(**kwargs):
        camera_id = str(kwargs["camera_id"])
        is_fallback = camera_id == "cam-2"
        return {
            "ok": True,
            "audit_id": f"audit-{camera_id}",
            "report": {
                "patrol_id": f"patrol-{camera_id}",
                "timestamp": "2026-06-21T10:00:00+00:00",
                "vlm_enabled": True,
                "cameras": [
                    {
                        "camera_id": camera_id,
                        "camera_name": "施工區域01" if camera_id == "cam-1" else "出入口02",
                        "area": "施工區域" if camera_id == "cam-1" else "出入口",
                        "success": True,
                        "snapshot_url": f"/api/visual/patrol-files/patrol-{camera_id}/{camera_id}_snapshot.jpg",
                        "annotated_url": f"/api/visual/patrol-files/patrol-{camera_id}/{camera_id}_annotated.jpg",
                        "snapshot_path": f"/tmp/{camera_id}_snapshot.jpg",
                        "annotated_path": f"/tmp/{camera_id}_annotated.jpg",
                        "snapshot_source": "fallback" if is_fallback else "csmart_screenshot",
                        "fallback_used": is_fallback,
                        "fallback_reason": "视频流不可用，使用样例图" if is_fallback else "",
                        "source_mix": "hybrid",
                        "user_question": "检查 PPE 和机械靠近人员",
                        "vlm_prompts": [
                            {
                                "detection_index": 0,
                                "label": "未戴安全帽" if camera_id == "cam-1" else "人员靠近机械",
                                "prompt": f"{camera_id} VLM prompt",
                                "messages": [
                                    {
                                        "role": "user",
                                        "content": [{"type": "text", "text": f"{camera_id} VLM prompt"}],
                                    }
                                ],
                            }
                        ],
                        "vlm_raw_responses": [
                            {
                                "detection_index": 0,
                                "label": "未戴安全帽" if camera_id == "cam-1" else "人员靠近机械",
                                "raw_response": f"{camera_id} raw vlm response",
                            }
                        ],
                        "roi_images": [
                            {
                                "detection_index": 0,
                                "label": "未戴安全帽" if camera_id == "cam-1" else "人员靠近机械",
                                "base64": f"{camera_id}-roi-base64",
                                "data_url": f"data:image/jpeg;base64,{camera_id}-roi-base64",
                            }
                        ],
                        "model_requests": [
                            {"detection_index": 0, "request": {"model": "glm-test", "messages": [{"role": "user"}]}}
                        ],
                        "model_responses": [
                            {"detection_index": 0, "response": {"choices": [{"message": {"content": "raw text"}}]}}
                        ],
                        "detections": [
                            {
                                "bbox": [10, 20, 100, 160],
                                "label": "未戴安全帽" if camera_id == "cam-1" else "人员靠近机械",
                                "confidence": 0.91,
                                "source": "hybrid",
                                "severity": "high" if camera_id == "cam-1" else "medium",
                                "description": f"{camera_id} 检出风险。",
                                "suggested_action": "现场复核并提醒整改。",
                            }
                        ],
                    }
                ],
            },
        }

    monkeypatch.setattr("chitung_center.workbench_video_detection_service.run_guardian_patrol", fake_run_guardian_patrol)

    result = asyncio.run(
        run_workbench_video_detection(
            WorkbenchVideoDetectionRequest(
                detection_direction="检查 PPE 和机械靠近人员",
                camera_ids=["cam-1", "cam-2"],
                refined_prompt="用户确认后的提示词：重点检查 PPE、机械回转半径和人员距离。",
            )
        )
    )

    assert result["ok"] is True
    assert "storage_error" not in result

    db_path = tmp_path / "video_detection_results.db"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(workbench_video_detection_results)")}
        assert {
            "report_id",
            "user_question",
            "camera_id",
            "camera_name",
            "area",
            "direction",
            "refined_prompt",
            "created_at",
            "snapshot_path",
            "snapshot_url",
            "annotated_path",
            "annotated_url",
            "snapshot_source",
            "fallback_used",
            "fallback_reason",
            "detection_count",
            "labels_json",
            "detections_json",
            "vlm_prompts_json",
            "vlm_raw_responses_json",
            "roi_images_json",
            "model_request_json",
            "model_response_json",
            "summary_title",
            "summary_text",
            "summary_severity",
            "camera_report_json",
        }.issubset(columns)

        rows = conn.execute(
            """
            SELECT *
            FROM workbench_video_detection_results
            ORDER BY camera_id
            """
        ).fetchall()

    assert len(rows) == 2
    first = rows[0]
    assert first["report_id"] == result["report_id"]
    assert first["created_at"] == result["created_at"]
    assert first["camera_id"] == "cam-1"
    assert first["camera_name"] == "施工區域01"
    assert first["area"] == "施工區域"
    assert first["direction"] == "检查 PPE 和机械靠近人员"
    assert first["user_question"] == "检查 PPE 和机械靠近人员"
    assert first["refined_prompt"] == "用户确认后的提示词：重点检查 PPE、机械回转半径和人员距离。"
    assert first["snapshot_source"] == "csmart_screenshot"
    assert first["fallback_used"] == 0
    assert first["detection_count"] == 1
    assert json.loads(first["labels_json"]) == ["未戴安全帽"]
    assert json.loads(first["detections_json"])[0]["label"] == "未戴安全帽"
    assert json.loads(first["vlm_prompts_json"])[0]["prompt"] == "cam-1 VLM prompt"
    assert json.loads(first["vlm_raw_responses_json"])[0]["raw_response"] == "cam-1 raw vlm response"
    assert json.loads(first["roi_images_json"])[0]["base64"] == "cam-1-roi-base64"
    assert json.loads(first["model_request_json"])[0]["request"]["model"] == "glm-test"
    assert json.loads(first["model_response_json"])[0]["response"]["choices"][0]["message"]["content"] == "raw text"
    assert first["summary_title"] == "施工區域01 视频检测简报"
    assert first["summary_severity"] == "high"
    assert json.loads(first["camera_report_json"])["summary"]["detection_count"] == 1

    second = rows[1]
    assert second["camera_id"] == "cam-2"
    assert second["snapshot_source"] == "fallback"
    assert second["fallback_used"] == 1
    assert second["fallback_reason"] == "视频流不可用，使用样例图"
    assert json.loads(second["labels_json"]) == ["人员靠近机械"]


def test_workbench_video_detection_exposes_storage_error_when_sqlite_write_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "chitung_center.workbench_video_detection_service._report_store_path",
        lambda: tmp_path / "reports.json",
    )
    monkeypatch.setattr(
        "chitung_center.workbench_video_detection_service.get_app_config",
        lambda: {"cameras": [{"id": "cam-1", "name": "施工區域01", "area": "施工區域", "enabled": True}]},
    )

    async def fake_run_guardian_patrol(**kwargs):
        return {
            "ok": True,
            "audit_id": "audit-cam-1",
            "report": {
                "patrol_id": "patrol-cam-1",
                "timestamp": "2026-06-21T10:00:00+00:00",
                "cameras": [
                    {
                        "camera_id": "cam-1",
                        "camera_name": "施工區域01",
                        "area": "施工區域",
                        "success": True,
                        "snapshot_url": "/api/visual/patrol-files/patrol-cam-1/cam-1_snapshot.jpg",
                        "annotated_url": "/api/visual/patrol-files/patrol-cam-1/cam-1_annotated.jpg",
                        "snapshot_path": "/tmp/cam-1_snapshot.jpg",
                        "annotated_path": "/tmp/cam-1_annotated.jpg",
                        "detections": [
                            {
                                "bbox": [10, 20, 100, 160],
                                "label": "未戴安全帽",
                                "confidence": 0.91,
                                "severity": "high",
                                "description": "作业人员未佩戴安全帽。",
                                "suggested_action": "现场复核并提醒整改。",
                            }
                        ],
                    }
                ],
            },
        }

    def fail_persist(*args, **kwargs):
        raise RuntimeError("sqlite disk full")

    monkeypatch.setattr("chitung_center.workbench_video_detection_service.run_guardian_patrol", fake_run_guardian_patrol)
    monkeypatch.setattr("chitung_center.workbench_video_detection_service.persist_video_detection_report", fail_persist)

    result = asyncio.run(
        run_workbench_video_detection(
            WorkbenchVideoDetectionRequest(
                detection_direction="检查未戴安全帽",
                camera_id="cam-1",
                refined_prompt="检查安全帽佩戴情况。",
            )
        )
    )

    assert result["ok"] is True
    assert result["storage_error"] == "sqlite disk full"

    stored = json.loads((tmp_path / "reports.json").read_text(encoding="utf-8"))
    assert stored[0]["storage_error"] == "sqlite disk full"


def test_workbench_video_detection_handles_guardian_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "chitung_center.workbench_video_detection_service._report_store_path",
        lambda: tmp_path / "reports.json",
    )
    monkeypatch.setattr(
        "chitung_center.workbench_video_detection_service.get_app_config",
        lambda: {"cameras": [{"id": "cam-1", "name": "施工區域01", "area": "施工區域", "enabled": True}]},
    )

    async def fake_refine(direction: str, cameras: list[dict[str, object]]) -> dict[str, object]:
        return {"original_direction": direction, "refined_prompt": direction, "policy_context": []}

    async def fake_run_guardian_patrol(**kwargs):
        return {"ok": False, "error": "camera offline"}

    monkeypatch.setattr("chitung_center.workbench_video_detection_service.refine_detection_prompt", fake_refine)
    monkeypatch.setattr("chitung_center.workbench_video_detection_service.run_guardian_patrol", fake_run_guardian_patrol)

    result = asyncio.run(
        run_workbench_video_detection(
            WorkbenchVideoDetectionRequest(detection_direction="检查吊装作业", camera_id="cam-1")
        )
    )

    assert result["ok"] is False
    assert result["error"] == "camera offline"
    assert list_video_detection_reports()["items"] == []


def test_fallback_prompt_targets_ppe_and_machinery_exclusion_zone():
    prompt = _fallback_refined_prompt(
        "检查人员PPE合规、机械作业半径和隔离围挡",
        [{"id": "cam-slope-03", "name": "斜坡03", "area": "斜坡"}],
        [],
    )

    assert "人员PPE合规" in prompt
    assert "机械作业半径" in prompt
    assert "人员与机械安全距离" in prompt
    assert "隔离围挡" in prompt


def test_aggregate_summary_flags_people_and_excavator_for_manual_review():
    summary = _build_aggregate_summary(
        "检查人员PPE合规、机械作业半径和隔离围挡",
        [
            {
                "camera_id": "cam-slope-03",
                "camera_name": "斜坡03",
                "detections": [
                    {"label": "人员", "severity": "low"},
                    {"label": "安全帽", "severity": "low"},
                    {"label": "反光衣", "severity": "low"},
                    {"label": "挖掘机", "severity": "low"},
                ],
            }
        ],
    )

    assert "人员与机械" in summary["text"]
    assert "安全距离" in summary["text"]
    assert "隔离围挡" in summary["text"]
    assert "0 个高风险" not in summary["text"]
    assert summary["severity"] == "medium"
    assert summary["suggested_action"] == "请复核人员与机械作业区安全距离、隔离围挡和现场管控。"
