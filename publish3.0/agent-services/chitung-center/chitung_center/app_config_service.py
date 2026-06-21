from __future__ import annotations

import json
from typing import Any

from chitung_center.config import settings
from chitung_center.models import AppConfigRequest


CONFIG_PATH = settings.chitung_data_dir / "app_config.json"


DEFAULT_CONFIG: dict[str, Any] = {
    "project": {
        "name": "赤瞳示范项目",
        "default_area": "B2",
        "location": "Hong Kong",
    },
    "cameras": [
        {"id": "B2-Z1", "name": "B2 区 1 号摄像头", "area": "B2", "rtmp_url": None, "enabled": True},
        {"id": "A3-Z1", "name": "A3 区 1 号摄像头", "area": "A3", "rtmp_url": None, "enabled": True},
    ],
    "contractors": [
        {"id": "default", "name": "待确认分包商", "contact": "", "channel": "", "default_due_days": 3},
    ],
}


def get_app_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        save_app_config(AppConfigRequest.model_validate(DEFAULT_CONFIG))
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = DEFAULT_CONFIG
    return AppConfigRequest.model_validate(data).model_dump()


def save_app_config(request: AppConfigRequest) -> dict[str, Any]:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = request.model_dump()
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "config": data}


def get_default_camera() -> dict[str, Any] | None:
    config = get_app_config()
    for camera in config.get("cameras", []):
        if camera.get("enabled"):
            return camera
    return None


def get_default_contractor() -> dict[str, Any] | None:
    config = get_app_config()
    contractors = config.get("contractors", [])
    return contractors[0] if contractors else None
