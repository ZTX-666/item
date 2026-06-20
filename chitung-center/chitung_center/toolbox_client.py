from __future__ import annotations

from typing import Any

import httpx

from chitung_center.audit import audit_logger
from chitung_center.config import settings


class ToolboxClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        self.base_url = (base_url or settings.agent_toolbox_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.agent_toolbox_timeout_seconds

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                response.raise_for_status()
                return response.json()
        except Exception as exc:  # noqa: BLE001 - health should report failure, not crash.
            return {"ok": False, "error": str(exc), "base_url": self.base_url}

    async def call_tool(
        self,
        tool_name: str,
        payload: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        audit_payload = {"tool_name": tool_name, "payload_keys": sorted(payload.keys())}
        if context:
            audit_payload["context"] = context
        audit_logger.write(
            "tool_call_requested",
            audit_payload,
        )
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/tools/{tool_name}", json=payload)
            response.raise_for_status()
            result = response.json()
        complete_payload = {
            "tool_name": tool_name,
            "result_keys": sorted(result.keys()) if isinstance(result, dict) else [],
        }
        if context:
            complete_payload["context"] = context
        audit_logger.write(
            "tool_call_completed",
            complete_payload,
        )
        return result


toolbox_client = ToolboxClient()
