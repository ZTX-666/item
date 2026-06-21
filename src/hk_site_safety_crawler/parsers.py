from __future__ import annotations

import hashlib
import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import feedparser
from bs4 import BeautifulSoup

from .models import FetchedDocument, NormalizedItem


def parse_document(document: FetchedDocument) -> list[NormalizedItem]:
    parser = document.source.parser
    if parser == "hko_warnsum":
        return _parse_hko_warnsum(document)
    if parser == "hko_warning_info":
        return _parse_hko_warning_info(document)
    if parser == "rss_generic":
        return _parse_rss(document)
    if parser == "gov_press_api":
        return _parse_gov_press_api(document)
    return _parse_html_links(document)


def _parse_hko_warnsum(document: FetchedDocument) -> list[NormalizedItem]:
    data = json.loads(document.text)
    items = []
    for code, value in data.items():
        if not isinstance(value, dict):
            continue
        name = value.get("name") or code
        text = json.dumps(value, ensure_ascii=False)
        items.append(
            _item(
                document,
                title=f"{name}",
                url=document.final_url,
                published_at=_parse_datetime(value.get("issueTime") or value.get("updateTime")),
                content_text=text,
                item_type="weather",
                raw={"warning_code": code, **value},
            )
        )
    return items


def _parse_hko_warning_info(document: FetchedDocument) -> list[NormalizedItem]:
    data = json.loads(document.text)
    details = data.get("details") or []
    items = []
    for detail in details:
        if not isinstance(detail, dict):
            continue
        code = detail.get("warningStatementCode") or "weather_warning"
        contents = detail.get("contents") or []
        content_text = "\n".join(str(content) for content in contents)
        items.append(
            _item(
                document,
                title=str(code),
                url=document.final_url,
                published_at=_parse_datetime(detail.get("updateTime")),
                content_text=content_text,
                item_type="weather",
                raw=detail,
            )
        )
    return items


def _parse_rss(document: FetchedDocument) -> list[NormalizedItem]:
    feed = feedparser.parse(document.text)
    items = []
    for entry in feed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", document.final_url)
        summary = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(" ", strip=True)
        published = entry.get("published") or entry.get("updated")
        items.append(
            _item(
                document,
                title=title,
                url=link,
                published_at=_parse_datetime(published),
                content_text=summary or title,
                item_type="media_report" if document.source.category == "media" else "policy",
                raw=dict(entry),
            )
        )
    return items


def _parse_gov_press_api(document: FetchedDocument) -> list[NormalizedItem]:
    data = json.loads(document.text)
    results = data.get("results", []) if isinstance(data, dict) else []
    items = []
    for result in results:
        if not isinstance(result, dict):
            continue
        title = result.get("title") or result.get("headline") or ""
        url = result.get("url") or result.get("link") or document.final_url
        content_text = result.get("content") or result.get("summary") or title
        published = result.get("release-date") or result.get("date") or result.get("published_at")
        items.append(
            _item(
                document,
                title=title,
                url=url,
                published_at=_parse_datetime(published),
                content_text=content_text,
                item_type="policy",
                raw=result,
            )
        )
    return items


def _parse_html_links(document: FetchedDocument) -> list[NormalizedItem]:
    soup = BeautifulSoup(document.text, "lxml")
    items = []
    seen_urls: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        title = anchor.get_text(" ", strip=True)
        if len(title) < 4:
            continue
        url = urljoin(document.final_url, anchor["href"])
        if url in seen_urls:
            continue
        seen_urls.add(url)
        items.append(
            _item(
                document,
                title=title,
                url=url,
                published_at=None,
                content_text=title,
                item_type="media_report" if document.source.category == "media" else "policy",
                raw={"href": anchor["href"]},
            )
        )
    return items


def _item(
    document: FetchedDocument,
    *,
    title: str,
    url: str,
    published_at: datetime | None,
    content_text: str,
    item_type: str,
    raw: dict,
) -> NormalizedItem:
    clean_title = " ".join(title.split())
    clean_text = " ".join(content_text.split())
    content_hash = hashlib.sha256(f"{url}|{clean_title}|{clean_text}".encode("utf-8")).hexdigest()
    return NormalizedItem(
        source_name=document.source.name,
        source_display_name=document.source.display_name,
        source_url=document.source.url,
        source_category=document.source.category,
        trust_level=document.source.trust_level,
        title=clean_title,
        url=url,
        published_at=published_at,
        detected_at=document.fetched_at,
        content_text=clean_text,
        content_hash=content_hash,
        language="zh-HK",
        item_type=item_type,
        raw=raw,
    )


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(text).astimezone()
    except (TypeError, ValueError):
        return None
