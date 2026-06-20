from __future__ import annotations

import json
from typing import Any

from chitung_center.config import settings
from chitung_center.models import AppConfigRequest


CONFIG_PATH = settings.chitung_data_dir / "app_config.json"


DEFAULT_CONFIG: dict[str, Any] = {
    "project": {
        "name": "赤瞳示范项目",
        "default_area": "施工區域",
        "location": "Hong Kong",
    },
    "cameras": [
        {
            "id": "cam-slope-03",
            "name": "斜坡03",
            "area": "斜坡",
            "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_6_1?expire=1843920402&id=987542176923750400&c=122083786b&t=389924b692745975bc71a1fc3dd9b25619b81438807a275d73584937a14f1539&ev=100",
            "enabled": True,
        },
        {
            "id": "cam-slope-container-01",
            "name": "斜坡貨櫃01",
            "area": "斜坡",
            "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_7_2?expire=1843920403&id=987542182618390528&c=122083786b&t=70de41b3ed10dc4a6d4c5106b109453ae85e1e3dd8b56fc96d74aa7ef301a9b8&ev=100",
            "enabled": True,
        },
        {
            "id": "cam-guard-03",
            "name": "崗亭03",
            "area": "崗亭",
            "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_3_1?expire=1843920394&id=987542144455352320&c=122083786b&t=2f337046d679fc43da4d4137d04381b7c80eac650e88c045bbf8381feb80d86e&ev=100",
            "enabled": True,
        },
        {
            "id": "cam-construction-01",
            "name": "施工區域01",
            "area": "施工區域",
            "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_9_1?expire=1843920407&id=987542197595897856&c=122083786b&t=8a9e754865f7e8ab8b32a57afab11b5d23a50b80c394fefafa171e04b385cebe&ev=100",
            "enabled": True,
        },
        {
            "id": "cam-construction-02",
            "name": "施工區域02",
            "area": "施工區域",
            "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_11_1?expire=1843920410&id=987542211702964224&c=122083786b&t=4aa6c914caee546093774557b308f8d95702b4113c28021002c794895fcbe31c&ev=100",
            "enabled": True,
        },
        {
            "id": "cam-guard-01",
            "name": "崗亭01",
            "area": "崗亭",
            "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_1_1?expire=1843920388&id=987542118474366976&c=122083786b&t=f1d6f039a568290ebf83e7a14cd8dd9cc0095ae6df76ae5e0f5816c1bbafb73c&ev=100",
            "enabled": True,
        },
        {
            "id": "cam-slope-top-intersection",
            "name": "坡頂T字路口",
            "area": "坡頂",
            "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_4_1?expire=1843920398&id=987542157776801792&c=122083786b&t=51d412022c6cc42ef36705b390d3a6ec87fd997dad6610127352b8fdb2d349ca&ev=100",
            "enabled": True,
        },
        {
            "id": "cam-slope-02",
            "name": "斜坡02",
            "area": "斜坡",
            "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_5_1?expire=1843920399&id=987542164091019264&c=122083786b&t=7455a2d80f6f74df9ab142d39bc20d9e3628ff790dd425dd122f7808842324c7&ev=100",
            "enabled": True,
        },
        {
            "id": "cam-slope-04",
            "name": "斜坡04",
            "area": "斜坡",
            "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_8_1?expire=1843920405&id=987542190475743232&c=122083786b&t=f7b811a3c3986ec6752defc41658b0ffdf87a7cd12ac5777a21c3a05cc2b71a2&ev=100",
            "enabled": True,
        },
        {
            "id": "cam-construction-03",
            "name": "施工區域03",
            "area": "施工區域",
            "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_10_1?expire=1843920409&id=987542205265182720&c=122083786b&t=f855cc6ab6611705e989d4ca6c57cb912560c85657966a378f95f02e17149094&ev=100",
            "enabled": True,
        },
        {
            "id": "cam-guard-02",
            "name": "崗亭02",
            "area": "崗亭",
            "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_2_1?expire=1843920391&id=987542131204300800&c=122083786b&t=9e1647c78140a1a3ae10231bdcb773554c3bba988df2def58d7efc7bc0fb6442&ev=100",
            "enabled": True,
        },
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
