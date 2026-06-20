"""Unit tests for visual_patrol_service.py — data flow and helper functions."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# We need to import from chitung_center, which may need its own path setup
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.visual_patrol_service import (
    build_visual_patrol_draft,
    confirm_visual_patrol_candidate,
    _extract_crops_from_yolo,
    _flatten_yolo_detections,
    _build_candidates,
    _build_candidates_from_merged,
    _max_severity,
    _severity_from_labels,
    _has_high_risk_label,
    _looks_like_image,
    _tool_data,
    _first_file_path,
)
from chitung_center.models import VisualPatrolConfirmRequest, VisualPatrolDraftRequest


# ── _extract_crops_from_yolo tests ───────────────────────────────


class TestExtractCropsFromYolo:
    def test_standard_yolo_format(self):
        """YOLO detect.py output format: {images: [{image, detections: [{class_name, confidence, bbox_xyxy}]}]}"""
        detections = {
            "images": [
                {
                    "image": "/tmp/img1.jpg",
                    "detections": [
                        {"class_name": "helmet", "confidence": 0.9, "bbox_xyxy": [10, 10, 50, 50]},
                        {"class_name": "vest", "confidence": 0.5, "bbox_xyxy": [60, 60, 100, 100]},
                    ],
                }
            ]
        }
        result = _extract_crops_from_yolo(detections, conf_threshold=0.45)
        assert "/tmp/img1.jpg" in result
        crops = result["/tmp/img1.jpg"]
        assert len(crops) == 2
        assert crops[0]["label"] == "helmet"
        assert crops[0]["bbox"] == [10.0, 10.0, 50.0, 50.0]
        assert crops[0]["confidence"] == 0.9

    def test_conf_threshold_filtering(self):
        detections = {
            "images": [
                {
                    "image": "/tmp/img1.jpg",
                    "detections": [
                        {"class_name": "helmet", "confidence": 0.9, "bbox_xyxy": [10, 10, 50, 50]},
                        {"class_name": "vest", "confidence": 0.3, "bbox_xyxy": [60, 60, 100, 100]},
                    ],
                }
            ]
        }
        result = _extract_crops_from_yolo(detections, conf_threshold=0.45)
        assert len(result["/tmp/img1.jpg"]) == 1
        assert result["/tmp/img1.jpg"][0]["label"] == "helmet"

    def test_bbox_key_fallback(self):
        """Should also accept 'bbox' key instead of 'bbox_xyxy'."""
        detections = {
            "images": [
                {
                    "image": "/tmp/img1.jpg",
                    "detections": [
                        {"class_name": "helmet", "confidence": 0.9, "bbox": [10, 10, 50, 50]},
                    ],
                }
            ]
        }
        result = _extract_crops_from_yolo(detections, conf_threshold=0.45)
        assert len(result["/tmp/img1.jpg"]) == 1
        assert result["/tmp/img1.jpg"][0]["bbox"] == [10.0, 10.0, 50.0, 50.0]

    def test_label_key_fallback(self):
        """Should also accept 'label' key instead of 'class_name'."""
        detections = {
            "images": [
                {
                    "image": "/tmp/img1.jpg",
                    "detections": [
                        {"label": "helmet", "confidence": 0.9, "bbox_xyxy": [10, 10, 50, 50]},
                    ],
                }
            ]
        }
        result = _extract_crops_from_yolo(detections, conf_threshold=0.45)
        assert result["/tmp/img1.jpg"][0]["label"] == "helmet"

    def test_objects_key_fallback(self):
        """Should also accept 'objects' key instead of 'detections'."""
        detections = {
            "images": [
                {
                    "image": "/tmp/img1.jpg",
                    "objects": [
                        {"class_name": "helmet", "confidence": 0.9, "bbox_xyxy": [10, 10, 50, 50]},
                    ],
                }
            ]
        }
        result = _extract_crops_from_yolo(detections, conf_threshold=0.45)
        assert len(result["/tmp/img1.jpg"]) == 1

    def test_empty_detections(self):
        result = _extract_crops_from_yolo({}, conf_threshold=0.45)
        assert result == {}

    def test_non_dict_input(self):
        result = _extract_crops_from_yolo("not a dict", conf_threshold=0.45)
        assert result == {}

    def test_missing_image_path(self):
        detections = {
            "images": [
                {
                    "detections": [
                        {"class_name": "helmet", "confidence": 0.9, "bbox_xyxy": [10, 10, 50, 50]},
                    ],
                }
            ]
        }
        result = _extract_crops_from_yolo(detections, conf_threshold=0.45)
        assert result == {}

    def test_multiple_images(self):
        detections = {
            "images": [
                {
                    "image": "/tmp/img1.jpg",
                    "detections": [{"class_name": "helmet", "confidence": 0.9, "bbox_xyxy": [10, 10, 50, 50]}],
                },
                {
                    "image": "/tmp/img2.jpg",
                    "detections": [{"class_name": "vest", "confidence": 0.8, "bbox_xyxy": [20, 20, 60, 60]}],
                },
            ]
        }
        result = _extract_crops_from_yolo(detections, conf_threshold=0.45)
        assert len(result) == 2
        assert "/tmp/img1.jpg" in result
        assert "/tmp/img2.jpg" in result

    def test_crop_id_generation(self):
        detections = {
            "images": [
                {
                    "image": "/tmp/img1.jpg",
                    "detections": [
                        {"class_name": "helmet", "confidence": 0.9, "bbox_xyxy": [10, 10, 50, 50]},
                        {"class_name": "vest", "confidence": 0.8, "bbox_xyxy": [60, 60, 100, 100]},
                    ],
                }
            ]
        }
        result = _extract_crops_from_yolo(detections, conf_threshold=0.45)
        ids = [c["id"] for c in result["/tmp/img1.jpg"]]
        assert ids == ["c1", "c2"]


# ── _flatten_yolo_detections tests ───────────────────────────────


class TestFlattenYoloDetections:
    def test_standard_format(self):
        detections = {
            "images": [
                {
                    "image": "/tmp/img1.jpg",
                    "detections": [
                        {"class_name": "helmet", "confidence": 0.9, "bbox_xyxy": [10, 10, 50, 50]},
                    ],
                }
            ]
        }
        result = _flatten_yolo_detections(detections)
        assert len(result) == 1
        assert result[0]["label"] == "helmet"
        assert result[0]["bbox"] == [10.0, 10.0, 50.0, 50.0]
        assert result[0]["source"] == "yolo"

    def test_empty_input(self):
        assert _flatten_yolo_detections({}) == []
        assert _flatten_yolo_detections(None) == []

    def test_all_detections_have_source_yolo(self):
        detections = {
            "images": [
                {
                    "image": "/tmp/img1.jpg",
                    "detections": [
                        {"class_name": "a", "confidence": 0.9, "bbox_xyxy": [10, 10, 50, 50]},
                        {"class_name": "b", "confidence": 0.8, "bbox_xyxy": [60, 60, 100, 100]},
                    ],
                }
            ]
        }
        result = _flatten_yolo_detections(detections)
        for det in result:
            assert det["source"] == "yolo"


# ── _max_severity tests ──────────────────────────────────────────


class TestMaxSeverity:
    def test_critical_is_highest(self):
        assert _max_severity(["low", "medium", "high", "critical"]) == "critical"

    def test_high_over_medium(self):
        assert _max_severity(["low", "medium", "high"]) == "high"

    def test_empty_list(self):
        assert _max_severity([]) == "low"

    def test_single_value(self):
        assert _max_severity(["medium"]) == "medium"

    def test_case_insensitive_ordering(self):
        # The function uses .lower() for ordering but returns the original string.
        # "High" should rank higher than "LOW" even with mixed case.
        result = _max_severity(["LOW", "High"])
        assert result.lower() == "high"


# ── _severity_from_labels tests ──────────────────────────────────


class TestSeverityFromLabels:
    def test_no_hardhat_is_high(self):
        assert _severity_from_labels(["no-hardhat"]) == "high"

    def test_no_helmet_is_high(self):
        assert _severity_from_labels(["no-helmet"]) == "high"

    def test_crane_is_medium(self):
        assert _severity_from_labels(["crane"]) == "medium"

    def test_excavator_is_medium(self):
        assert _severity_from_labels(["excavator"]) == "medium"

    def test_unknown_is_low(self):
        assert _severity_from_labels(["person", "car"]) == "low"


# ── _has_high_risk_label tests ───────────────────────────────────


class TestHasHighRiskLabel:
    def test_no_hardhat(self):
        assert _has_high_risk_label(["no-hardhat"]) is True

    def test_crane(self):
        assert _has_high_risk_label(["crane"]) is True

    def test_safe_labels(self):
        assert _has_high_risk_label(["helmet", "vest"]) is False


# ── _looks_like_image tests ──────────────────────────────────────


class TestLooksLikeImage:
    def test_jpg(self):
        assert _looks_like_image("/tmp/test.jpg") is True

    def test_jpeg(self):
        assert _looks_like_image("/tmp/test.jpeg") is True

    def test_png(self):
        assert _looks_like_image("/tmp/test.png") is True

    def test_webp(self):
        assert _looks_like_image("/tmp/test.webp") is True

    def test_non_image(self):
        assert _looks_like_image("/tmp/test.txt") is False
        assert _looks_like_image("/tmp/test.json") is False

    def test_uppercase_extension(self):
        assert _looks_like_image("/tmp/test.JPG") is True


# ── _tool_data tests ─────────────────────────────────────────────


class TestToolData:
    def test_valid_data(self):
        result = {"data": {"key": "value"}}
        assert _tool_data(result) == {"key": "value"}

    def test_no_data_key(self):
        result = {"ok": True}
        assert _tool_data(result) == {}

    def test_none_input(self):
        assert _tool_data(None) == {}

    def test_data_not_dict(self):
        result = {"data": "not a dict"}
        assert _tool_data(result) == {}


# ── _first_file_path tests ───────────────────────────────────────


class TestFirstFilePath:
    def test_valid_files_list(self):
        result = {"files": [{"path": "/tmp/test.jpg", "name": "test.jpg"}]}
        assert _first_file_path(result) == "/tmp/test.jpg"

    def test_empty_files(self):
        assert _first_file_path({"files": []}) is None

    def test_no_files_key(self):
        assert _first_file_path({}) is None

    def test_none_input(self):
        assert _first_file_path(None) is None


# ── _build_candidates_from_merged tests ──────────────────────────


class TestBuildCandidatesFromMerged:
    def test_empty_merged(self):
        candidates = _build_candidates_from_merged([], "task-123", "B2", "hybrid")
        assert len(candidates) == 1
        assert candidates[0]["id"] == "visual-review"
        assert candidates[0]["source_mix"] == "hybrid"
        assert candidates[0]["severity"] == "low"

    def test_with_detections(self):
        merged = [
            {"bbox": [10, 10, 50, 50], "label": "helmet", "confidence": 0.9, "source": "hybrid",
             "description": "no helmet", "severity": "high", "suggested_action": "stop work"},
        ]
        candidates = _build_candidates_from_merged(merged, "task-123", "B2", "hybrid")
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate["source_mix"] == "hybrid"
        assert candidate["severity"] == "high"
        assert candidate["risk_level"] == "high"
        assert len(candidate["detection_details"]) == 1
        assert candidate["detection_details"][0]["label"] == "helmet"
        assert candidate["detection_details"][0]["source"] == "hybrid"

    def test_max_severity_from_multiple(self):
        merged = [
            {"bbox": [10, 10, 50, 50], "label": "helmet", "confidence": 0.9, "source": "hybrid",
             "description": "ok", "severity": "low", "suggested_action": "ok"},
            {"bbox": [60, 60, 100, 100], "label": "crane", "confidence": 0.8, "source": "hybrid",
             "description": "danger", "severity": "critical", "suggested_action": "stop"},
        ]
        candidates = _build_candidates_from_merged(merged, "task-123", "B2", "hybrid")
        assert candidates[0]["severity"] == "critical"
        assert candidates[0]["risk_level"] == "critical"

    def test_candidate_has_all_required_fields(self):
        merged = [
            {"bbox": [10, 10, 50, 50], "label": "helmet", "confidence": 0.9, "source": "hybrid",
             "description": "no helmet", "severity": "high", "suggested_action": "stop work"},
        ]
        candidates = _build_candidates_from_merged(merged, "task-123", "B2", "hybrid")
        c = candidates[0]
        required_fields = {"id", "title", "risk_level", "area", "description", "labels",
                          "task_id", "source_mix", "severity", "suggested_action", "detection_details"}
        assert required_fields.issubset(set(c.keys()))


# ── _build_candidates tests (YOLO fallback path) ─────────────────


class TestBuildCandidatesYoloFallback:
    def test_no_detections(self):
        request = VisualPatrolDraftRequest()
        vlm_result = {"task_id": "test-123", "ok": True}
        candidates = _build_candidates({}, request, vlm_result, "B2", merged_detections=None, source_mix="yolo")
        assert len(candidates) == 1
        assert candidates[0]["id"] == "visual-review"
        assert candidates[0]["severity"] == "low"
        assert candidates[0]["source_mix"] == "yolo"

    def test_with_yolo_detections(self):
        detections = {
            "images": [
                {
                    "image": "/tmp/img1.jpg",
                    "detections": [
                        {"class_name": "no-hardhat", "confidence": 0.9, "bbox_xyxy": [10, 10, 50, 50]},
                    ],
                }
            ]
        }
        request = VisualPatrolDraftRequest()
        vlm_result = {"task_id": "test-123", "ok": True}
        candidates = _build_candidates(detections, request, vlm_result, "B2", merged_detections=None, source_mix="yolo")
        assert len(candidates) == 1
        assert candidates[0]["source_mix"] == "yolo"
        assert candidates[0]["severity"] == "high"
        assert candidates[0]["risk_level"] == "high"

    def test_merged_takes_precedence(self):
        """When merged_detections is provided, should use enhanced path."""
        merged = [
            {"bbox": [10, 10, 50, 50], "label": "helmet", "confidence": 0.9, "source": "hybrid",
             "description": "no helmet", "severity": "high", "suggested_action": "stop work"},
        ]
        request = VisualPatrolDraftRequest()
        vlm_result = {"task_id": "test-123", "ok": True}
        candidates = _build_candidates({}, request, vlm_result, "B2", merged_detections=merged, source_mix="hybrid")
        assert candidates[0]["source_mix"] == "hybrid"
        assert candidates[0]["severity"] == "high"
        assert len(candidates[0]["detection_details"]) == 1


# ── Service flow tests ───────────────────────────────────────────


def test_build_visual_patrol_draft_uses_local_source_without_snapshot():
    fake_vlm = {
        "ok": True,
        "task_id": "vlm-test-1",
        "data": {
            "detections": {
                "images": [
                    {
                        "image": "/tmp/site.jpg",
                        "detections": [
                            {
                                "class_name": "NO-Hardhat",
                                "confidence": 0.91,
                                "bbox_xyxy": [10, 20, 80, 120],
                            }
                        ],
                    }
                ]
            }
        },
    }

    with patch("chitung_center.visual_patrol_service.toolbox_client.call_tool", new_callable=AsyncMock) as call_tool:
        call_tool.return_value = fake_vlm
        result = asyncio.run(
            build_visual_patrol_draft(
                VisualPatrolDraftRequest(
                    source="/tmp/site.jpg",
                    area="B2",
                    contractor="Demo Contractor",
                    analysis_mode="yolo_only",
                    vlm_enabled=False,
                )
            )
        )

    assert result["ok"] is True
    assert result["snapshot"] is None
    assert result["source"] == "/tmp/site.jpg"
    assert result["candidates"]
    assert result["confirm_payload"]["detections"] == fake_vlm["data"]["detections"]
    assert result["confirm_payload"]["task_id"] == "vlm-test-1"
    call_tool.assert_awaited_once_with(
        "run_vlm_detection_batch",
        {"source": "/tmp/site.jpg", "conf": None, "worker_only": False, "machinery_only": False},
    )


def test_confirm_visual_patrol_candidate_rejects_empty_payload():
    result = asyncio.run(confirm_visual_patrol_candidate(VisualPatrolConfirmRequest()))

    assert result["ok"] is False
    assert result["error"] == "missing_visual_evidence"
    assert "No visual detections" in result["message"]


def test_confirm_visual_patrol_candidate_returns_created_case_id():
    tool_result = {
        "ok": True,
        "data": {
            "case": {
                "data": {
                    "case_id": 42,
                    "case_key": "abc123",
                }
            }
        },
    }
    request = VisualPatrolConfirmRequest(
        detections={"images": [{"image": "/tmp/site.jpg", "detections": []}]},
        task_id="vlm-test-1",
        image_path="/tmp/site.jpg",
        area="B2",
        contractor="Demo Contractor",
        description="B2 visual safety candidate",
    )

    with patch("chitung_center.visual_patrol_service.toolbox_client.call_tool", new_callable=AsyncMock) as call_tool:
        call_tool.return_value = tool_result
        result = asyncio.run(confirm_visual_patrol_candidate(request))

    assert result["ok"] is True
    assert result["case_id"] == 42
    assert result["message"] == "Visual patrol candidate confirmed and converted to safety case."
    call_tool.assert_awaited_once_with(
        "create_case_from_vlm",
        {
            "detections": request.detections,
            "vlm_result_path": None,
            "task_id": "vlm-test-1",
            "image_path": "/tmp/site.jpg",
            "area": "B2",
            "contractor": "Demo Contractor",
            "description": "B2 visual safety candidate",
        },
    )


# ── VisualPatrolDraftRequest model tests ─────────────────────────


class TestVisualPatrolDraftRequest:
    def test_defaults(self):
        req = VisualPatrolDraftRequest()
        assert req.analysis_mode == "hybrid"
        assert req.yolo_conf_threshold == 0.45
        assert req.vlm_enabled is True

    def test_yolo_only_mode(self):
        req = VisualPatrolDraftRequest(analysis_mode="yolo_only", vlm_enabled=False)
        assert req.analysis_mode == "yolo_only"
        assert req.vlm_enabled is False

    def test_custom_conf_threshold(self):
        req = VisualPatrolDraftRequest(yolo_conf_threshold=0.6)
        assert req.yolo_conf_threshold == 0.6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
