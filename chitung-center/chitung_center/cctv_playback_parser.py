from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


LABEL_MAP = {
    "EZOPEN(標清)": "ezopen_sd",
    "EZOPEN(标清)": "ezopen_sd",
    "EZOPEN(高清)": "ezopen_hd",
    "HLS(標清)": "hls_sd",
    "HLS(标清)": "hls_sd",
    "HLS(高清)": "hls_hd",
    "RTMP(標清)": "rtmp_sd",
    "RTMP(标清)": "rtmp_sd",
    "RTMP(高清)": "rtmp_hd",
    "FLV(標清)": "flv_sd",
    "FLV(标清)": "flv_sd",
    "FLV(高清)": "flv_hd",
}


def _normalize_url(raw: str) -> str:
    text = "".join(str(raw or "").strip().split())
    text = text.replace("？", "?").rstrip("。；;，,")
    if not text:
        return ""

    rtmp_wrapped = re.match(r"^rtmp://\[([^\]]+)]\((?:https?://)?[^)]+\)$", text)
    if rtmp_wrapped:
        return f"rtmp://{rtmp_wrapped.group(1)}"

    markdown = re.match(r"^\[([^]]+)]\(([^)]+)\)$", text)
    if markdown:
        label = markdown.group(1)
        href = markdown.group(2)
        return label if "://" in label else href

    return text


def _channel_number_from_playback(playback_info: dict[str, str]) -> int | None:
    ezopen = playback_info.get("ezopen_sd") or playback_info.get("ezopen_hd") or ""
    match = re.search(r"/(\d+)(?:\.hd)?\.live$", ezopen)
    if match:
        return int(match.group(1))

    for key in ("flv_sd", "hls_sd", "rtmp_sd", "flv_hd", "hls_hd", "rtmp_hd"):
        url = playback_info.get(key) or ""
        path = urlparse(url).path
        match = re.search(r"_(\d+)_[12](?:\.[a-z0-9]+)?$", path)
        if match:
            return int(match.group(1))
    return None


def _preferred_stream_url(playback_info: dict[str, str]) -> str:
    for key in ("flv_sd", "hls_sd", "rtmp_sd", "flv_hd", "hls_hd", "rtmp_hd"):
        url = playback_info.get(key)
        if url:
            return url
    return ""


def _parse_block(cam_number: int, block: str) -> dict[str, Any] | None:
    lines = [line.strip() for line in block.splitlines()]
    playback_info: dict[str, str] = {}
    current_key = ""
    current_value: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_value
        if current_key:
            value = _normalize_url("".join(current_value))
            if value:
                playback_info[current_key] = value
        current_key = ""
        current_value = []

    for line in lines:
        if not line or line == "播放信息":
            continue
        label = next((item for item in LABEL_MAP if line.upper() == item.upper()), "")
        if label:
            flush()
            current_key = LABEL_MAP[label]
            continue
        if current_key:
            current_value.append(line)
    flush()

    if not playback_info:
        return None

    channel_number = _channel_number_from_playback(playback_info)
    raw = f"Cam{cam_number}\n{block.strip()}".strip()
    return {
        "id": f"cam-{cam_number}",
        "name": f"Cam{cam_number}",
        "area": "施工區域",
        "source_type": "csmart_player",
        "rtmp_url": _preferred_stream_url(playback_info),
        "snapshot_url": "",
        "csmart_channel_number": channel_number,
        "csmart_channel_id": "",
        "player_screenshot_url": "",
        "playback_info": playback_info,
        "playback_info_raw": raw,
        "enabled": True,
    }


def parse_cctv_playback_info(text: str) -> list[dict[str, Any]]:
    """Parse C-SMART playback info copied from the backend into camera config rows."""
    matches = list(re.finditer(r"(?im)^Cam\s*(\d+)\s*$", str(text or "")))
    cameras: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        cam_number = int(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        camera = _parse_block(cam_number, text[start:end])
        if camera:
            cameras.append(camera)
    return cameras
