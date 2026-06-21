from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

Severity = Literal["P0", "P1", "P2"]


@dataclass(frozen=True)
class SourceConfig:
    name: str
    display_name: str
    category: str
    source_type: str
    trust_level: str
    url: str
    poll_interval_seconds: int
    priority: str
    parser: str
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TopicSkill:
    name: str
    display_name: str
    description: str
    enabled: bool
    source_scope: dict[str, Any]
    keywords: dict[str, list[str]]
    severity_rules: dict[str, Any]
    entities: dict[str, list[str]] = field(default_factory=dict)
    recommended_actions: list[str] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FetchedDocument:
    source: SourceConfig
    status_code: int
    content_type: str
    text: str
    fetched_at: datetime
    final_url: str


@dataclass(frozen=True)
class NormalizedItem:
    source_name: str
    source_display_name: str
    source_url: str
    source_category: str
    trust_level: str
    title: str
    url: str
    published_at: datetime | None
    detected_at: datetime
    content_text: str
    content_hash: str
    language: str
    item_type: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Classification:
    severity: Severity
    category: str
    matched_keywords: list[str]
    matched_topic: str
    reason: str
    requires_human_review: bool
    recommended_actions: list[str]


@dataclass(frozen=True)
class AlertCard:
    severity: Severity
    category: str
    title: str
    summary: str
    source_name: str
    source_type: str
    published_at: str | None
    detected_at: str
    matched_keywords: list[str]
    recommended_action: list[str]
    url: str
    ack_url: str | None
    render_payload: dict[str, Any]
