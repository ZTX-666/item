from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from chitung_center.confirmation_service import create_pending_confirmation
from chitung_center.external_monitor_store import (
    create_run,
    finish_run,
    get_last_run,
    get_last_success_run,
    get_settings,
    get_source_states,
    ingest_workflow_result,
    list_events,
    list_runs,
    next_run_at,
    save_settings,
)
from chitung_center.models import ChatMessageRequest
from chitung_center.workflow_engine import workflow_engine


class ExternalMonitorScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._last_error: str | None = None

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop(), name="external-info-monitor")

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                settings = get_settings()
                if settings.get("enabled", True) and self._is_due(settings):
                    await self.run_once(trigger="schedule")
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self._last_error = str(exc)
                await asyncio.sleep(30)

    def _is_due(self, settings: dict[str, Any]) -> bool:
        last_run = get_last_run()
        if not last_run:
            return True
        if last_run.get("status") == "running":
            return False
        try:
            last_started = datetime.fromisoformat(str(last_run["started_at"]))
        except (TypeError, ValueError):
            return True
        interval_seconds = max(5, int(settings.get("interval_minutes") or 60)) * 60
        return (datetime.now(timezone.utc) - last_started).total_seconds() >= interval_seconds

    async def run_once(self, *, trigger: str = "manual") -> dict[str, Any]:
        if self._running:
            return {"ok": False, "status": "skipped", "reason": "monitor_already_running"}

        self._running = True
        run = create_run()
        run_id = run["run_id"]
        settings = get_settings()
        try:
            request = ChatMessageRequest(
                message=_build_prompt(settings),
                channel="external_monitor",
                user_id="external_monitor",
                metadata={
                    "entry": "external_info_monitor_scheduler",
                    "trigger": trigger,
                    "area": settings.get("area"),
                    "sources": settings.get("sources"),
                    "keywords": settings.get("keywords"),
                    "lookback_hours": settings.get("lookback_hours"),
                    "delivery_mode": settings.get("delivery_mode"),
                    "recipient": settings.get("recipient"),
                },
            )
            result = await workflow_engine.run_template("workflow_daily_risk_briefing", request)
            ingest_summary = ingest_workflow_result(run_id, result, lookback_hours=int(settings.get("lookback_hours") or 24))
            alert_summary = await self._create_alerts(ingest_summary.get("new_alert_cards", []), result, settings)
            summary = {
                **ingest_summary,
                "alert_count": alert_summary["alert_count"],
                "alerts": alert_summary["alerts"],
                "trigger": trigger,
            }
            finished = finish_run(
                run_id,
                status="success" if result.get("ok") else "failed",
                workflow_run_id=str(result.get("workflow_run_id") or ""),
                summary=summary,
                error=None if result.get("ok") else str(result.get("error") or "workflow_failed"),
            )
            self._last_error = None if result.get("ok") else finished.get("error")
            return {"ok": bool(result.get("ok")), "run": finished, "workflow": result}
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc)
            finished = finish_run(run_id, status="failed", summary={"trigger": trigger}, error=str(exc))
            return {"ok": False, "run": finished, "error": str(exc)}
        finally:
            self._running = False

    async def _create_alerts(
        self,
        cards: list[dict[str, Any]],
        workflow_result: dict[str, Any],
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        alerts: list[dict[str, Any]] = []
        for card in cards:
            priority = str(card.get("priority") or "P2")
            if priority == "P0" and not settings.get("alert_p0", True):
                continue
            if priority == "P1" and not settings.get("alert_p1", True):
                continue
            if priority not in {"P0", "P1"}:
                continue
            confirmation = await create_pending_confirmation(
                action_type="external_info_alert",
                title=f"{priority} 外部讯息提醒：{card.get('title', '未命名讯息')}",
                summary=str(card.get("recommended_action") or "请安全负责人复核该外部讯息。"),
                payload={
                    "card": card,
                    "workflow_run_id": workflow_result.get("workflow_run_id"),
                    "recommended_action": card.get("recommended_action"),
                },
                risk_level="high" if priority == "P1" else "critical",
                source_channel="external_monitor",
                source_user_id="external_monitor",
                workflow_run_id=str(workflow_result.get("workflow_run_id") or ""),
                idempotency_key=f"external-info-alert:{card.get('card_id') or card.get('title')}",
                metadata={"priority": priority, "source_category": card.get("source_category")},
            )
            alerts.append({"card_id": card.get("card_id"), "priority": priority, "confirmation": confirmation})
        return {"alert_count": len(alerts), "alerts": alerts}

    def status(self) -> dict[str, Any]:
        settings = get_settings()
        last_run = get_last_run()
        last_success = get_last_success_run()
        return {
            "ok": True,
            "running": self._running,
            "scheduler_active": bool(self._task and not self._task.done()),
            "settings": settings,
            "last_run": last_run,
            "last_success_run": last_success,
            "next_run_at": next_run_at(settings, last_run),
            "last_error": self._last_error or (last_run or {}).get("error"),
            "sources": get_source_states().get("items", []),
        }

    def list_runs(self, limit: int = 20) -> dict[str, Any]:
        return list_runs(limit)

    def list_events(self, limit: int = 50, lookback_hours: int | None = None) -> dict[str, Any]:
        return list_events(limit, lookback_hours=lookback_hours)

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = save_settings(payload)
        return self.status() | {"settings": settings}


def _build_prompt(settings: dict[str, Any]) -> str:
    sources = "、".join(settings.get("sources") or ["weather", "official", "media"])
    keywords = "、".join(settings.get("keywords") or ["施工安全", "天气预警", "工伤意外"])
    lookback_hours = int(settings.get("lookback_hours") or 24)
    delivery = (
        f"生成后准备发送到飞书：{settings.get('recipient')}"
        if settings.get("delivery_mode") == "feishu"
        else "只生成草稿"
    )
    return (
        f"生成最近 {lookback_hours} 小时外部讯息简报。"
        f"项目范围：{settings.get('area') or '香港项目'}。关注：{keywords}。"
        f"来源：{sources}。{delivery}。"
    )


external_monitor_scheduler = ExternalMonitorScheduler()
