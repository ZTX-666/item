from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..config import ROOT
from ..models import ToolFile, ToolResult


PROMPTS_DIR = ROOT / "prompts"


class PromptTemplateListRequest(BaseModel):
    pass


class PromptTemplateRenderRequest(BaseModel):
    name: str
    variables: dict[str, Any] = Field(default_factory=dict)


def list_prompt_templates(req: PromptTemplateListRequest) -> ToolResult:
    del req
    items = []
    for path in sorted(PROMPTS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.strip()), path.stem)
        items.append({"name": path.stem, "title": title, "path": str(path)})
    return ToolResult(ok=True, tool="list_prompt_templates", summary=f"Found {len(items)} prompt templates.", data={"items": items})


def render_prompt_template(req: PromptTemplateRenderRequest) -> ToolResult:
    path = _prompt_path(req.name)
    text = path.read_text(encoding="utf-8", errors="ignore")
    rendered = text
    for key, value in req.variables.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return ToolResult(
        ok=True,
        tool="render_prompt_template",
        summary=f"Rendered prompt template {req.name}.",
        files=[ToolFile(path=str(path), name=path.name, mime_type="text/markdown")],
        data={"name": req.name, "prompt": rendered, "variables": req.variables},
    )


def _prompt_path(name: str) -> Path:
    safe_name = Path(name).stem
    path = PROMPTS_DIR / f"{safe_name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {safe_name}")
    return path
