from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.models import AppConfigRequest


def test_camera_config_preserves_source_fields():
    request = AppConfigRequest.model_validate(
        {
            "cameras": [
                {
                    "id": "cam-yard-01",
                    "name": "黄埔门岗",
                    "area": "出入口",
                    "source_type": "rtmp",
                    "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com/live",
                    "snapshot_url": "https://example.test/still.jpg",
                    "csmart_channel_number": 6,
                    "csmart_channel_id": "channel-6",
                    "player_screenshot_url": "http://127.0.0.1:3457/api/csmart/player-screenshot/6",
                    "playback_info": {
                        "ezopen_sd": "ezopen://open.ezviz.com/E48203280/6.live",
                        "hls_sd": "https://example.test/live.m3u8",
                        "rtmp_sd": "rtmp://example.test/live",
                        "flv_sd": "https://example.test/live.flv",
                    },
                    "playback_info_raw": "Cam1\nFLV(標清)\nhttps://example.test/live.flv",
                    "inspection_interval_minutes": 30,
                    "remark": "硬件同事提供的 H264 RTMP 流",
                    "enabled": True,
                }
            ]
        }
    )

    camera = request.model_dump()["cameras"][0]

    assert camera["source_type"] == "rtmp"
    assert camera["rtmp_url"] == "rtmp://vtmsgpzl.ezvizlife.com/live"
    assert camera["snapshot_url"] == "https://example.test/still.jpg"
    assert camera["csmart_channel_number"] == 6
    assert camera["csmart_channel_id"] == "channel-6"
    assert camera["player_screenshot_url"] == "http://127.0.0.1:3457/api/csmart/player-screenshot/6"
    assert camera["playback_info"]["flv_sd"] == "https://example.test/live.flv"
    assert "Cam1" in camera["playback_info_raw"]
    assert camera["inspection_interval_minutes"] == 30
    assert camera["remark"] == "硬件同事提供的 H264 RTMP 流"
