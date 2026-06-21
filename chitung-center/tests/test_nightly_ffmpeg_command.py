from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

import nightly_patrol  # type: ignore[import-untyped]


def test_default_ffmpeg_bin_resolves_to_an_existing_executable():
    ffmpeg_bin = Path(nightly_patrol.FFMPEG_BIN)

    assert ffmpeg_bin.exists()
    assert os.access(ffmpeg_bin, os.X_OK)


def test_ffmpeg_capture_command_keeps_rtmp_options_for_rtmp_stream():
    cmd = nightly_patrol._build_ffmpeg_capture_command(
        "rtmp://example.test/live/stream",
        Path("/tmp/frame.jpg"),
        timeout=12,
    )

    assert "-rtmp_live" in cmd
    assert "-update" in cmd
    assert "rtmp://example.test/live/stream" in cmd


def test_ffmpeg_capture_command_omits_rtmp_options_for_http_flv_stream():
    cmd = nightly_patrol._build_ffmpeg_capture_command(
        "https://example.test/openlive/camera.flv?token=demo",
        Path("/tmp/frame.jpg"),
        timeout=12,
    )

    assert "-rtmp_live" not in cmd
    assert "-update" in cmd
    assert "https://example.test/openlive/camera.flv?token=demo" in cmd


def test_camera_result_serializes_fallback_snapshot_metadata():
    result = nightly_patrol.CameraResult(
        camera_id="cam-01",
        camera_name="测试摄像头",
        area="施工区域",
        success=True,
    )
    result.snapshot_source = "fallback"
    result.fallback_used = True
    result.fallback_image = "sample.jpg"
    result.fallback_reason = "视频流不可用"

    payload = result.to_dict()

    assert payload["snapshot_source"] == "fallback"
    assert payload["fallback_used"] is True
    assert payload["fallback_image"] == "sample.jpg"
    assert payload["fallback_reason"] == "视频流不可用"


def test_vlm_enhance_batch_serializes_prompt_roi_and_raw_model_response(monkeypatch, tmp_path):
    from PIL import Image

    source = tmp_path / "source.jpg"
    Image.new("RGB", (120, 120), (255, 255, 255)).save(source)

    async def fake_call_vlm_api(base64_image: str, prompt: str):
        return {
            "description": "机械半径内疑似有人靠近",
            "severity": "high",
            "suggested_action": "立即复核并清场",
            "_audit": {
                "prompt": prompt,
                "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                "raw_response": '{"description":"机械半径内疑似有人靠近","severity":"high","suggested_action":"立即复核并清场"}',
                "model_request": {"model": "glm-test", "messages": [{"role": "user"}]},
                "model_response": {"choices": [{"message": {"content": "raw text"}}]},
            },
        }

    monkeypatch.setattr(nightly_patrol, "crop_roi", lambda *_args, **_kwargs: "roi-base64")
    monkeypatch.setattr(nightly_patrol, "call_vlm_api", fake_call_vlm_api)
    monkeypatch.setattr(nightly_patrol, "VLM_MAX_TARGETS_PER_CAMERA", 1)

    detections = asyncio.run(
        nightly_patrol.vlm_enhance_batch(
            str(source),
            [nightly_patrol.Detection(bbox=[10, 10, 80, 90], label="挖掘机", confidence=0.91)],
            context="施工區域01",
            inspection_prompt="检查施工机械和人员靠近风险",
        )
    )

    payload = detections[0].to_dict()

    assert payload["source"] == "hybrid"
    assert payload["description"] == "机械半径内疑似有人靠近"
    assert payload["vlm_audit"]["prompt"].startswith("你是工地安全监控专家")
    assert payload["vlm_audit"]["raw_response"].startswith('{"description"')
    assert payload["vlm_audit"]["roi_image"]["base64"] == "roi-base64"
    assert payload["vlm_audit"]["roi_image"]["data_url"].startswith("data:image/jpeg;base64,")
    assert payload["vlm_audit"]["model_request"]["model"] == "glm-test"
    assert payload["vlm_audit"]["model_response"]["choices"][0]["message"]["content"] == "raw text"


def test_vlm_raw_response_uses_reasoning_content_when_message_content_is_empty():
    raw = nightly_patrol._extract_vlm_raw_response(
        {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "reasoning_content": "模型推理内容和原始文字",
                    }
                }
            ]
        }
    )

    assert raw == "模型推理内容和原始文字"


def test_annotation_font_resolves_real_cjk_font_on_macos(monkeypatch):
    macos_cjk_fonts = [
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/System/Library/Fonts/STHeiti Light.ttc"),
        Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    ]
    if not any(path.exists() for path in macos_cjk_fonts):
        pytest.skip("No macOS CJK system font is available on this host")

    monkeypatch.setattr(nightly_patrol, "_zh_font", None)
    monkeypatch.setattr(nightly_patrol, "_zh_font_small", None)

    font = nightly_patrol._get_zh_font(22)

    assert Path(str(font.path)) in macos_cjk_fonts
    assert font.getname()[0] != "Aileron"


def test_annotation_label_uses_readable_text_on_bright_background(tmp_path, monkeypatch):
    import numpy as np
    from PIL import Image

    monkeypatch.setattr(nightly_patrol, "_zh_font", None)
    monkeypatch.setattr(nightly_patrol, "_zh_font_small", None)
    source = tmp_path / "source.jpg"
    output = tmp_path / "annotated.jpg"
    Image.new("RGB", (260, 180), (255, 255, 255)).save(source)

    nightly_patrol.draw_annotations(
        str(source),
        [
            nightly_patrol.Detection(
                bbox=[40, 70, 180, 150],
                label="流动式起重机",
                confidence=0.83,
                source="hybrid",
                severity="medium",
            )
        ],
        str(output),
        "施工区域01",
    )

    image = Image.open(output).convert("RGB")
    label_region = np.array(image.crop((40, 35, 220, 75)))
    dark_pixels = int(
        (
            (label_region[:, :, 0] < 80)
            & (label_region[:, :, 1] < 80)
            & (label_region[:, :, 2] < 80)
        ).sum()
    )

    assert dark_pixels > 10


def test_annotation_label_near_top_is_not_hidden_by_info_bar(tmp_path, monkeypatch):
    import numpy as np
    from PIL import Image

    monkeypatch.setattr(nightly_patrol, "_zh_font", None)
    monkeypatch.setattr(nightly_patrol, "_zh_font_small", None)
    source = tmp_path / "source.jpg"
    output = tmp_path / "annotated.jpg"
    Image.new("RGB", (260, 180), (255, 255, 255)).save(source)

    nightly_patrol.draw_annotations(
        str(source),
        [
            nightly_patrol.Detection(
                bbox=[40, 30, 180, 130],
                label="塔式起重机",
                confidence=0.80,
                source="hybrid",
                severity="medium",
            )
        ],
        str(output),
        "施工区域01",
    )

    image = Image.open(output).convert("RGB")
    top_label_region = np.array(image.crop((35, 0, 220, 42)))
    yellow_pixels = int(
        (
            (top_label_region[:, :, 0] > 180)
            & (top_label_region[:, :, 1] > 180)
            & (top_label_region[:, :, 2] < 80)
        ).sum()
    )

    assert yellow_pixels > 50


def test_annotation_description_uses_readable_text_on_bright_background(tmp_path, monkeypatch):
    import numpy as np
    from PIL import Image

    monkeypatch.setattr(nightly_patrol, "_zh_font", None)
    monkeypatch.setattr(nightly_patrol, "_zh_font_small", None)
    source = tmp_path / "source.jpg"
    output = tmp_path / "annotated.jpg"
    Image.new("RGB", (300, 220), (255, 255, 255)).save(source)

    nightly_patrol.draw_annotations(
        str(source),
        [
            nightly_patrol.Detection(
                bbox=[40, 60, 180, 140],
                label="挖掘机",
                confidence=0.89,
                source="hybrid",
                description="VLM返回解析失败",
                severity="medium",
                suggested_action="建议人工复核",
            )
        ],
        str(output),
        "施工区域01",
    )

    image = Image.open(output).convert("RGB")
    description_region = np.array(image.crop((40, 142, 260, 170)))
    dark_pixels = int(
        (
            (description_region[:, :, 0] < 80)
            & (description_region[:, :, 1] < 80)
            & (description_region[:, :, 2] < 80)
        ).sum()
    )

    assert dark_pixels > 10


def test_patrol_camera_prefers_csmart_snapshot_before_ffmpeg(monkeypatch, tmp_path):
    captured: dict[str, str] = {}

    def fake_download_http_image(url: str, output_path: Path, timeout: int = 10, retries: int = 2) -> bool:
        captured["url"] = url
        output_path.write_bytes(b"snapshot-bytes")
        return True

    def fail_if_ffmpeg_runs(*_args, **_kwargs):
        raise AssertionError("ffmpeg should not run when a stable C-SMART snapshot is available")

    monkeypatch.setattr(nightly_patrol, "capture_rtmp_frame", fail_if_ffmpeg_runs)
    monkeypatch.setattr(nightly_patrol, "download_http_image", fake_download_http_image)
    monkeypatch.setattr(nightly_patrol, "_get_test_image_fallback", lambda _camera_id: "local-sample.jpg")
    monkeypatch.setattr(nightly_patrol, "run_yolo_detection", lambda _path: [])
    monkeypatch.setattr(
        nightly_patrol,
        "draw_annotations",
        lambda source_path, _detections, annotated_path, _camera_name: Path(annotated_path).write_bytes(
            Path(source_path).read_bytes()
        ),
    )

    result = asyncio.run(
        nightly_patrol.patrol_camera(
            {
                "id": "cam-01",
                "name": "测试摄像头",
                "area": "施工区域",
                "rtmp_url": "https://example.test/broken.flv",
                "snapshot_url": "https://example.test/csmart-snapshot.jpg",
            },
            tmp_path,
            vlm_enabled=False,
        )
    )

    assert result.success is True
    assert captured["url"] == "https://example.test/csmart-snapshot.jpg"
    assert result.fallback_used is False
    assert result.snapshot_source == "csmart_screenshot"
    assert result.fallback_image == "csmart-snapshot.jpg"
    assert result.fallback_reason == ""


def test_patrol_camera_tries_all_csmart_snapshot_candidates_before_ffmpeg(monkeypatch, tmp_path):
    attempted_urls: list[str] = []

    def fake_download_http_image(url: str, output_path: Path, timeout: int = 10, retries: int = 2) -> bool:
        attempted_urls.append(url)
        if url.endswith("/fresh.jpg"):
            output_path.write_bytes(b"fresh-snapshot-bytes")
            return True
        return False

    def fail_if_ffmpeg_runs(*_args, **_kwargs):
        raise AssertionError("ffmpeg should not run until every C-SMART snapshot candidate fails")

    monkeypatch.setattr(nightly_patrol, "capture_rtmp_frame", fail_if_ffmpeg_runs)
    monkeypatch.setattr(nightly_patrol, "download_http_image", fake_download_http_image)
    monkeypatch.setattr(nightly_patrol, "_get_test_image_fallback", lambda _camera_id: "local-sample.jpg")
    monkeypatch.setattr(nightly_patrol, "run_yolo_detection", lambda _path: [])
    monkeypatch.setattr(
        nightly_patrol,
        "draw_annotations",
        lambda source_path, _detections, annotated_path, _camera_name: Path(annotated_path).write_bytes(
            Path(source_path).read_bytes()
        ),
    )

    result = asyncio.run(
        nightly_patrol.patrol_camera(
            {
                "id": "cam-01",
                "name": "测试摄像头",
                "area": "施工区域",
                "rtmp_url": "https://example.test/broken.flv",
                "snapshot_url": "https://example.test/stale.jpg",
                "screenshot_url": "https://example.test/fresh.jpg",
            },
            tmp_path,
            vlm_enabled=False,
        )
    )

    assert attempted_urls == [
        "https://example.test/stale.jpg",
        "https://example.test/fresh.jpg",
    ]
    assert result.snapshot_source == "csmart_screenshot"
    assert result.fallback_used is False
    assert result.fallback_image == "fresh.jpg"


def test_patrol_camera_records_csmart_snapshot_attempts(monkeypatch, tmp_path):
    def fake_download_http_image(url: str, output_path: Path, timeout: int = 10, retries: int = 2) -> bool:
        if url.endswith("/fresh.jpg"):
            output_path.write_bytes(b"fresh-snapshot-bytes")
            return True
        return False

    monkeypatch.setattr(nightly_patrol, "download_http_image", fake_download_http_image)
    monkeypatch.setattr(nightly_patrol, "capture_rtmp_frame", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(nightly_patrol, "_get_test_image_fallback", lambda _camera_id: None)
    monkeypatch.setattr(nightly_patrol, "run_yolo_detection", lambda _path: [])
    monkeypatch.setattr(
        nightly_patrol,
        "draw_annotations",
        lambda source_path, _detections, annotated_path, _camera_name: Path(annotated_path).write_bytes(
            Path(source_path).read_bytes()
        ),
    )

    result = asyncio.run(
        nightly_patrol.patrol_camera(
            {
                "id": "cam-01",
                "name": "测试摄像头",
                "area": "施工区域",
                "rtmp_url": "https://example.test/broken.flv",
                "snapshot_url": "https://example.test/stale.jpg",
                "screenshot_url": "https://example.test/fresh.jpg",
            },
            tmp_path,
            vlm_enabled=False,
        )
    )

    assert result.to_dict()["capture_attempts"] == [
        {"method": "csmart_screenshot", "url": "https://example.test/stale.jpg", "ok": False},
        {"method": "csmart_screenshot", "url": "https://example.test/fresh.jpg", "ok": True},
    ]


def test_patrol_camera_does_not_use_local_fallback_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("ALLOW_LOCAL_SNAPSHOT_FALLBACK", raising=False)
    monkeypatch.setattr(nightly_patrol, "download_http_image", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(nightly_patrol, "capture_rtmp_frame", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        nightly_patrol,
        "_get_test_image_fallback",
        lambda _camera_id: (_ for _ in ()).throw(AssertionError("local fallback image must not be used")),
    )
    monkeypatch.setattr(
        nightly_patrol,
        "run_yolo_detection",
        lambda _path: (_ for _ in ()).throw(AssertionError("YOLO must not run without a real camera frame")),
    )

    result = asyncio.run(
        nightly_patrol.patrol_camera(
            {
                "id": "cam-01",
                "name": "测试摄像头",
                "area": "施工区域",
                "rtmp_url": "https://example.test/broken.flv",
                "snapshot_url": "https://example.test/stale.jpg",
            },
            tmp_path,
            vlm_enabled=False,
        )
    )

    assert result.success is False
    assert result.snapshot_source == "failed"
    assert result.fallback_used is False
    assert result.fallback_image == ""
    assert "真实摄像头抽帧失败" in result.error


def test_download_http_image_retries_transient_failure(monkeypatch, tmp_path):
    calls = {"count": 0}

    class FakeResponse:
        content = b"image-bytes"

        def raise_for_status(self):
            return None

    def fake_get(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise nightly_patrol.httpx.TimeoutException("transient timeout")
        return FakeResponse()

    monkeypatch.setattr(nightly_patrol.httpx, "get", fake_get)
    output_path = tmp_path / "frame.jpg"

    assert nightly_patrol.download_http_image("https://example.test/frame.jpg", output_path, timeout=1)
    assert calls["count"] == 2
    assert output_path.read_bytes() == b"image-bytes"
