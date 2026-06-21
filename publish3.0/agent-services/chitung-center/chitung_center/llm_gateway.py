from __future__ import annotations

from typing import Any

import httpx

from chitung_center.audit import audit_logger
from chitung_center.config import settings
from chitung_center.security import compact_context, sanitize_for_llm


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
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(settings.llm_base_url.rstrip("/"), headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        audit_logger.write("llm_call_completed", {"model": settings.llm_model})
        return data


llm_gateway = LlmGateway()
