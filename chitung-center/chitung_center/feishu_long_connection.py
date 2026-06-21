from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import lark_oapi as lark
from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTriggerResponse

from chitung_center.config import settings
from chitung_center.feishu_adapter_service import handle_feishu_event


logger = logging.getLogger(__name__)

FeishuPayloadHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class FeishuLongConnectionConfig:
    app_id: str
    app_secret: str
    verification_token: str = ""
    encrypt_key: str = ""
    api_base_url: str = "https://open.feishu.cn"
    log_level: str = "INFO"

    def missing_required_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.app_id:
            missing.append("FEISHU_APP_ID")
        if not self.app_secret:
            missing.append("FEISHU_APP_SECRET")
        return missing


def load_feishu_long_connection_config() -> FeishuLongConnectionConfig:
    return FeishuLongConnectionConfig(
        app_id=settings.feishu_app_id.strip(),
        app_secret=settings.feishu_app_secret.strip(),
        verification_token=settings.feishu_verification_token.strip(),
        encrypt_key=settings.feishu_encrypt_key.strip(),
        api_base_url=settings.feishu_api_base_url.strip() or "https://open.feishu.cn",
        log_level=settings.feishu_long_connection_log_level.strip() or "INFO",
    )


def sdk_event_to_payload(event: Any) -> dict[str, Any]:
    if isinstance(event, dict):
        return event

    marshaled = lark.JSON.marshal(event)
    payload = json.loads(marshaled or "{}")
    if not isinstance(payload, dict):
        raise TypeError(f"Unsupported Feishu SDK event payload: {type(payload)!r}")
    return payload


def submit_sdk_event(event: Any, handler: FeishuPayloadHandler = handle_feishu_event) -> None:
    submit_feishu_payload(sdk_event_to_payload(event), handler=handler)


def submit_feishu_payload(
    payload: dict[str, Any],
    handler: FeishuPayloadHandler = handle_feishu_event,
) -> None:
    coroutine = _handle_payload(payload, handler)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coroutine)
        return

    loop.create_task(coroutine)


async def _handle_payload(payload: dict[str, Any], handler: FeishuPayloadHandler) -> None:
    try:
        result = await handler(payload)
        logger.info("handled Feishu long-connection event stage=%s ok=%s", result.get("stage"), result.get("ok"))
    except Exception:
        logger.exception("failed to handle Feishu long-connection event")


def build_lark_event_dispatcher(
    *,
    encrypt_key: str,
    verification_token: str,
    handler: FeishuPayloadHandler = handle_feishu_event,
) -> lark.EventDispatcherHandler:
    def on_message(event: Any) -> None:
        submit_sdk_event(event, handler=handler)

    def on_card_action(event: Any) -> P2CardActionTriggerResponse:
        submit_sdk_event(event, handler=handler)
        return P2CardActionTriggerResponse()

    return (
        lark.EventDispatcherHandler.builder(encrypt_key, verification_token)
        .register_p2_im_message_receive_v1(on_message)
        .register_p2_card_action_trigger(on_card_action)
        .build()
    )


def build_lark_ws_client(
    config: FeishuLongConnectionConfig | None = None,
    handler: FeishuPayloadHandler = handle_feishu_event,
) -> lark.ws.Client:
    config = config or load_feishu_long_connection_config()
    missing = config.missing_required_fields()
    if missing:
        raise RuntimeError(f"Missing Feishu long-connection config: {', '.join(missing)}")

    dispatcher = build_lark_event_dispatcher(
        encrypt_key=config.encrypt_key,
        verification_token=config.verification_token,
        handler=handler,
    )
    return lark.ws.Client(
        config.app_id,
        config.app_secret,
        event_handler=dispatcher,
        domain=config.api_base_url.rstrip("/"),
        log_level=_lark_log_level(config.log_level),
        source="chitung-center",
    )


def start_feishu_long_connection(config: FeishuLongConnectionConfig | None = None) -> None:
    client = build_lark_ws_client(config=config)
    logger.info("starting Feishu long-connection client")
    client.start()


def _lark_log_level(value: str) -> lark.LogLevel:
    normalized = value.upper()
    return {
        "DEBUG": lark.LogLevel.DEBUG,
        "INFO": lark.LogLevel.INFO,
        "WARNING": lark.LogLevel.WARNING,
        "WARN": lark.LogLevel.WARNING,
        "ERROR": lark.LogLevel.ERROR,
    }.get(normalized, lark.LogLevel.INFO)
