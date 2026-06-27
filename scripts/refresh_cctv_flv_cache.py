#!/usr/bin/env python3
"""Refresh EZVIZ FLV/RTMP URLs in the C-SMART channel cache using cached accessToken."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE = ROOT / "cctv-gateway" / "csmart-channel-list-latest.json"
APP_CONFIG = ROOT / "chitung-center" / "data" / "app_config.json"
EZVIZ_LIVE_ADDR = "https://open.ys7.com/api/lapp/v2/live/address/get"
RTMP_EXPIRE_SECONDS = 30 * 24 * 3600

# camera_id in app_config keyed by (channel, quality)
CAMERA_ID_BY_CHANNEL: dict[tuple[int, int], str] = {
    (6, 1): "cam-slope-03",
    (7, 2): "cam-slope-container-01",
    (3, 1): "cam-guard-03",
    (9, 1): "cam-construction-01",
    (11, 1): "cam-construction-02",
    (1, 1): "cam-guard-01",
    (4, 1): "cam-slope-top-intersection",
    (5, 1): "cam-slope-02",
    (8, 1): "cam-slope-04",
    (10, 1): "cam-construction-03",
    (2, 1): "cam-guard-02",
}


def parse_quality_from_flv(flv: str) -> int:
    match = re.search(r"_(\d+)_(\d+)\.flv", flv or "")
    if match:
        return int(match.group(2))
    return 1


def get_live_url(
    client: httpx.Client,
    access_token: str,
    device_serial: str,
    channel_no: int,
    quality: int,
    protocol: int,
) -> str:
    response = client.post(
        EZVIZ_LIVE_ADDR,
        data={
            "accessToken": access_token,
            "deviceSerial": device_serial,
            "channelNo": str(channel_no),
            "protocol": str(protocol),
            "quality": str(quality),
            "expireTime": str(RTMP_EXPIRE_SECONDS),
        },
        timeout=20,
    )
    payload = response.json()
    if payload.get("code") != "200":
        raise RuntimeError(
            f"channel {channel_no} protocol {protocol}: {payload.get('code')} {payload.get('msg')}"
        )
    url = str(payload.get("data", {}).get("url") or "").strip()
    if not url:
        raise RuntimeError(f"channel {channel_no} protocol {protocol}: empty url")
    return url


def verify_flv(client: httpx.Client, flv_url: str) -> bool:
    try:
        response = client.head(flv_url, timeout=15)
        return response.status_code < 400
    except Exception:
        return False


def refresh_cache(cache_path: Path) -> dict:
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    channels = cache.get("channels") or []
    if not channels:
        raise RuntimeError("channel cache is empty")

    access_token = str(channels[0].get("accessToken") or "").strip()
    if not access_token:
        raise RuntimeError("missing accessToken in channel cache")

    ok_flv = 0
    ok_rtmp: dict[str, str] = {}
    errors: list[str] = []

    with httpx.Client(trust_env=False, follow_redirects=True) as client:
        for channel in channels:
            device_serial = str(channel.get("deviceId") or "E48203280").strip()
            channel_no = int(channel.get("number") or 0)
            quality = int(channel.get("quality") or parse_quality_from_flv(channel.get("flv", "")))
            label = f"#{channel_no} {channel.get('cameraName') or channel.get('name') or ''}".strip()

            try:
                flv = get_live_url(client, access_token, device_serial, channel_no, quality, protocol=4)
                channel["flv"] = flv
                channel["accessToken"] = access_token
                if verify_flv(client, flv):
                    ok_flv += 1
                    print(f"  [OK] FLV {label}")
                else:
                    print(f"  [WARN] FLV refreshed but HEAD not OK {label}")
                    ok_flv += 1
            except Exception as exc:
                errors.append(f"FLV {label}: {exc}")
                print(f"  [FAIL] FLV {label}: {exc}")

            camera_id = CAMERA_ID_BY_CHANNEL.get((channel_no, quality))
            if camera_id:
                try:
                    rtmp = get_live_url(client, access_token, device_serial, channel_no, quality, protocol=3)
                    ok_rtmp[camera_id] = rtmp
                except Exception as exc:
                    errors.append(f"RTMP {label}: {exc}")

    cache["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    cache["source"] = "refresh_cctv_flv_cache.py"
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved cache: {cache_path}")

    if APP_CONFIG.exists() and ok_rtmp:
        config = json.loads(APP_CONFIG.read_text(encoding="utf-8"))
        updated = 0
        for camera in config.get("cameras", []):
            new_url = ok_rtmp.get(camera.get("id", ""))
            if new_url:
                camera["rtmp_url"] = new_url
                updated += 1
        APP_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Updated app_config RTMP for {updated} cameras: {APP_CONFIG}")

    return {
        "channels": len(channels),
        "flv_ok": ok_flv,
        "rtmp_ok": len(ok_rtmp),
        "errors": errors,
    }


def main() -> int:
    cache_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CACHE
    if not cache_path.exists():
        print(f"Cache not found: {cache_path}", file=sys.stderr)
        return 1

    print(f"Refreshing CCTV stream URLs from: {cache_path}")
    result = refresh_cache(cache_path)
    print(
        f"Done: {result['flv_ok']}/{result['channels']} FLV, "
        f"{result['rtmp_ok']} RTMP, {len(result['errors'])} errors"
    )
    return 0 if result["flv_ok"] == result["channels"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
