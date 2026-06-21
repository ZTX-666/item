from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.visual_patrol_batch_service import _configure_nightly_vlm, _sync_cameras, run_guardian_patrol


def test_run_guardian_patrol_passes_inspection_prompt_to_nightly(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_run_patrol(**kwargs):
        captured.update(kwargs)
        return {
            "patrol_id": "patrol-1",
            "success_count": 1,
            "total_detections": 0,
            "cameras": [],
        }

    monkeypatch.setattr(
        "chitung_center.visual_patrol_batch_service._load_nightly_patrol",
        lambda: SimpleNamespace(run_patrol=fake_run_patrol),
    )
    monkeypatch.setattr(
        "chitung_center.visual_patrol_batch_service._sync_cameras",
        lambda nightly: [{"id": "cam-1", "name": "施工區域01", "area": "施工區域", "rtmp_url": "rtmp://demo"}],
    )
    monkeypatch.setattr(
        "chitung_center.visual_patrol_batch_service._rewrite_paths",
        lambda summary: summary,
    )

    result = asyncio.run(
        run_guardian_patrol(
            camera_id="cam-1",
            vlm_enabled=True,
            inspection_prompt="重点检查未戴安全帽。",
        )
    )

    assert result["ok"] is True
    assert captured["camera_filter"] == "cam-1"
    assert captured["vlm_enabled"] is True
    assert captured["inspection_prompt"] == "重点检查未戴安全帽。"


def test_configure_nightly_vlm_uses_center_secureeye_settings(monkeypatch):
    fake_nightly = SimpleNamespace(
        VLM_BASE_URL="",
        VLM_API_KEY="",
        VLM_MODEL="glm-4v",
        VLM_MAX_CONCURRENCY=4,
    )
    monkeypatch.delenv("SECUREEYE_BASE_URL", raising=False)
    monkeypatch.delenv("SECUREEYE_API_KEY", raising=False)
    monkeypatch.delenv("SECUREEYE_MODEL", raising=False)
    monkeypatch.delenv("SECUREEYE_MAX_CONCURRENCY", raising=False)
    monkeypatch.setattr(
        "chitung_center.visual_patrol_batch_service.settings.secureeye_base_url",
        "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    )
    monkeypatch.setattr("chitung_center.visual_patrol_batch_service.settings.secureeye_api_key", "test-key")
    monkeypatch.setattr("chitung_center.visual_patrol_batch_service.settings.secureeye_model", "glm-4.5v")
    monkeypatch.setattr("chitung_center.visual_patrol_batch_service.settings.secureeye_max_concurrency", 1)
    monkeypatch.setattr("chitung_center.visual_patrol_batch_service.settings.secureeye_max_targets_per_camera", 2)

    _configure_nightly_vlm(fake_nightly)

    assert fake_nightly.VLM_BASE_URL == "https://open.bigmodel.cn/api/paas/v4"
    assert fake_nightly.VLM_API_KEY == "test-key"
    assert fake_nightly.VLM_MODEL == "glm-4.5v"
    assert fake_nightly.VLM_MAX_CONCURRENCY == 1
    assert fake_nightly.VLM_MAX_TARGETS_PER_CAMERA == 2


def test_sync_cameras_enriches_stream_and_screenshot_from_csmart_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "csmart-channel-list-latest.json"
    cache_path.write_text(
        json.dumps(
            {
                "channels": [
                    {
                        "id": "channel-6",
                        "cameraName": "斜坡03",
                        "number": 6,
                        "flv": "https://example.test/live.flv",
                        "screenshot": "https://example.test/snapshot.jpg",
                        "snapshot": "https://example.test/still.jpg",
                        "captureUrl": "https://example.test/capture.jpg",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CCTV_CHANNEL_CACHE_FILE", str(cache_path))
    monkeypatch.setenv("CCTV_GATEWAY_BASE_URL", "http://127.0.0.1:3457")
    monkeypatch.setattr(
        "chitung_center.visual_patrol_batch_service.get_app_config",
        lambda: {
            "cameras": [
                {
                    "id": "cam-slope-03",
                    "name": "斜坡03",
                    "area": "斜坡",
                    "rtmp_url": "https://stale.example.test/old.flv",
                    "snapshot_url": "https://stale.example.test/old-snapshot.jpg",
                    "enabled": True,
                    "csmart_channel_number": 6,
                    "csmart_channel_id": "channel-6",
                }
            ]
        },
    )
    nightly = SimpleNamespace(CAMERAS=[])

    cameras = _sync_cameras(nightly)

    assert cameras[0]["rtmp_url"] == "https://example.test/live.flv"
    assert cameras[0]["snapshot_url"] == "http://127.0.0.1:3457/api/csmart/snapshot/6"
    assert cameras[0]["snapshot_remote_url"] == "https://example.test/snapshot.jpg"
    assert cameras[0]["snapshot_url_candidates"] == [
        "http://127.0.0.1:3457/api/csmart/snapshot/6",
        "https://example.test/snapshot.jpg",
        "https://example.test/still.jpg",
        "https://example.test/capture.jpg",
        "https://stale.example.test/old-snapshot.jpg",
    ]
    assert nightly.CAMERAS == cameras
