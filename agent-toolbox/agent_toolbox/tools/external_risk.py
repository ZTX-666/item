from __future__ import annotations

import html
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

import requests
from pydantic import BaseModel, Field

from ..config import settings


HKO_WEATHER_API = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"
DEFAULT_HKO_DATA_TYPES = ["rhrread", "warnsum", "warningInfo", "swt", "flw", "fnd"]

WEATHER_RISK_BY_WARNING_CODE = {
    "WTCSGNL": "high",
    "WRAIN": "high",
    "WHOT": "medium",
    "WTS": "medium",
    "WL": "high",
    "WFIRE": "medium",
    "WFNTSA": "medium",
    "WMSGNL": "medium",
    "WCOLD": "medium",
    "WTMW": "critical",
}

SAFETY_KEYWORDS = [
    "工業意外",
    "工业意外",
    "工伤",
    "工傷",
    "職安",
    "职安",
    "安全警示",
    "地盘",
    "地盤",
    "工地",
    "建造業",
    "建造业",
    "高處墮下",
    "高处堕下",
    "墮下",
    "堕下",
    "吊運",
    "吊运",
    "起重",
    "天秤",
    "棚架",
    "竹棚",
    "密閉空間",
    "密闭空间",
    "電力",
    "电力",
    "酷熱",
    "酷热",
    "熱壓力",
    "热压力",
    "火警",
    "消防",
    "壓斃",
    "压毙",
    "夾斃",
    "夹毙",
    "昏迷",
    "死亡",
    "不治",
    "承建商",
]

STRONG_SAFETY_KEYWORDS = [
    "工業意外",
    "工业意外",
    "工伤",
    "工傷",
    "職安",
    "职安",
    "安全警示",
    "地盘",
    "地盤",
    "工地",
    "高處墮下",
    "高处堕下",
    "墮下",
    "堕下",
    "吊運",
    "吊运",
    "起重",
    "天秤",
    "棚架",
    "竹棚",
    "密閉空間",
    "密闭空间",
    "酷熱",
    "酷热",
    "熱壓力",
    "热压力",
    "壓斃",
    "压毙",
    "夾斃",
    "夹毙",
    "死亡",
    "不治",
    "暫時停工",
    "暂停施工",
    "停工通知書",
]

OFFICIAL_SOURCES: dict[str, dict[str, Any]] = {
    "gov_press_rss": {
        "display_name": "香港政府新闻公报",
        "base_url": "https://www.info.gov.hk",
        "adapter": "rss",
        "urls": [
            "https://www.info.gov.hk/gia/rss/general_zh.xml",
        ],
    },
    "labour_department": {
        "display_name": "香港劳工处",
        "base_url": "https://www.labour.gov.hk",
        "urls": [
            "https://www.labour.gov.hk/tc/news/work_safety_alert.htm",
            "https://www.labour.gov.hk/tc/news/work_safety_alert_2026.htm",
            "https://www.labour.gov.hk/tc/news/press.htm",
            "https://www.labour.gov.hk/tc/news/systemic_safety_alert.htm",
        ],
    },
    "housing_authority": {
        "display_name": "香港房屋署/房委会",
        "base_url": "https://www.housingauthority.gov.hk",
        "urls": [
            "https://www.housingauthority.gov.hk/tc/about-us/news-centre/press-releases/index.html",
            "https://www.housingauthority.gov.hk/tc/about-us/news-centre/speeches/index.html",
        ],
    },
    "development_bureau": {
        "display_name": "香港发展局",
        "base_url": "https://www.devb.gov.hk",
        "urls": [
            "https://www.devb.gov.hk/tc/publications_and_press_releases/press/index.html",
        ],
    },
    "buildings_department": {
        "display_name": "香港屋宇署",
        "base_url": "https://www.bd.gov.hk",
        "urls": [
            "https://www.bd.gov.hk/tc/resources/codes-and-references/practice-notes-and-circular-letters/index.html",
            "https://www.bd.gov.hk/tc/whats-new/press-releases/index.html",
        ],
    },
    "oshc": {
        "display_name": "香港职业安全健康局",
        "base_url": "https://www.oshc.org.hk",
        "urls": [
            "https://www.oshc.org.hk/tchi/news/index.html",
            "https://www.oshc.org.hk/tchi/news/press_release.html",
        ],
    },
    "cic": {
        "display_name": "香港建造业议会",
        "base_url": "https://www.cic.hk",
        "urls": [
            "https://www.cic.hk/zh-hk/safety/alerts-messages",
        ],
    },
}

MEDIA_SOURCES: dict[str, dict[str, Any]] = {
    "hk01": {
        "display_name": "香港01",
        "base_url": "https://www.hk01.com",
        "urls": [
            "https://www.hk01.com/tag/5985",
            "https://www.hk01.com/tag/28789",
        ],
    },
    "sing_tao": {
        "display_name": "星岛日报",
        "base_url": "https://std.stheadline.com",
        "urls": [
            "https://std.stheadline.com/realtime/%E5%8D%B3%E6%99%82-%E6%B8%AF%E8%81%9E",
            "https://std.stheadline.com/realtime/%E5%8D%B3%E6%99%82",
        ],
    },
    "ming_pao": {
        "display_name": "明报",
        "base_url": "https://news.mingpao.com",
        "urls": [
            "https://news.mingpao.com/ins/%e6%b8%af%e8%81%9e",
        ],
    },
    "oriental_daily": {
        "display_name": "东方日报",
        "base_url": "https://hk.on.cc",
        "urls": [
            "https://hk.on.cc/hk/news/index.html",
        ],
    },
    "hkcd": {
        "display_name": "香港商报",
        "base_url": "https://www.hkcd.com.hk",
        "urls": [
            "https://www.hkcd.com.hk/hkcdweb/index",
        ],
    },
}

ALL_SOURCES = {**OFFICIAL_SOURCES, **MEDIA_SOURCES}
DEFAULT_SAFETY_UPDATE_SOURCES = list(OFFICIAL_SOURCES.keys()) + ["hk01", "sing_tao"]


class HkoWeatherFetchRequest(BaseModel):
    lang: str = Field("tc", description="HKO language: en, tc, or sc.")
    data_types: list[str] = Field(default_factory=lambda: DEFAULT_HKO_DATA_TYPES.copy())
    timeout_seconds: float = 10.0


class ExternalRiskFetchRequest(BaseModel):
    sources: list[str] = Field(default_factory=lambda: DEFAULT_SAFETY_UPDATE_SOURCES.copy())
    keywords: list[str] = Field(default_factory=lambda: SAFETY_KEYWORDS.copy())
    limit_per_source: int = 10
    timeout_seconds: float = 10.0


class ExternalRiskResult(BaseModel):
    ok: bool
    source: str
    fetched_at: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class ExternalRiskPersistRequest(BaseModel):
    weather_result: dict[str, Any] | None = None
    safety_updates_result: dict[str, Any] | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    source_batch: str = "manual"


class ExternalRiskSummarizeRequest(BaseModel):
    weather_result: dict[str, Any] | None = None
    safety_updates_result: dict[str, Any] | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    include_recommended_actions: bool = True


class DailyRiskBriefingRequest(BaseModel):
    weather_result: dict[str, Any] | None = None
    safety_updates_result: dict[str, Any] | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    project_name: str | None = None
    audience: str = "site_safety_team"
    language: str = "zh-HK"


class ExternalRiskFormLinkRequest(BaseModel):
    weather_result: dict[str, Any] | None = None
    safety_updates_result: dict[str, Any] | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    limit_per_risk: int = Field(default=5, ge=1, le=20)


def fetch_hko_weather(req: HkoWeatherFetchRequest) -> ExternalRiskResult:
    lang = req.lang if req.lang in {"en", "tc", "sc"} else "tc"
    items: list[dict[str, Any]] = []
    errors: list[str] = []

    for data_type in req.data_types:
        if data_type not in DEFAULT_HKO_DATA_TYPES:
            errors.append(f"Unsupported HKO dataType skipped: {data_type}")
            continue
        try:
            response = requests.get(
                HKO_WEATHER_API,
                params={"dataType": data_type, "lang": lang},
                timeout=req.timeout_seconds,
            )
            response.raise_for_status()
            items.append({"data_type": data_type, "url": response.url, "data": response.json()})
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{data_type}: {exc}")

    return ExternalRiskResult(
        ok=bool(items) and not errors,
        source="hko",
        fetched_at=_now_iso(),
        items=items,
        summary=_summarize_weather(items),
        errors=errors,
    )


def fetch_hk_safety_updates(req: ExternalRiskFetchRequest) -> ExternalRiskResult:
    req = _apply_skill_config(req)
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_urls: set[str] = set()

    for source in req.sources:
        source_config = ALL_SOURCES.get(source)
        if not source_config:
            errors.append(f"Unsupported source skipped: {source}")
            continue
        source_items = _fetch_source_items(source, source_config, req, seen_urls, errors)
        items.extend(source_items[: req.limit_per_source])

    return ExternalRiskResult(
        ok=bool(items) and not errors,
        source="hk_safety_updates",
        fetched_at=_now_iso(),
        items=items,
        summary={
            "official_sources": [source for source in req.sources if source in OFFICIAL_SOURCES],
            "media_sources": [source for source in req.sources if source in MEDIA_SOURCES],
            "matched_item_count": len(items),
            "highest_risk_level": _highest_risk([item["risk_level"] for item in items]),
        },
        errors=errors,
    )


def fetch_hk_industrial_news(req: ExternalRiskFetchRequest) -> ExternalRiskResult:
    media_req = req.model_copy(update={"sources": [source for source in req.sources if source in MEDIA_SOURCES] or ["hk01", "sing_tao"]})
    result = fetch_hk_safety_updates(media_req)
    result.source = "hk_industrial_news"
    return result


def persist_external_risk_items(req: ExternalRiskPersistRequest) -> ExternalRiskResult:
    db_path = _ensure_external_risk_schema()
    items = _collect_external_items(req.weather_result, req.safety_updates_result, req.items)
    inserted = 0
    updated = 0
    now = _now_iso()

    with _connect() as conn:
        for item in items:
            item_key = _item_key(item)
            cursor = conn.execute("SELECT id FROM external_risk_items WHERE item_key = ?", (item_key,))
            exists = cursor.fetchone() is not None
            conn.execute(
                """
                INSERT INTO external_risk_items (
                    item_key, source, source_name, source_type, title, url, risk_level,
                    matched_keywords_json, payload_json, first_seen_at, last_seen_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_key) DO UPDATE SET
                    risk_level = excluded.risk_level,
                    matched_keywords_json = excluded.matched_keywords_json,
                    payload_json = excluded.payload_json,
                    last_seen_at = excluded.last_seen_at,
                    updated_at = excluded.updated_at
                """,
                (
                    item_key,
                    item.get("source", req.source_batch),
                    item.get("source_name", item.get("source", req.source_batch)),
                    item.get("source_type", "external"),
                    item.get("title", ""),
                    item.get("url", ""),
                    item.get("risk_level", "medium"),
                    json.dumps(item.get("matched_keywords", []), ensure_ascii=False),
                    json.dumps(item, ensure_ascii=False, sort_keys=True),
                    now,
                    now,
                    now,
                    now,
                ),
            )
            inserted += 0 if exists else 1
            updated += 1 if exists else 0

    return ExternalRiskResult(
        ok=True,
        source="persist_external_risk_items",
        fetched_at=now,
        items=[{"database_path": str(db_path), "inserted": inserted, "updated": updated}],
        summary={"item_count": len(items), "inserted": inserted, "updated": updated},
    )


def summarize_external_risks(req: ExternalRiskSummarizeRequest) -> ExternalRiskResult:
    items = _collect_external_items(req.weather_result, req.safety_updates_result, req.items)
    grouped: dict[str, list[dict[str, Any]]] = {"critical": [], "high": [], "medium": [], "low": []}
    for item in items:
        level = item.get("risk_level", "medium")
        grouped.setdefault(level, []).append(item)

    actions = _recommended_actions(items) if req.include_recommended_actions else []
    summary = {
        "total_items": len(items),
        "highest_risk_level": _highest_risk([item.get("risk_level", "low") for item in items]),
        "risk_counts": {level: len(grouped.get(level, [])) for level in ["critical", "high", "medium", "low"]},
        "recommended_actions": actions,
    }

    return ExternalRiskResult(
        ok=True,
        source="summarize_external_risks",
        fetched_at=_now_iso(),
        items=[
            {
                "risk_level": level,
                "items": grouped.get(level, []),
            }
            for level in ["critical", "high", "medium", "low"]
            if grouped.get(level)
        ],
        summary=summary,
    )


def draft_daily_risk_briefing(req: DailyRiskBriefingRequest) -> ExternalRiskResult:
    summary_result = summarize_external_risks(
        ExternalRiskSummarizeRequest(
            weather_result=req.weather_result,
            safety_updates_result=req.safety_updates_result,
            items=req.items,
            include_recommended_actions=True,
        )
    )
    summary = summary_result.summary
    items = _collect_external_items(req.weather_result, req.safety_updates_result, req.items)
    title_project = f" - {req.project_name}" if req.project_name else ""
    lines = [
        f"# 晴晴外部风险简报{title_project}",
        "",
        f"- 生成时间：{_now_iso()}",
        f"- 最高风险等级：{summary.get('highest_risk_level', 'low')}",
        f"- 外部风险条目：{summary.get('total_items', 0)}",
        "",
        "## 重点风险",
    ]
    for item in items[:10]:
        lines.append(
            f"- [{item.get('risk_level', 'medium')}] {item.get('title', '未命名风险')} "
            f"（来源：{item.get('source_name', item.get('source', 'unknown'))}）"
        )
    if not items:
        lines.append("- 暂未发现匹配白名单来源和施工安全关键词的外部风险。")

    lines.extend(["", "## 建议动作"])
    actions = summary.get("recommended_actions") or ["维持常规巡查，继续关注天气和官方安全提示。"]
    lines.extend(f"- {action}" for action in actions)

    return ExternalRiskResult(
        ok=True,
        source="draft_daily_risk_briefing",
        fetched_at=_now_iso(),
        items=[{"format": "markdown", "text": "\n".join(lines), "audience": req.audience, "language": req.language}],
        summary=summary,
    )


def link_external_risk_to_forms(req: ExternalRiskFormLinkRequest) -> ExternalRiskResult:
    from .forms import FormTemplateSearchRequest, search_form_templates

    items = _collect_external_items(req.weather_result, req.safety_updates_result, req.items)
    linked: list[dict[str, Any]] = []
    for item in items:
        keywords = _form_keywords_for_external_item(item)
        suggestions: list[dict[str, Any]] = []
        for keyword in keywords:
            result = search_form_templates(FormTemplateSearchRequest(query=keyword, limit=req.limit_per_risk))
            suggestions.extend(result.data.get("items", []))
        linked.append(
            {
                "risk_item": item,
                "form_keywords": keywords,
                "suggested_forms": _dedupe_forms(suggestions)[: req.limit_per_risk],
                "requires_human_confirmation": True,
            }
        )
    return ExternalRiskResult(
        ok=True,
        source="link_external_risk_to_forms",
        fetched_at=_now_iso(),
        items=linked,
        summary={"risk_item_count": len(items), "linked_count": len(linked)},
    )


def _fetch_source_items(
    source: str,
    source_config: dict[str, Any],
    req: ExternalRiskFetchRequest,
    seen_urls: set[str],
    errors: list[str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    headers = {
        "User-Agent": "ChitungSafetyPlatform/0.1 (+local safety risk monitor)",
        "Accept-Language": "zh-HK,zh-TW;q=0.9,zh;q=0.8,en;q=0.5",
    }
    for page_url in source_config["urls"]:
        try:
            response = requests.get(page_url, timeout=req.timeout_seconds, headers=headers)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            if source_config.get("adapter") == "rss" or page_url.lower().endswith((".xml", ".rss")):
                items.extend(_extract_rss_items(response.text, source, source_config, req, seen_urls))
                continue
            for title, url in _extract_links(response.text, page_url, source_config["base_url"]):
                if url in seen_urls:
                    continue
                matched = _matched_keywords(f"{title} {url}", req.keywords)
                if not matched or not _is_safety_relevant(title, matched):
                    continue
                seen_urls.add(url)
                items.append(
                    {
                        "source": source,
                        "source_name": source_config["display_name"],
                        "source_type": "official" if source in OFFICIAL_SOURCES else "media",
                        "title": title,
                        "url": url,
                        "matched_keywords": matched,
                        "risk_level": _classify_text_risk(title, matched),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{source}:{page_url}: {exc}")
    return items


def _extract_rss_items(
    text: str,
    source: str,
    source_config: dict[str, Any],
    req: ExternalRiskFetchRequest,
    seen_urls: set[str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    root = ElementTree.fromstring(text.encode("utf-8"))
    for item in root.findall(".//item"):
        title = _xml_text(item, "title")
        url = _xml_text(item, "link")
        description = _xml_text(item, "description")
        published_at = _xml_text(item, "pubDate")
        if not title or not url or url in seen_urls:
            continue
        haystack = f"{title} {description} {url}"
        matched = _matched_keywords(haystack, req.keywords)
        if not matched or not _is_safety_relevant(haystack, matched):
            continue
        seen_urls.add(url)
        items.append(
            {
                "source": source,
                "source_name": source_config["display_name"],
                "source_type": "official_rss",
                "title": title,
                "url": url,
                "published_at": published_at,
                "short_summary": re.sub(r"\s+", " ", description).strip()[:220],
                "matched_keywords": matched,
                "risk_level": _classify_text_risk(haystack, matched),
            }
        )
    return items


def _xml_text(item: ElementTree.Element, tag_name: str) -> str:
    child = item.find(tag_name)
    return html.unescape((child.text or "").strip()) if child is not None else ""


def _apply_skill_config(req: ExternalRiskFetchRequest) -> ExternalRiskFetchRequest:
    config = _read_skill_config()
    if not config:
        return req

    updates: dict[str, Any] = {}
    configured_sources = _configured_sources(config)
    if configured_sources and req.sources == DEFAULT_SAFETY_UPDATE_SOURCES:
        updates["sources"] = configured_sources

    configured_keywords = _configured_keywords(config)
    if configured_keywords and req.keywords == SAFETY_KEYWORDS:
        updates["keywords"] = configured_keywords

    return req.model_copy(update=updates) if updates else req


def _skill_config_path() -> Path:
    override = os.getenv("DAILY_RISK_SKILL_CONFIG_PATH")
    if override:
        return Path(override)
    return settings.root.parent / "chitung-center" / "skills" / "daily-risk-briefing" / "config.json"


def _read_skill_config() -> dict[str, Any]:
    path = _skill_config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _configured_sources(config: dict[str, Any]) -> list[str]:
    sources = config.get("sources")
    if not isinstance(sources, list):
        return []
    configured: list[str] = []
    for source in sources:
        if not isinstance(source, dict) or source.get("enabled") is False:
            continue
        source_id = str(source.get("id") or "").strip()
        if source_id in ALL_SOURCES:
            configured.append(source_id)
    return list(dict.fromkeys(configured))


def _configured_keywords(config: dict[str, Any]) -> list[str]:
    groups = config.get("keyword_groups")
    if not isinstance(groups, list):
        return []
    keywords: list[str] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        include = group.get("include")
        if isinstance(include, list):
            keywords.extend(str(item).strip() for item in include if str(item).strip())
    return list(dict.fromkeys(keywords))


def _collect_external_items(
    weather_result: dict[str, Any] | None,
    safety_updates_result: dict[str, Any] | None,
    direct_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if weather_result:
        weather_summary = weather_result.get("summary") or {}
        for basis in weather_summary.get("risk_basis", []):
            code = basis.get("warning_code", "weather_warning")
            items.append(
                {
                    "source": "hko",
                    "source_name": "香港天文台",
                    "source_type": "official_weather",
                    "title": f"天文台天气警告：{code}",
                    "url": HKO_WEATHER_API,
                    "risk_level": basis.get("risk_level", "medium"),
                    "matched_keywords": [code],
                    "payload": basis,
                }
            )
        for tip in weather_summary.get("special_tips", []):
            items.append(
                {
                    "source": "hko",
                    "source_name": "香港天文台",
                    "source_type": "official_weather",
                    "title": f"特别天气提示：{tip}",
                    "url": HKO_WEATHER_API,
                    "risk_level": "medium",
                    "matched_keywords": ["specialWxTips"],
                }
            )
    if safety_updates_result:
        items.extend(safety_updates_result.get("items") or [])
    items.extend(direct_items)
    return items


def _recommended_actions(items: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    text = " ".join(f"{item.get('title', '')} {' '.join(item.get('matched_keywords', []))}" for item in items)
    if "WRAIN" in text or "暴雨" in text:
        actions.append("检查排水、临时用电防水、斜坡/基坑积水，并评估室外高风险工序是否暂停。")
    if "WHOT" in text or "酷熱" in text or "酷热" in text:
        actions.append("执行防暑降温安排，检查饮水、遮阴、休息节奏和热应激记录。")
    if "WTCSGNL" in text or "台风" in text or "颱風" in text:
        actions.append("检查吊机、棚架、临时设施、围挡和高空物料防风加固。")
    if any(term in text for term in ["吊運", "吊运", "天秤", "起重"]):
        actions.append("加强吊运作业检查，包括吊具、信号员、禁区围封、起重机械证书和吊运计划。")
    if any(term in text for term in ["高處墮下", "高处堕下", "棚架", "竹棚", "墮下", "堕下"]):
        actions.append("重点检查临边洞口、棚架、工作平台、梯具和防坠落措施。")
    if any(term in text for term in ["死亡", "不治", "斃", "毙", "工業意外", "工业意外"]):
        actions.append("在班前会通报相关事故教训，并安排同类工序专项复查。")
    return actions or ["维持常规巡查，继续关注天气和官方安全提示。"]


def _form_keywords_for_external_item(item: dict[str, Any]) -> list[str]:
    text = f"{item.get('title', '')} {' '.join(item.get('matched_keywords', []))} {item.get('source', '')}"
    keywords: list[str] = []
    if "WHOT" in text or "酷熱" in text or "酷热" in text:
        keywords.extend(["酷熱", "暑熱", "热"])
    if "WRAIN" in text or "暴雨" in text or "水浸" in text:
        keywords.extend(["暴雨", "排水", "临时用电"])
    if "WTCSGNL" in text or "台风" in text or "颱風" in text:
        keywords.extend(["台风", "棚架", "吊"])
    if any(term in text for term in ["吊運", "吊运", "起重", "天秤"]):
        keywords.extend(["吊運", "起重", "天秤"])
    if any(term in text for term in ["棚架", "竹棚", "高處墮下", "高处堕下", "墮下", "堕下"]):
        keywords.extend(["棚架", "高處", "临边"])
    if any(term in text for term in ["電", "电", "配電", "触电", "觸電"]):
        keywords.extend(["電", "配電"])
    if any(term in text for term in ["密閉", "密闭"]):
        keywords.extend(["密閉"])
    if not keywords:
        keywords.append("安全")
    return list(dict.fromkeys(keywords))


def _dedupe_forms(forms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for form in forms:
        template_id = str(form.get("id"))
        if template_id in seen:
            continue
        seen.add(template_id)
        out.append(form)
    return out


def _ensure_external_risk_schema() -> Path:
    db_path = _db_path()
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS external_risk_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_key TEXT UNIQUE NOT NULL,
                source TEXT,
                source_name TEXT,
                source_type TEXT,
                title TEXT,
                url TEXT,
                risk_level TEXT,
                matched_keywords_json TEXT NOT NULL DEFAULT '[]',
                payload_json TEXT NOT NULL DEFAULT '{}',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_external_risk_items_source ON external_risk_items(source, source_type);
            CREATE INDEX IF NOT EXISTS idx_external_risk_items_risk ON external_risk_items(risk_level);
            CREATE INDEX IF NOT EXISTS idx_external_risk_items_last_seen ON external_risk_items(last_seen_at);
            """
        )
    return db_path


def _db_path() -> Path:
    path = settings.safety_database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _item_key(item: dict[str, Any]) -> str:
    text = "|".join(
        [
            str(item.get("source", "")),
            str(item.get("url", "")),
            str(item.get("title", "")),
        ]
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _extract_links(text: str, page_url: str, base_url: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for match in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", text, flags=re.I | re.S):
        href = html.unescape(match.group(1)).strip()
        raw_title = re.sub(r"<[^>]+>", " ", match.group(2))
        title = " ".join(html.unescape(raw_title).split())
        if len(title) < 4:
            continue
        url = urljoin(page_url, href)
        if not url.startswith(base_url):
            continue
        links.append((title, url))
    return links


def _summarize_weather(items: list[dict[str, Any]]) -> dict[str, Any]:
    active_warning_codes: list[str] = []
    special_tips: list[str] = []
    for item in items:
        data_type = item.get("data_type")
        data = item.get("data") or {}
        if data_type == "warnsum":
            active_warning_codes.extend(sorted(data.keys()))
        if data_type in {"rhrread", "swt"}:
            tips = data.get("specialWxTips") or data.get("swt") or []
            if isinstance(tips, list):
                special_tips.extend(str(tip) for tip in tips)
    levels = [WEATHER_RISK_BY_WARNING_CODE.get(code, "low") for code in active_warning_codes]
    return {
        "active_warning_codes": active_warning_codes,
        "special_tips": special_tips,
        "highest_risk_level": _highest_risk(levels),
        "risk_basis": [
            {"warning_code": code, "risk_level": WEATHER_RISK_BY_WARNING_CODE.get(code, "low")}
            for code in active_warning_codes
        ],
    }


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    lowered = text.lower()
    return [keyword for keyword in keywords if keyword.lower() in lowered]


def _is_safety_relevant(title: str, matched: list[str]) -> bool:
    text = f"{title} {' '.join(matched)}"
    return any(keyword in text for keyword in STRONG_SAFETY_KEYWORDS)


def _classify_text_risk(title: str, matched: list[str]) -> str:
    text = f"{title} {' '.join(matched)}"
    if any(term in text for term in ["死亡", "不治", "斃", "毙", "奪命", "夺命"]):
        return "critical"
    if any(term in text for term in ["高處墮下", "高处堕下", "吊運", "吊运", "天秤", "壓斃", "压毙", "昏迷"]):
        return "high"
    return "medium"


def _highest_risk(levels: list[str]) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    if not levels:
        return "low"
    return max(levels, key=lambda level: order.get(level, 0))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
