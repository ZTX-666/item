from __future__ import annotations

from .models import AlertCard, Classification, NormalizedItem


def build_alert_card(
    item: NormalizedItem,
    classification: Classification,
    *,
    ack_base_url: str | None = None,
) -> AlertCard:
    title = f"[{classification.severity}][{classification.category}] {item.title}"
    summary = _summary(item, classification)
    ack_url = None
    if ack_base_url:
        ack_url = f"{ack_base_url.rstrip('/')}/{item.content_hash}/ack"

    render_payload = {
        "schema_version": 1,
        "severity": classification.severity,
        "category": classification.category,
        "title": title,
        "summary": summary,
        "source": {
            "name": item.source_display_name,
            "type": item.trust_level,
            "url": item.source_url,
        },
        "times": {
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "detected_at": item.detected_at.isoformat(),
        },
        "matched_keywords": classification.matched_keywords,
        "classification_reason": classification.reason,
        "recommended_action": classification.recommended_actions,
        "links": {
            "original": item.url,
            "ack": ack_url,
        },
        "requires_human_review": classification.requires_human_review,
    }

    return AlertCard(
        severity=classification.severity,
        category=classification.category,
        title=title,
        summary=summary,
        source_name=item.source_display_name,
        source_type=item.trust_level,
        published_at=item.published_at.isoformat() if item.published_at else None,
        detected_at=item.detected_at.isoformat(),
        matched_keywords=classification.matched_keywords,
        recommended_action=classification.recommended_actions,
        url=item.url,
        ack_url=ack_url,
        render_payload=render_payload,
    )


def _summary(item: NormalizedItem, classification: Classification) -> str:
    text = item.content_text.strip() or item.title
    if len(text) > 220:
        text = text[:217].rstrip() + "..."
    keywords = "、".join(classification.matched_keywords[:8])
    if keywords:
        return f"{text} 命中关键词：{keywords}。"
    return text
