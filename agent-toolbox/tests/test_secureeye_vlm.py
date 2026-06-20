"""Unit tests for SecureEye VLM module — verifies core algorithms and data flow."""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from agent_toolbox.tools.secureeye_vlm import (
    SecureEyeBatchAnalyzeRequest,
    SecureEyeCropAnalyzeRequest,
    SecureEyeMergeRequest,
    _build_vlm_prompt,
    _compute_iou,
    _parse_vlm_json,
    analyze_batch,
    analyze_crop,
    crop_roi,
    merge_results,
)


# ── _compute_iou tests ──────────────────────────────────────────


class TestComputeIoU:
    def test_identical_boxes(self):
        box = [10, 10, 50, 50]
        assert _compute_iou(box, box) == pytest.approx(1.0)

    def test_no_overlap(self):
        box_a = [0, 0, 10, 10]
        box_b = [20, 20, 30, 30]
        assert _compute_iou(box_a, box_b) == 0.0

    def test_partial_overlap(self):
        box_a = [0, 0, 10, 10]
        box_b = [5, 5, 15, 15]
        # intersection = 5*5 = 25, area_a = 100, area_b = 100, union = 175
        expected = 25.0 / 175.0
        assert _compute_iou(box_a, box_b) == pytest.approx(expected)

    def test_contained_box(self):
        outer = [0, 0, 100, 100]
        inner = [10, 10, 20, 20]
        # intersection = 10*10 = 100, area_outer = 10000, area_inner = 100, union = 10000
        expected = 100.0 / 10000.0
        assert _compute_iou(outer, inner) == pytest.approx(expected)

    def test_zero_area_box(self):
        # Degenerate box with zero area
        assert _compute_iou([5, 5, 5, 5], [0, 0, 10, 10]) == 0.0

    def test_touching_boxes(self):
        # Boxes that share an edge but don't overlap
        box_a = [0, 0, 10, 10]
        box_b = [10, 0, 20, 10]
        assert _compute_iou(box_a, box_b) == 0.0


# ── _parse_vlm_json tests ────────────────────────────────────────


class TestParseVlmJson:
    def test_valid_json(self):
        raw = '{"description": "worker without helmet", "severity": "high", "suggested_action": "stop work"}'
        result = _parse_vlm_json(raw)
        assert result["description"] == "worker without helmet"
        assert result["severity"] == "high"
        assert result["suggested_action"] == "stop work"

    def test_json_embedded_in_text(self):
        raw = 'The analysis result is: {"description": "crane operating", "severity": "medium", "suggested_action": "monitor"} as shown.'
        result = _parse_vlm_json(raw)
        assert result["description"] == "crane operating"
        assert result["severity"] == "medium"

    def test_empty_string(self):
        result = _parse_vlm_json("")
        assert result["description"] == "VLM analysis unavailable"
        assert result["severity"] == "medium"
        assert result["suggested_action"] == "请人工复核"

    def test_non_json_text(self):
        raw = "This is just plain text with no JSON."
        result = _parse_vlm_json(raw)
        assert "medium" == result["severity"]
        assert "请人工复核" == result["suggested_action"]

    def test_json_with_extra_fields(self):
        raw = '{"description": "test", "severity": "low", "suggested_action": "ok", "extra": "ignored"}'
        result = _parse_vlm_json(raw)
        assert result["description"] == "test"
        assert result["extra"] == "ignored"


# ── _build_vlm_prompt tests ──────────────────────────────────────


class TestBuildVlmPrompt:
    def test_prompt_with_label_only(self):
        prompt = _build_vlm_prompt("helmet", "")
        assert "helmet" in prompt
        assert "JSON" in prompt
        assert "severity" in prompt

    def test_prompt_with_context(self):
        prompt = _build_vlm_prompt("crane", "B2施工區域")
        assert "crane" in prompt
        assert "B2施工區域" in prompt
        assert "JSON" in prompt


# ── crop_roi tests ───────────────────────────────────────────────


class TestCropRoi:
    def test_crop_returns_base64_jpeg(self):
        # Create a test image
        img = Image.new("RGB", (640, 480), color=(255, 0, 0))
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            img.save(tmp.name, "JPEG")
            tmp_path = tmp.name

        try:
            b64 = crop_roi(tmp_path, [100, 100, 200, 200], padding_ratio=0.1)
            # Verify it's valid base64 JPEG
            decoded = base64.b64decode(b64)
            cropped_img = Image.open(io.BytesIO(decoded))
            assert cropped_img.size == (640, 640)  # target_size default
            assert cropped_img.format == "JPEG"
        finally:
            os.unlink(tmp_path)

    def test_crop_with_padding_exceeds_bounds(self):
        img = Image.new("RGB", (100, 100), color=(0, 255, 0))
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img.save(tmp.name, "PNG")
            tmp_path = tmp.name

        try:
            # bbox near edge, padding should be clamped
            b64 = crop_roi(tmp_path, [0, 0, 10, 10], padding_ratio=0.5, target_size=128)
            decoded = base64.b64decode(b64)
            cropped_img = Image.open(io.BytesIO(decoded))
            assert cropped_img.size == (128, 128)
        finally:
            os.unlink(tmp_path)

    def test_crop_full_image_bbox(self):
        img = Image.new("RGB", (200, 200), color=(0, 0, 255))
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            img.save(tmp.name, "JPEG")
            tmp_path = tmp.name

        try:
            b64 = crop_roi(tmp_path, [0, 0, 200, 200], padding_ratio=0.0, target_size=256)
            decoded = base64.b64decode(b64)
            cropped_img = Image.open(io.BytesIO(decoded))
            assert cropped_img.size == (256, 256)
        finally:
            os.unlink(tmp_path)


# ── merge_results tests ──────────────────────────────────────────


class TestMergeResults:
    def test_empty_inputs(self):
        req = SecureEyeMergeRequest(yolo_detections=[], vlm_results=[])
        result = merge_results(req)
        assert result.ok is True
        assert result.data["detections"] == []
        assert result.data["count"] == 0

    def test_hybrid_match(self):
        # YOLO and VLM boxes overlap perfectly → IoU = 1.0 > 0.7
        yolo_dets = [{"bbox": [10, 10, 50, 50], "label": "helmet", "confidence": 0.9}]
        vlm_dets = [{"bbox": [10, 10, 50, 50], "label": "helmet", "confidence": 0.9,
                      "description": "no helmet", "severity": "high", "suggested_action": "stop"}]
        req = SecureEyeMergeRequest(yolo_detections=yolo_dets, vlm_results=vlm_dets, iou_threshold=0.7)
        result = merge_results(req)
        dets = result.data["detections"]
        assert len(dets) == 1
        assert dets[0]["source"] == "hybrid"
        assert dets[0]["severity"] == "high"
        assert dets[0]["description"] == "no helmet"

    def test_yolo_only_no_match(self):
        yolo_dets = [{"bbox": [0, 0, 10, 10], "label": "crane", "confidence": 0.88}]
        vlm_dets = [{"bbox": [100, 100, 200, 200], "label": "worker", "confidence": 0.8,
                      "description": "worker", "severity": "low", "suggested_action": "ok"}]
        req = SecureEyeMergeRequest(yolo_detections=yolo_dets, vlm_results=vlm_dets, iou_threshold=0.7)
        result = merge_results(req)
        dets = result.data["detections"]
        assert len(dets) == 2
        sources = [d["source"] for d in dets]
        assert "yolo" in sources
        assert "vlm" in sources

    def test_vlm_only_no_match(self):
        yolo_dets = []
        vlm_dets = [{"bbox": [10, 10, 50, 50], "label": "excavator", "confidence": 0.7,
                      "description": "excavator working", "severity": "medium", "suggested_action": "monitor"}]
        req = SecureEyeMergeRequest(yolo_detections=yolo_dets, vlm_results=vlm_dets, iou_threshold=0.7)
        result = merge_results(req)
        dets = result.data["detections"]
        assert len(dets) == 1
        assert dets[0]["source"] == "vlm"
        assert dets[0]["label"] == "excavator"

    def test_bbox_xyxy_key_fallback(self):
        """YOLO detections may use 'bbox_xyxy' instead of 'bbox'."""
        yolo_dets = [{"bbox_xyxy": [10, 10, 50, 50], "class_name": "helmet", "confidence": 0.9}]
        vlm_dets = [{"bbox": [10, 10, 50, 50], "label": "helmet", "confidence": 0.9,
                      "description": "ok", "severity": "low", "suggested_action": "ok"}]
        req = SecureEyeMergeRequest(yolo_detections=yolo_dets, vlm_results=vlm_dets, iou_threshold=0.7)
        result = merge_results(req)
        dets = result.data["detections"]
        assert len(dets) == 1
        assert dets[0]["source"] == "hybrid"
        assert dets[0]["label"] == "helmet"

    def test_multiple_yolo_one_vlm_match(self):
        yolo_dets = [
            {"bbox": [10, 10, 50, 50], "label": "helmet", "confidence": 0.9},
            {"bbox": [100, 100, 150, 150], "label": "vest", "confidence": 0.7},
        ]
        vlm_dets = [{"bbox": [10, 10, 50, 50], "label": "helmet", "confidence": 0.9,
                      "description": "no helmet", "severity": "high", "suggested_action": "stop"}]
        req = SecureEyeMergeRequest(yolo_detections=yolo_dets, vlm_results=vlm_dets, iou_threshold=0.7)
        result = merge_results(req)
        dets = result.data["detections"]
        assert len(dets) == 2
        sources = sorted(d["source"] for d in dets)
        assert sources == ["hybrid", "yolo"]

    def test_iou_threshold_boundary(self):
        """IoU exactly at threshold should NOT match (uses > not >=)."""
        # Create boxes with known IoU - identical boxes have IoU=1.0
        # For boundary test, use threshold=1.0 so IoU=1.0 is NOT > 1.0
        yolo_dets = [{"bbox": [10, 10, 50, 50], "label": "helmet", "confidence": 0.9}]
        vlm_dets = [{"bbox": [10, 10, 50, 50], "label": "helmet", "confidence": 0.9,
                      "description": "no helmet", "severity": "high", "suggested_action": "stop"}]
        req = SecureEyeMergeRequest(yolo_detections=yolo_dets, vlm_results=vlm_dets, iou_threshold=1.0)
        result = merge_results(req)
        dets = result.data["detections"]
        # IoU=1.0 is NOT > 1.0, so both should appear separately
        assert len(dets) == 2
        sources = sorted(d["source"] for d in dets)
        assert sources == ["vlm", "yolo"]

    def test_all_detections_have_required_fields(self):
        yolo_dets = [{"bbox": [10, 10, 50, 50], "label": "helmet", "confidence": 0.9}]
        vlm_dets = [{"bbox": [10, 10, 50, 50], "label": "helmet", "confidence": 0.9,
                      "description": "no helmet", "severity": "high", "suggested_action": "stop"}]
        req = SecureEyeMergeRequest(yolo_detections=yolo_dets, vlm_results=vlm_dets)
        result = merge_results(req)
        for det in result.data["detections"]:
            assert "bbox" in det
            assert "label" in det
            assert "confidence" in det
            assert "source" in det
            assert "description" in det
            assert "severity" in det
            assert "suggested_action" in det


# ── analyze_crop tests (with mocked VLM API) ─────────────────────


class TestAnalyzeCrop:
    def test_vlm_success(self):
        """VLM call succeeds → source='vlm'"""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            Image.new("RGB", (640, 480), (255, 0, 0)).save(tmp.name, "JPEG")
            tmp_path = tmp.name

        try:
            req = SecureEyeCropAnalyzeRequest(
                image_path=tmp_path,
                bbox=[100, 100, 200, 200],
                label="helmet",
                confidence=0.85,
            )
            mock_vlm_result = {
                "description": "Worker without helmet",
                "severity": "high",
                "suggested_action": "Stop work immediately",
                "source": "vlm",
            }
            with patch("agent_toolbox.tools.secureeye_vlm._call_vlm_api", new_callable=AsyncMock, return_value=mock_vlm_result):
                result = asyncio.run(analyze_crop(req))

            assert result.ok is True
            assert result.data["source"] == "vlm"
            assert result.data["severity"] == "high"
            assert result.data["label"] == "helmet"
            assert result.data["confidence"] == 0.85
        finally:
            os.unlink(tmp_path)

    def test_vlm_failure_fallback_to_yolo(self):
        """VLM call fails → fallback to source='yolo'"""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            Image.new("RGB", (640, 480), (255, 0, 0)).save(tmp.name, "JPEG")
            tmp_path = tmp.name

        try:
            req = SecureEyeCropAnalyzeRequest(
                image_path=tmp_path,
                bbox=[100, 100, 200, 200],
                label="helmet",
                confidence=0.85,
            )
            with patch("agent_toolbox.tools.secureeye_vlm._call_vlm_api", new_callable=AsyncMock, side_effect=Exception("API timeout")):
                result = asyncio.run(analyze_crop(req))

            assert result.ok is True
            assert result.data["source"] == "yolo"
            assert result.data["label"] == "helmet"
            assert result.data["confidence"] == 0.85
            assert "VLM" in result.summary or "fallback" in result.summary.lower()
        finally:
            os.unlink(tmp_path)

    def test_crop_failure(self):
        """Image file doesn't exist → ok=False"""
        req = SecureEyeCropAnalyzeRequest(
            image_path="/nonexistent/path/image.jpg",
            bbox=[100, 100, 200, 200],
            label="helmet",
            confidence=0.85,
        )
        result = asyncio.run(analyze_crop(req))
        assert result.ok is False
        assert result.error is not None


# ── analyze_batch tests ──────────────────────────────────────────


class TestAnalyzeBatch:
    def test_empty_crops(self):
        req = SecureEyeBatchAnalyzeRequest(image_path="/tmp/test.jpg", crops=[])
        result = asyncio.run(analyze_batch(req))
        assert result.ok is True
        assert result.data["results"] == []
        assert result.data["count"] == 0

    def test_batch_with_vlm_success(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            Image.new("RGB", (640, 480), (255, 0, 0)).save(tmp.name, "JPEG")
            tmp_path = tmp.name

        try:
            crops = [
                {"id": "c1", "bbox": [10, 10, 50, 50], "label": "helmet", "confidence": 0.9},
                {"id": "c2", "bbox": [60, 60, 100, 100], "label": "vest", "confidence": 0.8},
            ]
            req = SecureEyeBatchAnalyzeRequest(image_path=tmp_path, crops=crops, max_concurrency=2)

            mock_vlm_result = {
                "description": "detected",
                "severity": "medium",
                "suggested_action": "review",
                "source": "vlm",
            }
            with patch("agent_toolbox.tools.secureeye_vlm._call_vlm_api", new_callable=AsyncMock, return_value=mock_vlm_result):
                result = asyncio.run(analyze_batch(req))

            assert result.ok is True
            assert result.data["count"] == 2
            assert len(result.data["results"]) == 2
            for r in result.data["results"]:
                assert r["source"] == "vlm"
                assert "crop_id" in r
        finally:
            os.unlink(tmp_path)

    def test_batch_partial_failure(self):
        """One crop VLM fails, another succeeds — both should return results."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            Image.new("RGB", (640, 480), (255, 0, 0)).save(tmp.name, "JPEG")
            tmp_path = tmp.name

        try:
            crops = [
                {"id": "c1", "bbox": [10, 10, 50, 50], "label": "helmet", "confidence": 0.9},
                {"id": "c2", "bbox": [60, 60, 100, 100], "label": "vest", "confidence": 0.8},
            ]
            req = SecureEyeBatchAnalyzeRequest(image_path=tmp_path, crops=crops, max_concurrency=1)

            call_count = [0]
            async def mock_call(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return {"description": "ok", "severity": "low", "suggested_action": "ok", "source": "vlm"}
                raise Exception("VLM timeout for second crop")

            with patch("agent_toolbox.tools.secureeye_vlm._call_vlm_api", side_effect=mock_call):
                result = asyncio.run(analyze_batch(req))

            assert result.ok is True
            assert result.data["count"] == 2
            sources = [r["source"] for r in result.data["results"]]
            assert "vlm" in sources
            assert "yolo" in sources  # fallback for failed crop
        finally:
            os.unlink(tmp_path)


# ── Pydantic model tests ─────────────────────────────────────────


class TestPydanticModels:
    def test_crop_analyze_request_defaults(self):
        req = SecureEyeCropAnalyzeRequest(
            image_path="/test.jpg",
            bbox=[0, 0, 10, 10],
            label="helmet",
            confidence=0.9,
        )
        assert req.padding_ratio == 0.15
        assert req.context == ""

    def test_batch_analyze_request_defaults(self):
        req = SecureEyeBatchAnalyzeRequest(image_path="/test.jpg")
        assert req.crops == []
        assert req.max_concurrency is None
        assert req.context == ""

    def test_merge_request_defaults(self):
        req = SecureEyeMergeRequest()
        assert req.yolo_detections == []
        assert req.vlm_results == []
        assert req.iou_threshold == 0.7

    def test_merge_request_custom_threshold(self):
        req = SecureEyeMergeRequest(iou_threshold=0.5)
        assert req.iou_threshold == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
