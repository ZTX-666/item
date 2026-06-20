from __future__ import annotations

from chitung_center.config import settings
from chitung_center.models import IntegrationStatus


def list_integrations() -> list[IntegrationStatus]:
    return [
        IntegrationStatus(
            name="agent_toolbox",
            display_name="AgentToolbox",
            enabled=True,
            category="tool_execution",
            notes="Local HTTP tool gateway for VLM, OCR, WhatsApp archive, documents, and SQLite.",
        ),
        IntegrationStatus(
            name="chitong_lingxun",
            display_name="赤瞳灵讯",
            enabled=settings.enable_chitong_lingxun_adapter,
            category="communication",
            notes="Reserved adapter for WhatsApp archive/search/send and group operations.",
        ),
        IntegrationStatus(
            name="docmate",
            display_name="闪闪文档",
            enabled=settings.enable_docmate_adapter,
            category="document",
            notes="Reserved adapter for document editing, template filling, and report generation.",
        ),
        IntegrationStatus(
            name="yaoyao_huidu",
            display_name="耀耀慧读",
            enabled=settings.enable_yaoyao_huidu_adapter,
            category="ocr",
            notes="Reserved adapter for OCR, table extraction, and document structure parsing.",
        ),
        IntegrationStatus(
            name="feishu",
            display_name="飞书",
            enabled=settings.enable_feishu_adapter,
            category="bot",
            notes="Reserved adapter for approval, notification, and human confirmation flows.",
        ),
        IntegrationStatus(
            name="zht",
            display_name="中海通",
            enabled=settings.enable_zht_adapter,
            category="enterprise_system",
            notes="Reserved adapter for enterprise robot and safety management system sync.",
        ),
        IntegrationStatus(
            name="openclaw",
            display_name="OpenClaw",
            enabled=settings.enable_openclaw_adapter,
            category="agent_reference",
            notes="Reserved optional adapter. Not required for the MVP agent base.",
        ),
    ]
