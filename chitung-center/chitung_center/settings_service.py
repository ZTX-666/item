from __future__ import annotations

from pathlib import Path

from chitung_center.config import ROOT, settings
from chitung_center.models import ConnectorSettingsRequest, LlmSettingsRequest


ENV_PATH = ROOT / ".env"
TOOLBOX_ENV_PATH = ROOT.parent / "agent-toolbox" / ".env"


def get_llm_settings_status() -> dict[str, object]:
    return {
        "configured": settings.llm_configured,
        "base_url": settings.llm_base_url,
        "model": settings.llm_model,
        "api_key_masked": _mask_secret(settings.llm_api_key),
    }


def save_llm_settings(request: LlmSettingsRequest) -> dict[str, object]:
    values = {
        "LLM_BASE_URL": request.base_url.strip(),
        "LLM_API_KEY": request.api_key.strip(),
        "LLM_MODEL": request.model.strip(),
    }
    _write_env_values(ENV_PATH, values)

    settings.llm_base_url = values["LLM_BASE_URL"]
    settings.llm_api_key = values["LLM_API_KEY"]
    settings.llm_model = values["LLM_MODEL"]

    return {
        "ok": settings.llm_configured,
        "message": "LLM settings saved locally.",
        "status": get_llm_settings_status(),
    }


async def test_llm_connection() -> dict[str, object]:
    if not settings.llm_configured:
        return {
            "ok": False,
            "message": "LLM is not configured. Please fill Base URL, API key, and model first.",
            "model": settings.llm_model,
        }
    try:
        from chitung_center.llm_gateway import llm_gateway

        result = await llm_gateway.complete_json(
            "Return JSON only. Use {\"ok\": true, \"message\": \"pong\"}.",
            "Connectivity test from Chitung Center.",
        )
        return {
            "ok": True,
            "message": "LLM Gateway responded successfully.",
            "model": settings.llm_model,
            "raw_keys": sorted(result.keys())[:10] if isinstance(result, dict) else [],
        }
    except Exception as exc:
        return {
            "ok": False,
            "message": str(exc),
            "model": settings.llm_model,
        }


def get_connector_settings_status() -> dict[str, object]:
    values = _read_env_values(ENV_PATH) | _read_env_values(TOOLBOX_ENV_PATH)
    whatsapp_url = values.get("WHATSAPP_ARCHIVE_BASE_URL", "http://127.0.0.1:8787")
    return {
        "whatsapp": {
            "configured": bool(whatsapp_url),
            "archive_base_url": whatsapp_url,
        },
        "feishu": {
            "configured": bool(values.get("FEISHU_APP_ID") and values.get("FEISHU_APP_SECRET")),
            "webhook_configured": bool(values.get("FEISHU_WEBHOOK_URL")),
            "app_id": values.get("FEISHU_APP_ID", ""),
            "app_secret_masked": _mask_secret(values.get("FEISHU_APP_SECRET", "")),
            "webhook_url": values.get("FEISHU_WEBHOOK_URL", ""),
            "webhook_secret_masked": _mask_secret(values.get("FEISHU_WEBHOOK_SECRET", "")),
            "verification_token_masked": _mask_secret(values.get("FEISHU_VERIFICATION_TOKEN", "")),
            "encrypt_key_masked": _mask_secret(values.get("FEISHU_ENCRYPT_KEY", "")),
            "api_base_url": values.get("FEISHU_API_BASE_URL", "https://open.feishu.cn"),
        },
        "requires_toolbox_restart": True,
    }


def save_connector_settings(request: ConnectorSettingsRequest) -> dict[str, object]:
    values = {
        "WHATSAPP_ARCHIVE_BASE_URL": request.whatsapp_archive_base_url.strip() or "http://127.0.0.1:8787",
        "FEISHU_WEBHOOK_URL": request.feishu_webhook_url.strip(),
        "FEISHU_WEBHOOK_SECRET": request.feishu_webhook_secret.strip(),
        "FEISHU_APP_ID": request.feishu_app_id.strip(),
        "FEISHU_APP_SECRET": request.feishu_app_secret.strip(),
        "FEISHU_VERIFICATION_TOKEN": request.feishu_verification_token.strip(),
        "FEISHU_ENCRYPT_KEY": request.feishu_encrypt_key.strip(),
        "FEISHU_API_BASE_URL": request.feishu_api_base_url.strip() or "https://open.feishu.cn",
    }
    _write_env_values(ENV_PATH, values)
    _write_env_values(TOOLBOX_ENV_PATH, values)
    return {
        "ok": True,
        "message": "Connector settings saved. Restart agent-toolbox to reload running integrations.",
        "status": get_connector_settings_status(),
    }


def _write_env_values(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    handled: set[str] = set()
    new_lines: list[str] = []

    for line in existing_lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in values:
            new_lines.append(f"{key}={values[key]}")
            handled.add(key)
        else:
            new_lines.append(line)

    for key, value in values.items():
        if key not in handled:
            new_lines.append(f"{key}={value}")

    path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")


def _read_env_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"
