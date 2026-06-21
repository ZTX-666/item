from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.config import Settings
from chitung_center.models import LlmSettingsRequest
from chitung_center import settings_service


def test_glm_alias_key_configures_default_llm_gateway():
    settings = Settings(
        llm_base_url="",
        llm_api_key="",
        llm_model="",
        glm_api_key="glm-secret",
    )

    assert settings.llm_configured is True
    assert settings.llm_api_key == "glm-secret"
    assert settings.llm_base_url == "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    assert settings.llm_model == "glm-5.1"


def test_save_llm_settings_preserves_existing_key_when_payload_key_is_blank(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.setattr(settings_service, "ENV_PATH", env_path)
    monkeypatch.setattr(settings_service.settings, "llm_base_url", "https://old.example/chat/completions")
    monkeypatch.setattr(settings_service.settings, "llm_api_key", "existing-secret")
    monkeypatch.setattr(settings_service.settings, "llm_model", "glm-4-plus")

    result = settings_service.save_llm_settings(
        LlmSettingsRequest(
            base_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
            api_key="",
            model="glm-5.1",
        )
    )

    assert result["ok"] is True
    assert settings_service.settings.llm_api_key == "existing-secret"
    assert "LLM_API_KEY=existing-secret" in env_path.read_text()
