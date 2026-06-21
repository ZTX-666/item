from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from ..config import settings
from ..models import ToolFile, ToolResult
from ..runner import CommandError, run_command
from ..tasks import new_task_id, record_task_event, task_dir


class RtmpSnapshotRequest(BaseModel):
    url: str | None = None
    count: int = Field(default=1, ge=1, le=50)
    interval: float = Field(default=5.0, ge=0.0, le=3600.0)
    prefix: str = Field(default="snapshot", min_length=1, max_length=64)
    retries: int = Field(default=3, ge=1, le=30)
    retry_delay: float = Field(default=2.0, ge=0.0, le=60.0)
    timeout_seconds: int = Field(default=180, ge=10, le=7200)


def run_rtmp_snapshot(req: RtmpSnapshotRequest) -> ToolResult:
    task_id = new_task_id("rtmp")
    out_dir = task_dir(task_id) / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)

    url = req.url or settings.default_rtmp_url
    command = [
        settings.rtmp_python,
        str(settings.rtmp_snapshot_script),
        url,
        "--output",
        str(out_dir),
        "--count",
        str(req.count),
        "--interval",
        str(req.interval),
        "--prefix",
        req.prefix,
        "--retries",
        str(req.retries),
        "--retry-delay",
        str(req.retry_delay),
    ]
    if req.count == 1:
        command.append("--once")

    record_task_event(task_id, {"tool": "rtmp_snapshot", "status": "running", "url": url})
    try:
        result = run_command(command, cwd=settings.rtmp_snapshot_script.parent, timeout=req.timeout_seconds)
    except CommandError as exc:
        record_task_event(task_id, {"tool": "rtmp_snapshot", "status": "failed", "stderr": exc.stderr})
        return ToolResult(
            ok=False,
            tool="rtmp_snapshot",
            task_id=task_id,
            summary="RTMP 截图失败。",
            logs=[exc.stdout, exc.stderr],
            error=str(exc),
        )

    files = [
        ToolFile(path=str(p), name=p.name, kind="image", mime_type="image/jpeg")
        for p in sorted(Path(out_dir).glob("*.jpg"))
    ]
    record_task_event(task_id, {"tool": "rtmp_snapshot", "status": "done", "file_count": len(files)})
    return ToolResult(
        ok=True,
        tool="rtmp_snapshot",
        task_id=task_id,
        summary=f"RTMP 截图完成，共生成 {len(files)} 张图片。",
        files=files,
        data={"url": url, "output_dir": str(out_dir)},
        logs=[result.stdout, result.stderr],
    )
