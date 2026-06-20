from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chitung_center.config import settings


@dataclass(frozen=True)
class SkillInfo:
    name: str
    path: str
    summary: str


class SkillLoader:
    def __init__(self, skills_dir: Path | None = None) -> None:
        self.skills_dir = skills_dir or settings.chitung_skills_dir
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def list_skills(self) -> list[SkillInfo]:
        skills: list[SkillInfo] = []
        for path in sorted(self.skills_dir.glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            lines = [line.strip("# ").strip() for line in text.splitlines() if line.strip()]
            summary = lines[1] if len(lines) > 1 else "No summary provided."
            skills.append(
                SkillInfo(
                    name=path.parent.name,
                    path=str(path),
                    summary=summary,
                )
            )
        return skills

    def read_skill(self, name: str) -> str | None:
        if any(part in name for part in ("/", "\\", "..")):
            return None
        path = self.skills_dir / name / "SKILL.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8", errors="ignore")

    def skill_for_intent(self, intent: str) -> SkillInfo | None:
        name = INTENT_TO_SKILL.get(intent)
        if not name:
            return None
        for skill in self.list_skills():
            if skill.name == name:
                return skill
        return None


# Maps router intents to the SKILL.md directory that governs that flow.
INTENT_TO_SKILL: dict[str, str] = {
    "hazard_intake": "hazard-intake",
    "weather_news_risk": "daily-risk-briefing",
    "document_form": "shanshan-doc",
}


skill_loader = SkillLoader()
