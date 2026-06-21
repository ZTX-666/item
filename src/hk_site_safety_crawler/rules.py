from __future__ import annotations

from .models import Classification, NormalizedItem, TopicSkill


def classify_item(item: NormalizedItem, skills: list[TopicSkill]) -> list[Classification]:
    classifications = []
    for skill in skills:
        if not _source_allowed(item, skill):
            continue
        text = f"{item.title}\n{item.content_text}"
        if _has_any(text, skill.keywords.get("exclude", [])):
            continue

        matched_keywords = _matched_keywords(text, skill.keywords.get("include", []))
        if not matched_keywords:
            continue

        severity, reason = _resolve_severity(text, item, skill)
        classifications.append(
            Classification(
                severity=severity,
                category=_category_for(item, skill),
                matched_keywords=matched_keywords,
                matched_topic=skill.name,
                reason=reason,
                requires_human_review=severity == "P0" or item.trust_level == "media_lead",
                recommended_actions=skill.recommended_actions,
            )
        )
    return classifications


def _source_allowed(item: NormalizedItem, skill: TopicSkill) -> bool:
    scope = skill.source_scope or {}
    include_sources = set(scope.get("include_sources") or [])
    include_categories = set(scope.get("include_categories") or [])
    if include_sources and item.source_name not in include_sources:
        return False
    if include_categories and item.source_category not in include_categories:
        return False
    return True


def _resolve_severity(text: str, item: NormalizedItem, skill: TopicSkill) -> tuple[str, str]:
    rules = skill.severity_rules or {}
    p0 = rules.get("p0", {})
    p1 = rules.get("p1", {})

    keyword = _first_match(text, p0.get("any_keywords", []))
    if keyword:
        return "P0", f"Matched P0 keyword: {keyword}"

    combo = _first_combined_match(text, p0.get("combined_keywords", []))
    if combo:
        return "P0", f"Matched P0 keyword combination: {', '.join(combo)}"

    keyword = _first_match(text, p1.get("any_keywords", []))
    if keyword:
        return "P1", f"Matched P1 keyword: {keyword}"

    combo = _first_combined_match(text, p1.get("combined_keywords", []))
    if combo:
        return "P1", f"Matched P1 keyword combination: {', '.join(combo)}"

    if item.trust_level == "media_lead" and p1.get("media_requires_review"):
        return "P1", "Media lead requires human review"

    return "P2", "Matched topic keywords"


def _category_for(item: NormalizedItem, skill: TopicSkill) -> str:
    if item.item_type == "weather":
        return "weather"
    if item.trust_level == "media_lead":
        return "media_lead"
    if "accident" in skill.name or "safety" in skill.name:
        return "site_safety"
    return item.item_type


def _has_any(text: str, keywords: list[str]) -> bool:
    return bool(_first_match(text, keywords))


def _first_match(text: str, keywords: list[str]) -> str | None:
    for keyword in keywords:
        if keyword and keyword in text:
            return keyword
    return None


def _first_combined_match(text: str, combinations: list[list[str]]) -> list[str] | None:
    for combo in combinations:
        if all(keyword in text for keyword in combo):
            return combo
    return None


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword and keyword in text]
