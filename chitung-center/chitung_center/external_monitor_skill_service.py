from __future__ import annotations

import re
from typing import Any

from chitung_center.external_monitor_scheduler import external_monitor_scheduler
from chitung_center.job_service import start_background_job, update_progress


SOURCE_KEYWORDS = {
    "weather": ["天气", "天文台", "暴雨", "台风", "酷热"],
    "official": ["政府", "劳工处", "屋宇署", "发展局", "官方", "公告"],
    "media": ["媒体", "新闻", "白名单", "报纸", "电台"],
}


async def apply_external_monitor_skill(message: str) -> dict[str, Any]:
    payload = _parse_settings(message)
    changed = bool(payload)
    status = external_monitor_scheduler.save_settings(payload) if payload else external_monitor_scheduler.status()
    should_run = _should_run_now(message)
    job: dict[str, Any] | None = None
    if should_run:
        job = _start_monitor_job(message)
    settings = status.get("settings", {})
    summary = _build_summary(settings, changed=changed, job=job)
    return {
        "ok": True,
        "changed": changed,
        "run_started": bool(job),
        "job_id": (job or {}).get("job_id"),
        "settings": settings,
        "status": status,
        "summary": summary,
    }


def _start_monitor_job(message: str) -> dict[str, Any]:
    async def runner(job_id: str) -> dict[str, Any]:
        update_progress(job_id, 20, "技能已触发外部讯息监听")
        result = await external_monitor_scheduler.run_once(trigger=f"skill:{job_id}")
        update_progress(job_id, 90, "技能监听已完成")
        return result

    return start_background_job(
        job_type="external_info_monitor",
        title="技能触发外部讯息监听",
        source_module="external_info_skill",
        request={"message": message},
        runner=runner,
    )


def _parse_settings(message: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    interval = _first_int_after(message, ["每", "频率", "间隔"])
    if interval:
        payload["interval_minutes"] = max(5, min(interval, 24 * 60))
    lookback = _first_int_after(message, ["最近", "过去", "回看", "时间窗口"])
    if lookback:
        payload["lookback_hours"] = max(1, min(lookback, 24 * 30))
    keywords = _parse_keywords(message)
    if keywords:
        payload["keywords"] = keywords
    sources = _parse_sources(message)
    if sources:
        payload["sources"] = sources
    if any(word in message for word in ["开启监听", "启用监听", "保持监听", "打开监听"]):
        payload["enabled"] = True
    if any(word in message for word in ["关闭监听", "停止监听", "暂停监听"]):
        payload["enabled"] = False
    return payload


def _parse_keywords(message: str) -> list[str]:
    match = re.search(r"关键词[：:为是]?\s*([^。；;\n]+)", message)
    if not match:
        return []
    raw = match.group(1)
    parts = re.split(r"[,，、\s]+", raw)
    return [part.strip() for part in parts if part.strip()][:20]


def _parse_sources(message: str) -> list[str]:
    sources: list[str] = []
    for source, words in SOURCE_KEYWORDS.items():
        if any(word in message for word in words):
            sources.append(source)
    return sources


def _first_int_after(message: str, markers: list[str]) -> int | None:
    for marker in markers:
        match = re.search(rf"{marker}\D*(\d+)\s*(分钟|分鐘|分|小时|小時|h|H)?", message)
        if not match:
            continue
        value = int(match.group(1))
        unit = match.group(2) or ""
        if unit in {"小时", "小時", "h", "H"} and marker in {"每", "频率", "间隔"}:
            return value * 60
        return value
    return None


def _should_run_now(message: str) -> bool:
    return any(word in message for word in ["立即", "马上", "立刻", "现在监听", "跑一次", "执行一次", "触发"])


def _build_summary(settings: dict[str, Any], *, changed: bool, job: dict[str, Any] | None) -> str:
    action = "已更新监听设置" if changed else "当前监听设置未改变"
    run = f"，并已启动后台任务 {job.get('job_id')}" if job else ""
    return (
        f"{action}{run}。频率：每 {settings.get('interval_minutes')} 分钟；"
        f"时间窗口：最近 {settings.get('lookback_hours')} 小时；"
        f"来源：{'、'.join(settings.get('sources') or [])}；"
        f"关键词：{'、'.join(settings.get('keywords') or [])}。"
    )
