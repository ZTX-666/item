from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .cards import build_alert_card
from .config import load_sources, load_topic_skills
from .fetcher import Fetcher
from .parsers import parse_document
from .rules import classify_item


def run_once(
    *,
    sources_path: Path,
    skills_dir: Path,
    enabled_only: bool = True,
    source_names: set[str] | None = None,
    max_sources: int | None = None,
    max_cards: int | None = None,
    ack_base_url: str | None = None,
) -> dict[str, Any]:
    sources = load_sources(sources_path)
    skills = load_topic_skills(skills_dir)
    if enabled_only:
        sources = [source for source in sources if source.enabled]
    if source_names:
        sources = [source for source in sources if source.name in source_names]
    if max_sources is not None:
        sources = sources[:max_sources]

    cards = []
    errors = []
    seen_card_keys: set[tuple[str, str, str]] = set()
    fetcher = Fetcher()
    try:
        for source in sources:
            try:
                documents = fetcher.fetch(source)
                for document in documents:
                    if document.status_code >= 400:
                        errors.append(
                            {
                                "source": source.name,
                                "error": f"HTTP {document.status_code}",
                                "url": document.final_url,
                            }
                        )
                        continue
                    for item in parse_document(document):
                        for classification in classify_item(item, skills):
                            card = build_alert_card(
                                item,
                                classification,
                                ack_base_url=ack_base_url,
                            )
                            key = (card.url, card.title, classification.matched_topic)
                            if key in seen_card_keys:
                                continue
                            seen_card_keys.add(key)
                            cards.append(asdict(card))
                            if max_cards is not None and len(cards) >= max_cards:
                                return _result(cards, errors)
            except Exception as exc:  # noqa: BLE001 - collect source-level crawler errors
                errors.append({"source": source.name, "error": str(exc)})
    finally:
        fetcher.close()

    return _result(cards, errors)


def _result(cards: list[dict[str, Any]], errors: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "card_count": len(cards),
        "error_count": len(errors),
        "cards": cards,
        "errors": errors,
    }
