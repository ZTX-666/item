"""LLM-assisted enrichment and clustering for external info monitoring."""

from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from typing import Any

from chitung_center.config import settings
from chitung_center.llm_gateway import llm_gateway
from chitung_center.risk_card_store import persist_risk_cards
from chitung_center.toolbox_client import toolbox_client


ENRICH_SYSTEM_PROMPT = """你是香港建筑工地安全外部讯息分析助手。根据标题、来源、正文摘要，输出 JSON：
{
  "is_safety_relevant": true,
  "relevance_score": 0-100,
  "priority": "P0|P1|P2",
  "risk_level": "critical|high|medium|low",
  "summary_zh": "80字内中文摘要",
  "keywords": ["关键词"],
  "recommended_action": "给现场安全负责人的具体建议",
  "event_date": "YYYY-MM-DD 或 null",
  "discard": false
}
规则：
- P0：死亡、重伤、大面积停工、极端天气红色警告、重大工业意外
- P1：工伤、坠下、吊运事故、酷热/暴雨/台风影响施工、官方重要安全通告
- P2：一般安全提示、技术通告、预防性提醒
- 媒体来源需更严格：与工地/建造业/职安无关则 discard=true
- 只输出 JSON，不要 markdown"""


def _extract_llm_json(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("available") is False:
        raise ValueError(raw.get("reason") or "llm_unavailable")
    if "is_safety_relevant" in raw or "priority" in raw:
        return raw
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else {}
        content = message.get("content") if isinstance(message, dict) else ""
        if isinstance(content, str) and content.strip():
            return json.loads(content)
    raise ValueError("model did not return enrich JSON")


def _priority_to_risk(priority: str) -> str:
    if priority == "P0":
        return "critical"
    if priority == "P1":
        return "high"
    return "medium"


def _normalize_cluster_text(text: str) -> str:
    cleaned = re.sub(r"\s+", "", str(text or "").lower())
    return re.sub(r"[^\w\u4e00-\u9fff]", "", cleaned)[:80]


def _cluster_key(item: dict[str, Any]) -> str:
    title = _normalize_cluster_text(str(item.get("title") or ""))
    if not title:
        return hashlib.sha1(str(item.get("url") or "").encode()).hexdigest()[:12]
    return hashlib.sha1(title.encode()).hexdigest()[:12]


def _titles_similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.72


def cluster_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge near-duplicate titles into primary cards with cluster metadata."""
    groups: list[list[dict[str, Any]]] = []
    for item in items:
        norm = _normalize_cluster_text(str(item.get("title") or ""))
        matched = False
        for group in groups:
            anchor = _normalize_cluster_text(str(group[0].get("title") or ""))
            if _titles_similar(norm, anchor):
                group.append(item)
                matched = True
                break
        if not matched:
            groups.append([item])
    merged: list[dict[str, Any]] = []
    for group in groups:
        primary = dict(group[0])
        if len(group) > 1:
            cluster_id = _cluster_key(primary)
            sources = list(dict.fromkeys(str(x.get("source_name") or x.get("source") or "") for x in group if x.get("source_name") or x.get("source")))
            primary["cluster_id"] = cluster_id
            primary["cluster_count"] = len(group)
            primary["cluster_sources"] = sources
            alt_urls = [x.get("url") for x in group[1:] if x.get("url")]
            if alt_urls:
                primary["related_urls"] = alt_urls[:5]
        merged.append(primary)
    return merged


async def enrich_safety_updates(
    updates: dict[str, Any],
    *,
    keywords: list[str] | None = None,
    area: str = "香港项目",
    max_items: int = 25,
    media_strict: bool = True,
) -> dict[str, Any]:
    """Fetch article bodies, LLM-enrich, filter, and cluster safety update items."""
    if not isinstance(updates, dict):
        return {"ok": False, "source": "llm_enrich", "items": [], "errors": ["invalid_updates"]}
    if not settings.llm_configured:
        return {
            **updates,
            "source": updates.get("source") or "hk_safety_updates",
            "summary": {
                **(updates.get("summary") or {}),
                "llm_enrich_skipped": True,
                "llm_enrich_reason": "llm_not_configured",
            },
        }

    items = [dict(item) for item in (updates.get("items") or []) if isinstance(item, dict)]
    keywords = keywords or []
    enriched: list[dict[str, Any]] = []
    errors: list[str] = []
    skipped = 0

    for item in items[: max(1, min(int(max_items or 25), 40))]:
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "未命名讯息")
        source_name = str(item.get("source_name") or item.get("source") or "外部来源")
        source_type = str(item.get("source_type") or item.get("source_category") or "external")
        body = ""
        if url:
            try:
                page = await toolbox_client.call_tool(
                    "fetch_url_content",
                    {"url": url, "max_chars": 4500, "extract_mode": "readable"},
                )
                if page.get("ok"):
                    body = str(page.get("content") or "")[:4500]
                    if not title and page.get("title"):
                        title = str(page.get("title"))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{url}: fetch_failed:{exc}")

        user_payload = json.dumps(
            {
                "project_area": area,
                "watch_keywords": keywords[:20],
                "source_name": source_name,
                "source_type": source_type,
                "title": title,
                "url": url,
                "body_excerpt": body or title,
            },
            ensure_ascii=False,
        )
        try:
            raw = await llm_gateway.complete_json(ENRICH_SYSTEM_PROMPT, user_payload)
            parsed = _extract_llm_json(raw)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{title[:40]}: llm_failed:{exc}")
            enriched.append(item)
            continue

        if parsed.get("discard") and media_strict and source_type == "media":
            skipped += 1
            continue
        if not parsed.get("is_safety_relevant") and media_strict and source_type == "media":
            if int(parsed.get("relevance_score") or 0) < 55:
                skipped += 1
                continue

        priority = str(parsed.get("priority") or "P2").upper()
        if priority not in {"P0", "P1", "P2"}:
            priority = "P2"
        risk_level = str(parsed.get("risk_level") or _priority_to_risk(priority))
        summary_zh = str(parsed.get("summary_zh") or "").strip()
        llm_keywords = parsed.get("keywords") if isinstance(parsed.get("keywords"), list) else []
        merged_keywords = list(dict.fromkeys([*(item.get("matched_keywords") or []), *[str(k) for k in llm_keywords if str(k).strip()]]))[:12]

        item.update(
            {
                "llm_enriched": True,
                "short_summary": summary_zh or item.get("short_summary"),
                "summary": summary_zh or item.get("summary"),
                "priority": priority,
                "risk_level": risk_level,
                "recommended_action": str(parsed.get("recommended_action") or "").strip() or item.get("recommended_action"),
                "matched_keywords": merged_keywords,
                "relevance_score": int(parsed.get("relevance_score") or 0),
                "published_at": parsed.get("event_date") or item.get("published_at"),
            }
        )
        enriched.append(item)

    # Append non-LLM-processed tail items without dropping them
    if len(items) > max_items:
        enriched.extend(items[max_items:])

    clustered = cluster_items(enriched)
    summary = dict(updates.get("summary") or {})
    summary.update(
        {
            "llm_enriched": True,
            "llm_enriched_count": sum(1 for x in clustered if x.get("llm_enriched")),
            "llm_skipped_media": skipped,
            "cluster_count": len(clustered),
            "matched_item_count": len(clustered),
        }
    )
    return {
        **updates,
        "items": clustered,
        "summary": summary,
        "errors": list(updates.get("errors") or []) + errors,
    }


async def enrich_and_persist_cards(
    updates: dict[str, Any],
    *,
    keywords: list[str] | None = None,
    area: str = "香港项目",
    max_items: int = 25,
) -> dict[str, Any]:
    """Enrich updates and write risk cards for UI consumption."""
    enriched = await enrich_safety_updates(
        updates,
        keywords=keywords,
        area=area,
        max_items=max_items,
        media_strict=True,
    )
    cards = _items_to_cards(enriched.get("items") or [])
    if cards:
        persist_risk_cards(cards)
    enriched["cards"] = cards
    enriched["source"] = "llm_enrich"
    return enriched


def _items_to_cards(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for item in items:
        source_type = str(item.get("source_type") or item.get("source_category") or "media")
        category = "official" if source_type.startswith("official") else ("weather" if "weather" in source_type else "media")
        priority = str(item.get("priority") or "P2").upper()
        cards.append(
            {
                "card_id": hashlib.sha1(f"{item.get('url')}|{item.get('title')}".encode()).hexdigest()[:12],
                "source_category": category,
                "source_name": item.get("source_name") or item.get("source") or "外部来源",
                "source_url": item.get("url"),
                "title": item.get("title") or "未命名讯息",
                "summary": item.get("short_summary") or item.get("summary"),
                "priority": priority if priority in {"P0", "P1", "P2"} else "P2",
                "risk_level": item.get("risk_level") or _priority_to_risk(priority),
                "keywords": item.get("matched_keywords") or [],
                "event_date": item.get("published_at"),
                "recommended_action": item.get("recommended_action"),
                "is_confirmed": 1 if category == "official" else 0,
                "payload": item,
            }
        )
    return cards
