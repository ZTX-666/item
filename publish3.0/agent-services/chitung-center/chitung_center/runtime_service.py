from __future__ import annotations

from typing import Any

from chitung_center.config import settings
from chitung_center.settings_service import get_llm_settings_status
from chitung_center.toolbox_client import toolbox_client


REQUIRED_TOOLBOX_CHECKS = [
    "rtmp_snapshot",
    "vlm_detect",
    "generate_report",
    "safety_policy_templates",
    "safety_platform_database",
]

OPTIONAL_TOOLBOX_CHECKS = [
    "whatsapp_archive",
    "feishu_notify",
    "feishu_openapi_bot",
    "hko_weather_api",
    "hk_safety_update_sources",
]


async def build_runtime_status() -> dict[str, Any]:
    toolbox = await toolbox_client.health()
    checks = toolbox.get("tools", {}) if isinstance(toolbox.get("tools"), dict) else {}
    required = [_component_from_tool(name, checks.get(name, {})) for name in REQUIRED_TOOLBOX_CHECKS]
    optional = [_component_from_tool(name, checks.get(name, {})) for name in OPTIONAL_TOOLBOX_CHECKS]

    return {
        "center": {
            "ok": True,
            "service": "chitung-center",
            "url": f"http://{settings.host}:{settings.port}",
        },
        "llm": get_llm_settings_status(),
        "toolbox": {
            "ok": all(item["ok"] for item in required),
            "base_url": settings.agent_toolbox_base_url,
            "raw_ok": bool(toolbox.get("ok")),
            "required": required,
            "optional": optional,
        },
        "ready": all(item["ok"] for item in required),
    }


def _component_from_tool(name: str, value: Any) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    return {
        "name": name,
        "ok": bool(data.get("available")),
        "path": data.get("path"),
        "url": data.get("url"),
        "configured": data.get("configured"),
        "error": data.get("error"),
    }
