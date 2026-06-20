from __future__ import annotations

import importlib.util
from pathlib import Path

from pydantic import BaseModel

from ..config import settings
from ..models import ToolFile, ToolResult
from ..tasks import new_task_id, record_task_event, task_dir


class GenerateReportRequest(BaseModel):
    output_path: str | None = None
    timeout_seconds: int = 180


def generate_report(req: GenerateReportRequest) -> ToolResult:
    task_id = new_task_id("report")
    base = task_dir(task_id)
    desired_output = Path(req.output_path) if req.output_path else base / "数字员工社区建设方案（飞书版）.docx"

    record_task_event(task_id, {"tool": "generate_report", "status": "running"})
    try:
        spec = importlib.util.spec_from_file_location("agent_toolbox_report_template", settings.report_script)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load report script: {settings.report_script}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        document = module.build_document()
        desired_output.parent.mkdir(parents=True, exist_ok=True)
        document.save(str(desired_output))
    except Exception as exc:
        record_task_event(task_id, {"tool": "generate_report", "status": "failed", "error": str(exc)})
        return ToolResult(
            ok=False,
            tool="generate_report",
            task_id=task_id,
            summary="报告生成失败。",
            error=str(exc),
        )

    files = []
    if desired_output.exists():
        files.append(
            ToolFile(
                path=str(desired_output),
                name=desired_output.name,
                kind="document",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        )

    record_task_event(task_id, {"tool": "generate_report", "status": "done", "file_count": len(files)})
    return ToolResult(
        ok=bool(files),
        tool="generate_report",
        task_id=task_id,
        summary="报告生成完成。" if files else "脚本运行完成，但未找到输出文件。",
        files=files,
        data={"output_path": str(desired_output)},
        error=None if files else f"Expected output not found: {desired_output}",
    )
