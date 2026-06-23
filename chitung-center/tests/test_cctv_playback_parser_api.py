from __future__ import annotations

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.app import app


def test_cctv_playback_parse_api_returns_camera_rows():
    client = TestClient(app)

    response = client.post(
        "/api/config/cctv-playback-info/parse",
        json={
            "text": """
Cam12
EZOPEN(標清)
ezopen://open.ezviz.com/E48203280/2.live
FLV(標清)
https://vtmsgpzl.ezvizlife.com:9188/v3/openlive/E48203280_2_2.flv?expire=1&id=2
"""
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["cameras"][0]["id"] == "cam-12"
    assert payload["cameras"][0]["source_type"] == "csmart_player"
    assert payload["cameras"][0]["csmart_channel_number"] == 2
