from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolFile(BaseModel):
    path: str
    name: str | None = None
    kind: str = "file"
    mime_type: str | None = None


class ToolResult(BaseModel):
    ok: bool
    tool: str
    summary: str
    task_id: str | None = None
    files: list[ToolFile] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list)
    error: str | None = None


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class HealthResult(BaseModel):
    ok: bool
    workspace: str
    tools: dict[str, dict[str, Any]]
