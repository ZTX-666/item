from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import SourceConfig, TopicSkill


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML file must contain a mapping: {path}")
    return data


def load_sources(path: Path) -> list[SourceConfig]:
    data = load_yaml(path)
    sources = []
    for item in data.get("sources", []):
        known = {
            "name",
            "display_name",
            "category",
            "source_type",
            "trust_level",
            "url",
            "poll_interval_seconds",
            "priority",
            "parser",
            "enabled",
        }
        options = {key: value for key, value in item.items() if key not in known}
        sources.append(
            SourceConfig(
                name=item["name"],
                display_name=item.get("display_name", item["name"]),
                category=item.get("category", "unknown"),
                source_type=item.get("source_type", "html"),
                trust_level=item.get("trust_level", "unknown"),
                url=item["url"],
                poll_interval_seconds=int(item.get("poll_interval_seconds", 3600)),
                priority=item.get("priority", "medium"),
                parser=item.get("parser", "html_generic"),
                enabled=bool(item.get("enabled", True)),
                options=options,
            )
        )
    return sources


def load_topic_skill(path: Path) -> TopicSkill:
    data = load_yaml(path)
    return TopicSkill(
        name=data["name"],
        display_name=data.get("display_name", data["name"]),
        description=data.get("description", ""),
        enabled=bool(data.get("enabled", True)),
        source_scope=data.get("source_scope", {}),
        keywords=data.get("keywords", {}),
        severity_rules=data.get("severity_rules", {}),
        entities=data.get("entities", {}),
        recommended_actions=data.get("recommended_actions", []),
        output=data.get("output", {}),
    )


def load_topic_skills(directory: Path) -> list[TopicSkill]:
    skills = []
    for path in sorted(directory.glob("*.yml")):
        skill = load_topic_skill(path)
        if skill.enabled:
            skills.append(skill)
    return skills
