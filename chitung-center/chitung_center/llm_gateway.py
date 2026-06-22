from __future__ import annotations

from typing import Any

import httpx

from chitung_center.audit import audit_logger
from chitung_center.config import settings
from chitung_center.security import compact_context, sanitize_for_llm


def _augment_payload(payload: dict[str, Any], *, max_tokens: int) -> dict[str, Any]:
    payload["max_tokens"] = max_tokens
    model = (settings.llm_model or "").lower()
    base_url = (settings.llm_base_url or "").lower()
    if model.startswith("glm") or "bigmodel" in base_url:
        payload["thinking"] = {"type": "disabled"}
    return payload


class LlmGateway:
    async def complete_json(self, system_prompt: str, user_text: str) -> dict[str, Any]:
        sanitized = compact_context(sanitize_for_llm(user_text))
        audit_logger.write(
            "llm_call_requested",
            {
                "configured": settings.llm_configured,
                "model": settings.llm_model,
                "chars": len(sanitized),
            },
        )
        if not settings.llm_configured:
            return {
                "available": False,
                "reason": "LLM is not configured. Rule-based routing was used.",
            }

        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": sanitized},
            ],
            "response_format": {"type": "json_object"},
        }
        _augment_payload(payload, max_tokens=2048)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(settings.llm_base_url.rstrip("/"), headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        audit_logger.write("llm_call_completed", {"model": settings.llm_model})
        return data

    async def complete_document_json(
        self,
        system_prompt: str,
        user_text: str,
        *,
        max_chars: int = 12000,
    ) -> dict[str, Any]:
        trimmed = user_text if len(user_text) <= max_chars else user_text[: max_chars - 20] + "...[TRUNCATED]"
        audit_logger.write(
            "llm_document_call_requested",
            {
                "configured": settings.llm_configured,
                "model": settings.llm_model,
                "chars": len(trimmed),
            },
        )
        if not settings.llm_configured:
            return {"available": False, "reason": "LLM is not configured."}

        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": trimmed},
            ],
            "response_format": {"type": "json_object"},
        }
        _augment_payload(payload, max_tokens=8192)
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(settings.llm_base_url.rstrip("/"), headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        audit_logger.write("llm_document_call_completed", {"model": settings.llm_model})
        return data


llm_gateway = LlmGateway()
