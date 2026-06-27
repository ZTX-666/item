from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from chitung_center.config import settings


CATEGORY_IDS = ("weather", "official", "media")


def _briefing_skill_config_path() -> Path:
    return settings.chitung_skills_dir / "daily-risk-briefing" / "config.json"


def _category_for_source(source: dict[str, Any]) -> str:
    adapter = str(source.get("adapter") or "").lower()
    category = str(source.get("category") or "").lower()
    source_id = str(source.get("id") or "").lower()
    if adapter == "hko_weather" or "weather" in source_id or source_id.startswith("hko"):
        return "weather"
    if category in {"media", "media_whitelist", "cautious_media"} or source.get("type") in {"media", "media_list"}:
        return "media"
    return "official"


def load_source_catalog() -> dict[str, Any]:
    path = _briefing_skill_config_path()
    feeds: list[dict[str, Any]] = []
    defaults: dict[str, list[str]] = {key: [] for key in CATEGORY_IDS}

    if path.exists():
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            config = {}
        sources = config.get("sources") if isinstance(config.get("sources"), list) else []
        for source in sources:
            if not isinstance(source, dict) or source.get("enabled") is False:
                continue
            category = _category_for_source(source)
            urls = [str(item).strip() for item in (source.get("urls") or []) if str(item).strip()]
            if not urls:
                continue
            defaults[category].extend(urls)
            feeds.append(
                {
                    "id": str(source.get("id") or ""),
                    "name": str(source.get("name") or source.get("id") or "未命名来源"),
                    "category": category,
                    "adapter": str(source.get("adapter") or "html_index"),
                    "urls": urls,
                    "poll_interval_seconds": int(source.get("poll_interval_seconds") or 3600),
                    "reliability": str(source.get("reliability") or "unknown"),
                }
            )

    for category in CATEGORY_IDS:
        defaults[category] = list(dict.fromkeys(defaults[category]))

    return {
        "ok": True,
        "categories": [
            {"id": "weather", "label": "香港天文台 / 天气", "description": "天文台开放数据与天气预警接口"},
            {"id": "official", "label": "官方安全更新", "description": "政府、劳工处、屋宇署等官方公开页面"},
            {"id": "media", "label": "白名单媒体", "description": "已审核媒体站点列表页与 RSS"},
        ],
        "defaults": defaults,
        "feeds": feeds,
    }


def clean_url_list(urls: Any) -> list[str]:
    if not isinstance(urls, list):
        return []
    cleaned: list[str] = []
    for item in urls:
        text = str(item or "").strip()
        if not text:
            continue
        parsed = urlparse(text)
        if parsed.scheme not in {"http", "https"}:
            continue
        cleaned.append(text)
    return list(dict.fromkeys(cleaned))


def effective_category_urls(source_urls: dict[str, Any] | None = None) -> dict[str, list[str]]:
    catalog = load_source_catalog()
    defaults = catalog.get("defaults") if isinstance(catalog.get("defaults"), dict) else {}
    custom = source_urls if isinstance(source_urls, dict) else {}
    result: dict[str, list[str]] = {}
    for category in CATEGORY_IDS:
        user_list = clean_url_list(custom.get(category))
        if user_list:
            result[category] = user_list
        else:
            result[category] = clean_url_list(defaults.get(category))
    return result
