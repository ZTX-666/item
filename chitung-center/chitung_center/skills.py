from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chitung_center.config import settings

SKILL_USE_PREFIX = re.compile(r"🔨\s*使用技能[：:]\s*(.+?)(?:\n|$)", re.IGNORECASE)


@dataclass
class SkillInfo:
    name: str
    path: str
    summary: str
    enabled: bool = True
    category: str = "builtin"
    status: str = "ready"
    phase: str = ""
    tools: list[str] = field(default_factory=list)
    workflow: str = ""
    display_name: str = ""
    description: str = ""
    intents: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    example_prompts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "summary": self.summary,
            "enabled": self.enabled,
            "category": self.category,
            "status": self.status,
            "phase": self.phase,
            "tools": self.tools,
            "workflow": self.workflow,
            "display_name": self.display_name,
            "description": self.description,
            "intents": self.intents,
            "triggers": self.triggers,
            "example_prompts": self.example_prompts,
        }


@dataclass
class SkillRoute:
    skill_name: str
    intent: str
    confidence: float
    reason: str


class SkillLoader:
    INDEX_FILE = "skills_index.json"

    def __init__(self, skills_dir: Path | None = None) -> None:
        self.skills_dir = skills_dir or settings.chitung_skills_dir
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.skills_dir / self.INDEX_FILE
        self._index = self._load_index()

    def _load_index(self) -> dict[str, dict[str, Any]]:
        if not self._index_path.exists():
            return {}
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save_index(self) -> None:
        self._index_path.write_text(json.dumps(self._index, ensure_ascii=False, indent=2), encoding="utf-8")

    def _meta(self, name: str) -> dict[str, Any]:
        meta = self._index.get(name, {})
        return meta if isinstance(meta, dict) else {}

    def _set_meta(self, name: str, meta: dict[str, Any]) -> None:
        self._index[name] = meta
        self._save_index()

    def list_skills(self, enabled_only: bool = False) -> list[SkillInfo]:
        skills: list[SkillInfo] = []
        for path in sorted(self.skills_dir.glob("*/SKILL.md")):
            name = path.parent.name
            meta = self._meta(name)
            if enabled_only and meta.get("enabled") is False:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            lines = [line.strip("# ").strip() for line in text.splitlines() if line.strip()]
            summary = lines[1] if len(lines) > 1 else "No summary provided."
            routing = self._routing_fields(name, summary)
            skills.append(
                SkillInfo(
                    name=name,
                    path=str(path),
                    summary=summary,
                    enabled=bool(meta.get("enabled", True)),
                    category=str(meta.get("category", "builtin")),
                    status=str(meta.get("status", "ready")),
                    phase=str(meta.get("phase", "")),
                    tools=meta.get("tools") if isinstance(meta.get("tools"), list) else self._extract_tools(text),
                    workflow=str(meta.get("workflow", "")),
                    display_name=routing["display_name"],
                    description=routing["description"],
                    intents=routing["intents"],
                    triggers=routing["triggers"],
                    example_prompts=routing["example_prompts"],
                )
            )
        return skills

    def get_info(self, name: str) -> SkillInfo | None:
        for skill in self.list_skills():
            if skill.name == name:
                return skill
        return None

    def read_skill(self, name: str) -> str | None:
        if any(part in name for part in ("/", "\\", "..")):
            return None
        path = self.skills_dir / name / "SKILL.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8", errors="ignore")

    def read_config(self, name: str) -> dict[str, Any] | None:
        if self.read_skill(name) is None:
            return None
        path = self.skills_dir / name / "config.json"
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def write_config(self, name: str, config: dict[str, Any]) -> bool:
        if self.read_skill(name) is None:
            return False
        path = self.skills_dir / name / "config.json"
        path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        return True

    def set_enabled(self, name: str, enabled: bool) -> bool:
        if self.read_skill(name) is None:
            return False
        meta = self._meta(name)
        meta["enabled"] = enabled
        self._set_meta(name, meta)
        return True

    def import_skill(self, name: str, content: str) -> SkillInfo | None:
        clean_name = _clean_name(name)
        if not clean_name or not content.strip():
            return None
        skill_dir = self.skills_dir / clean_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        md_path = skill_dir / "SKILL.md"
        md_path.write_text(content, encoding="utf-8")
        lines = [line.strip("# ").strip() for line in content.splitlines() if line.strip()]
        summary = lines[1] if len(lines) > 1 else "Imported skill."
        tools = self._extract_tools(content)
        meta = {
            "enabled": True,
            "category": "external",
            "status": "ready",
            "phase": "Imported",
            "tools": tools,
            "workflow": "",
        }
        self._set_meta(clean_name, meta)
        routing = self._routing_fields(clean_name, summary)
        return SkillInfo(
            name=clean_name,
            path=str(md_path),
            summary=summary,
            enabled=True,
            category="external",
            status="ready",
            phase="Imported",
            tools=tools,
            display_name=routing["display_name"],
            description=routing["description"],
            intents=routing["intents"],
            triggers=routing["triggers"],
            example_prompts=routing["example_prompts"],
        )

    def delete_skill(self, name: str) -> bool:
        info = self.get_info(name)
        if not info or info.category != "external":
            return False
        skill_dir = self.skills_dir / name
        if not skill_dir.exists():
            return False
        shutil.rmtree(skill_dir, ignore_errors=True)
        self._index.pop(name, None)
        self._save_index()
        return True

    def skill_for_intent(self, intent: str) -> SkillInfo | None:
        name = INTENT_TO_SKILL.get(intent)
        if not name:
            return None
        for skill in self.list_skills():
            if skill.name == name and skill.enabled:
                return skill
        return None

    def primary_intent_for_skill(self, skill_name: str) -> str | None:
        info = self.get_info(skill_name)
        if not info:
            return None
        if info.intents:
            return info.intents[0]
        return SKILL_TO_INTENT.get(skill_name)

    def resolve_route(self, message: str, metadata: dict[str, Any] | None = None) -> SkillRoute | None:
        metadata = metadata or {}
        forced_name = str(metadata.get("skill") or metadata.get("skill_name") or "").strip()
        if forced_name:
            return self._route_for_skill_name(forced_name, reason="metadata.skill 指定技能")

        prefix_match = SKILL_USE_PREFIX.search(message)
        if prefix_match:
            label = prefix_match.group(1).strip()
            skill_name = self._match_skill_label(label)
            if skill_name:
                return self._route_for_skill_name(skill_name, reason=f"识别到技能前缀：{label}")

        trigger_route = self._route_by_triggers(message)
        if trigger_route:
            return trigger_route

        return None

    def routing_catalog_for_llm(self, enabled_only: bool = True) -> list[dict[str, Any]]:
        catalog: list[dict[str, Any]] = []
        for skill in self.list_skills(enabled_only=enabled_only):
            if not skill.intents:
                continue
            catalog.append(
                {
                    "skill": skill.name,
                    "display_name": skill.display_name,
                    "description": skill.description,
                    "intents": skill.intents,
                    "triggers": skill.triggers[:12],
                    "example_prompts": skill.example_prompts[:4],
                }
            )
        return catalog

    def trigger_rules(self) -> list[tuple[str, list[str]]]:
        rules: list[tuple[str, list[str]]] = []
        for skill in self.list_skills(enabled_only=True):
            if not skill.triggers or not skill.intents:
                continue
            rules.append((skill.intents[0], skill.triggers))
        return rules

    def _route_for_skill_name(self, skill_name: str, *, reason: str) -> SkillRoute | None:
        info = self.get_info(skill_name)
        if not info:
            return None
        intent = self.primary_intent_for_skill(skill_name)
        if not intent:
            return None
        return SkillRoute(
            skill_name=skill_name,
            intent=intent,
            confidence=0.94,
            reason=reason,
        )

    def _route_by_triggers(self, message: str) -> SkillRoute | None:
        lowered = message.lower()
        best: SkillRoute | None = None
        best_hits = 0
        for skill in self.list_skills(enabled_only=True):
            if not skill.triggers or not skill.intents:
                continue
            hits = [trigger for trigger in skill.triggers if trigger.lower() in lowered]
            if len(hits) > best_hits:
                best_hits = len(hits)
                best = SkillRoute(
                    skill_name=skill.name,
                    intent=skill.intents[0],
                    confidence=min(0.9, 0.5 + 0.1 * len(hits)),
                    reason=f"技能触发词匹配：{', '.join(hits[:4])}",
                )
        return best if best_hits > 0 else None

    def _match_skill_label(self, label: str) -> str | None:
        normalized = _normalize_label(label)
        if not normalized:
            return None
        for skill in self.list_skills():
            candidates = {
                _normalize_label(skill.name),
                _normalize_label(skill.display_name),
                _normalize_label(skill.name.replace("-", " ")),
            }
            if normalized in candidates:
                return skill.name
        for skill in self.list_skills():
            display = _normalize_label(skill.display_name)
            if display and (display in normalized or normalized in display):
                return skill.name
        return None

    def _routing_fields(self, name: str, summary: str) -> dict[str, Any]:
        config = self.read_config(name) or {}
        intents = config.get("intents")
        if not isinstance(intents, list) or not intents:
            intent = SKILL_TO_INTENT.get(name)
            intents = [intent] if intent else []
        triggers = config.get("triggers")
        examples = config.get("example_prompts")
        return {
            "display_name": str(config.get("display_name") or _humanize_skill_name(name)),
            "description": str(config.get("description") or summary),
            "intents": [str(item) for item in intents if str(item).strip()],
            "triggers": [str(item) for item in triggers if isinstance(triggers, list) and str(item).strip()],
            "example_prompts": [str(item) for item in examples if isinstance(examples, list) and str(item).strip()],
        }

    @staticmethod
    def _extract_tools(text: str) -> list[str]:
        tools: list[str] = []
        in_tools_section = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("##") and ("tool" in stripped.lower() or "preferred" in stripped.lower()):
                in_tools_section = True
                continue
            if in_tools_section and stripped.startswith("##"):
                in_tools_section = False
            if in_tools_section:
                tools.extend(re.findall(r"`([a-zA-Z_][a-zA-Z0-9_]*)`", stripped))
        return list(dict.fromkeys(tools))


INTENT_TO_SKILL: dict[str, str] = {
    "hazard_intake": "hazard-intake",
    "visual_detection": "visual-patrol",
    "weather_news_risk": "daily-risk-briefing",
    "external_info_monitor": "external-info-monitor",
    "document_form": "shanshan-doc",
    "knowledge_query": "knowledge-query",
    "whatsapp_sql_query": "whatsapp-sql-query",
    "whatsapp_wacli_ops": "whatsapp-wacli-ops",
    "long_term_memory": "long-term-memory",
}

SKILL_TO_INTENT = {skill: intent for intent, skill in INTENT_TO_SKILL.items()}


def _clean_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-_")
    return cleaned[:80]


def _humanize_skill_name(name: str) -> str:
    return " ".join(part.capitalize() for part in name.replace("_", "-").split("-") if part)


def _normalize_label(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


skill_loader = SkillLoader()
