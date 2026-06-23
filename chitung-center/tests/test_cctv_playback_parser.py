from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.cctv_playback_parser import parse_cctv_playback_info


def test_parse_cctv_playback_info_extracts_cam_blocks_and_stream_urls():
    text = """
Cam12
播放信息
EZOPEN(標清)
ezopen://open.ezviz.com/E48203280/2.live
EZOPEN(高清)
ezopen://open.ezviz.com/E48203280/2.hd.live
HLS(標清)
https://vtmucyn.ezvizlife.com:8883/v3/openlive/E48203280_2_2.m3u8?expire=1844360286&id=989353631169667072
HLS(高清)
https://vtmucyn.ezvizlife.com:8883/v3/openlive/E48203280_2_1.m3u8?expire=1844360287&id=989353631937224704
RTMP(標清)
rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_2_2?expire=1844352287&id=989353632875663360
RTMP(高清)
rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_2_1?expire=1844352287&id=989353634364686336
FLV(標清)
https://vtmsgpzl.ezvizlife.com:9188/v3/openlive/E48203280_2_2.flv?expire=1844360287&id=989353635301326848
FLV(高清)
https://vtmsgpzl.ezvizlife.com:9188/v3/openlive/E48203280_2_1.flv?expire=1844360288&id=989353636119007232
"""

    cameras = parse_cctv_playback_info(text)

    assert len(cameras) == 1
    camera = cameras[0]
    assert camera["id"] == "cam-12"
    assert camera["name"] == "Cam12"
    assert camera["csmart_channel_number"] == 2
    assert camera["source_type"] == "csmart_player"
    assert camera["rtmp_url"].startswith("https://vtmsgpzl.ezvizlife.com:9188/")
    assert camera["playback_info"]["ezopen_sd"] == "ezopen://open.ezviz.com/E48203280/2.live"
    assert camera["playback_info"]["hls_sd"].endswith("id=989353631169667072")
    assert camera["playback_info"]["rtmp_sd"].startswith("rtmp://vtmsgpzl.ezvizlife.com:1935/")
    assert camera["playback_info"]["flv_sd"].endswith("id=989353635301326848")
    assert "Cam12" in camera["playback_info_raw"]


def test_parse_cctv_playback_info_normalizes_markdown_wrapped_urls():
    text = """
Cam1
RTMP(標清)
rtmp://[vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_6_2?expire=1&id=2](http://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_6_2?expire=1&id=2)
FLV(標清)
[https://vtmsgpzl.ezvizlife.com:9188/v3/openlive/E48203280_6_2.flv?expire=3&id=4](https://vtmsgpzl.ezvizlife.com:9188/v3/openlive/E48203280_6_2.flv?expire=3&id=4)
"""

    cameras = parse_cctv_playback_info(text)

    assert cameras[0]["playback_info"]["rtmp_sd"] == (
        "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_6_2?expire=1&id=2"
    )
    assert cameras[0]["playback_info"]["flv_sd"] == (
        "https://vtmsgpzl.ezvizlife.com:9188/v3/openlive/E48203280_6_2.flv?expire=3&id=4"
    )
