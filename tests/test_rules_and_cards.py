from __future__ import annotations

from datetime import datetime

from hk_site_safety_crawler.cards import build_alert_card
from hk_site_safety_crawler.models import NormalizedItem, TopicSkill
from hk_site_safety_crawler.rules import classify_item


def test_fatal_work_accident_generates_p0_card() -> None:
    skill = TopicSkill(
        name="site-safety",
        display_name="香港地盘安全总览",
        description="",
        enabled=True,
        source_scope={"include_sources": ["gov_press_rss"]},
        keywords={"include": ["致命工作意外", "地盘"], "exclude": []},
        severity_rules={
            "p0": {"any_keywords": ["致命工作意外"]},
            "p1": {"any_keywords": ["职安警示"]},
            "p2": {"default_for_matched_items": True},
        },
        recommended_actions=["通知项目经理和安全经理。"],
    )
    item = NormalizedItem(
        source_name="gov_press_rss",
        source_display_name="香港特区政府新闻公报 RSS",
        source_url="https://www.info.gov.hk/gia/rss/general_zh.xml",
        source_category="official",
        trust_level="official",
        title="劳工处高度关注一宗致命工作意外",
        url="https://www.info.gov.hk/example",
        published_at=None,
        detected_at=datetime(2026, 6, 21, 18, 0).astimezone(),
        content_text="劳工处高度关注一宗涉及地盘的致命工作意外。",
        content_hash="abc",
        language="zh-HK",
        item_type="policy",
    )

    classifications = classify_item(item, [skill])
    card = build_alert_card(item, classifications[0], ack_base_url="https://internal/alerts")

    assert classifications[0].severity == "P0"
    assert card.severity == "P0"
    assert "致命工作意外" in card.summary
    assert card.ack_url == "https://internal/alerts/abc/ack"
