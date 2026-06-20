from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chitung_center.audit import audit_logger
from chitung_center.config import ROOT, settings
from chitung_center.llm_gateway import llm_gateway
from chitung_center.toolbox_client import toolbox_client

PLAN_STATUSES = {
    "DRAFT",
    "PLANNED",
    "PENDING_CONFIRMATION",
    "CONFIRMED",
    "EXECUTING",
    "SUCCEEDED",
    "FAILED",
}

RISK_LEVELS = {"low", "medium", "high", "critical"}
HIGH_RISK_LEVELS = {"high", "critical"}
PLANNER_TIMEOUT_SECONDS = 18
TOOL_EXECUTION_TIMEOUT_SECONDS = 35
MAX_ACTIONS_PER_PLAN = 8

WORKFLOW_ALLOWED_TOOLS: dict[str, set[str]] = {
    "daily_risk_briefing": {
        "fetch_hko_weather",
        "fetch_hk_safety_updates",
        "summarize_external_risks",
        "draft_daily_risk_briefing",
    },
    "hazard_intake": {
        "ingest_chat_hazards",
        "connect_hazard_actions",
    },
    "smart_form_filling": {
        "search_form_templates",
        "prefill_form_fields",
        "generate_docx_from_template",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_load(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class HybridOrchestrationStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (ROOT / "data" / "hybrid_orchestration.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orchestration_plans (
                  plan_id TEXT PRIMARY KEY,
                  session_id TEXT NOT NULL,
                  user_input TEXT NOT NULL,
                  workflow TEXT NOT NULL,
                  planner_mode TEXT NOT NULL,
                  status TEXT NOT NULL,
                  fallback_used INTEGER NOT NULL DEFAULT 0,
                  fallback_reason TEXT,
                  proposed_actions_json TEXT NOT NULL,
                  selected_action_ids_json TEXT NOT NULL DEFAULT '[]',
                  idempotency_key TEXT,
                  result_json TEXT,
                  last_error TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orchestration_actions (
                  action_id TEXT PRIMARY KEY,
                  plan_id TEXT NOT NULL,
                  sequence_no INTEGER NOT NULL,
                  tool_name TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  risk_level TEXT NOT NULL,
                  requires_confirmation INTEGER NOT NULL DEFAULT 1,
                  status TEXT NOT NULL,
                  retry_count INTEGER NOT NULL DEFAULT 0,
                  max_retries INTEGER NOT NULL DEFAULT 2,
                  idempotency_key TEXT,
                  result_json TEXT,
                  last_error TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  FOREIGN KEY(plan_id) REFERENCES orchestration_plans(plan_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orchestration_audit_events (
                  audit_id TEXT PRIMARY KEY,
                  event_type TEXT NOT NULL,
                  session_id TEXT,
                  plan_id TEXT,
                  action_id TEXT,
                  status TEXT,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_session ON orchestration_plans(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_action_plan ON orchestration_actions(plan_id)")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_plan_idempotency ON orchestration_plans(plan_id, idempotency_key)")

    def write_audit(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        session_id: str | None = None,
        plan_id: str | None = None,
        action_id: str | None = None,
        status: str | None = None,
    ) -> str:
        audit_id = _new_id("audit")
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO orchestration_audit_events
                (audit_id, event_type, session_id, plan_id, action_id, status, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (audit_id, event_type, session_id, plan_id, action_id, status, _json(payload), now),
            )
        audit_logger.write(
            "hybrid_orchestration_audit",
            {
                "audit_id": audit_id,
                "event_type": event_type,
                "session_id": session_id,
                "plan_id": plan_id,
                "action_id": action_id,
                "status": status,
                "payload": payload,
            },
        )
        return audit_id

    def create_plan(
        self,
        *,
        session_id: str,
        user_input: str,
        workflow: str,
        planner_mode: str,
        fallback_used: bool,
        fallback_reason: str | None,
        actions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        now = _now()
        plan_id = _new_id("plan")
        action_rows: list[dict[str, Any]] = []
        for index, action in enumerate(actions, start=1):
            action_id = _new_id("action")
            risk_level = str(action.get("risk_level") or "medium").lower()
            if risk_level not in RISK_LEVELS:
                risk_level = "medium"
            requires_confirmation = bool(action.get("requires_confirmation", True))
            if risk_level in HIGH_RISK_LEVELS:
                requires_confirmation = True
            action_rows.append(
                {
                    "action_id": action_id,
                    "plan_id": plan_id,
                    "sequence_no": index,
                    "tool_name": str(action.get("tool_name") or "").strip(),
                    "payload_json": _json(action.get("payload") or {}),
                    "risk_level": risk_level,
                    "requires_confirmation": 1 if requires_confirmation else 0,
                    "status": "PLANNED",
                    "retry_count": 0,
                    "max_retries": int(action.get("max_retries") or 2),
                    "idempotency_key": None,
                    "result_json": None,
                    "last_error": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )

        status = "PLANNED"
        if action_rows:
            status = "PENDING_CONFIRMATION"

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO orchestration_plans
                (plan_id, session_id, user_input, workflow, planner_mode, status, fallback_used, fallback_reason,
                 proposed_actions_json, selected_action_ids_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?)
                """,
                (
                    plan_id,
                    session_id,
                    user_input,
                    workflow,
                    planner_mode,
                    status,
                    1 if fallback_used else 0,
                    fallback_reason,
                    _json(action_rows),
                    now,
                    now,
                ),
            )
            conn.executemany(
                """
                INSERT INTO orchestration_actions
                (action_id, plan_id, sequence_no, tool_name, payload_json, risk_level, requires_confirmation, status,
                 retry_count, max_retries, idempotency_key, result_json, last_error, created_at, updated_at)
                VALUES (:action_id, :plan_id, :sequence_no, :tool_name, :payload_json, :risk_level, :requires_confirmation, :status,
                        :retry_count, :max_retries, :idempotency_key, :result_json, :last_error, :created_at, :updated_at)
                """,
                action_rows,
            )
        return self.get_plan(plan_id)

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            plan = conn.execute("SELECT * FROM orchestration_plans WHERE plan_id = ?", (plan_id,)).fetchone()
            if not plan:
                raise ValueError(f"Unknown plan_id: {plan_id}")
            actions = conn.execute(
                "SELECT * FROM orchestration_actions WHERE plan_id = ? ORDER BY sequence_no ASC",
                (plan_id,),
            ).fetchall()
        return {
            "plan_id": str(plan["plan_id"]),
            "session_id": str(plan["session_id"]),
            "user_input": str(plan["user_input"]),
            "workflow": str(plan["workflow"]),
            "planner_mode": str(plan["planner_mode"]),
            "status": str(plan["status"]),
            "fallback_used": bool(plan["fallback_used"]),
            "fallback_reason": plan["fallback_reason"],
            "selected_action_ids": _json_load(plan["selected_action_ids_json"], []),
            "idempotency_key": plan["idempotency_key"],
            "result": _json_load(plan["result_json"], {}),
            "last_error": plan["last_error"],
            "created_at": plan["created_at"],
            "updated_at": plan["updated_at"],
            "actions": [
                {
                    "action_id": str(action["action_id"]),
                    "sequence_no": int(action["sequence_no"]),
                    "tool_name": str(action["tool_name"]),
                    "payload": _json_load(action["payload_json"], {}),
                    "risk_level": str(action["risk_level"]),
                    "requires_confirmation": bool(action["requires_confirmation"]),
                    "status": str(action["status"]),
                    "retry_count": int(action["retry_count"]),
                    "max_retries": int(action["max_retries"]),
                    "result": _json_load(action["result_json"], {}),
                    "last_error": action["last_error"],
                }
                for action in actions
            ],
        }

    def transition_plan_status(self, plan_id: str, target_status: str, *, last_error: str | None = None) -> None:
        if target_status not in PLAN_STATUSES:
            raise ValueError(f"Unsupported target status: {target_status}")
        plan = self.get_plan(plan_id)
        current = plan["status"]
        allowed = {
            "DRAFT": {"PLANNED"},
            "PLANNED": {"PENDING_CONFIRMATION"},
            "PENDING_CONFIRMATION": {"CONFIRMED", "FAILED"},
            "CONFIRMED": {"EXECUTING", "FAILED"},
            "EXECUTING": {"SUCCEEDED", "FAILED"},
            "FAILED": set(),
            "SUCCEEDED": set(),
        }
        if target_status != current and target_status not in allowed.get(current, set()):
            raise ValueError(f"Invalid transition: {current} -> {target_status}")
        with self._connect() as conn:
            conn.execute(
                "UPDATE orchestration_plans SET status = ?, last_error = ?, updated_at = ? WHERE plan_id = ?",
                (target_status, last_error, _now(), plan_id),
            )

    def confirm_plan(self, plan_id: str, selected_action_ids: list[str]) -> dict[str, Any]:
        plan = self.get_plan(plan_id)
        if plan["status"] != "PENDING_CONFIRMATION":
            raise ValueError(f"Plan must be pending confirmation. Current: {plan['status']}")
        action_ids = {item["action_id"] for item in plan["actions"]}
        selected = [item for item in selected_action_ids if item in action_ids]
        if not selected:
            raise ValueError("No valid action ids selected for confirmation.")
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE orchestration_plans SET status = 'CONFIRMED', selected_action_ids_json = ?, updated_at = ? WHERE plan_id = ?",
                (_json(selected), now, plan_id),
            )
            for action in plan["actions"]:
                status = "CONFIRMED" if action["action_id"] in selected else "REJECTED"
                conn.execute(
                    "UPDATE orchestration_actions SET status = ?, updated_at = ? WHERE action_id = ?",
                    (status, now, action["action_id"]),
                )
        return self.get_plan(plan_id)

    def set_plan_execution_state(self, plan_id: str, idempotency_key: str | None) -> dict[str, Any]:
        plan = self.get_plan(plan_id)
        if plan["status"] == "SUCCEEDED" and idempotency_key and plan["idempotency_key"] == idempotency_key:
            return plan
        if plan["status"] != "CONFIRMED":
            raise ValueError(f"Plan must be CONFIRMED before execute. Current: {plan['status']}")
        with self._connect() as conn:
            conn.execute(
                "UPDATE orchestration_plans SET status = 'EXECUTING', idempotency_key = ?, updated_at = ? WHERE plan_id = ?",
                (idempotency_key, _now(), plan_id),
            )
        return self.get_plan(plan_id)

    def mark_action_running(self, action_id: str, idempotency_key: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE orchestration_actions SET status = 'EXECUTING', idempotency_key = ?, updated_at = ? WHERE action_id = ?",
                (idempotency_key, _now(), action_id),
            )

    def mark_action_result(
        self,
        action_id: str,
        *,
        ok: bool,
        result: dict[str, Any],
        error: str | None = None,
        increment_retry: bool = False,
    ) -> None:
        status = "SUCCEEDED" if ok else "FAILED"
        with self._connect() as conn:
            if increment_retry:
                conn.execute(
                    """
                    UPDATE orchestration_actions
                    SET status = ?, result_json = ?, last_error = ?, retry_count = retry_count + 1, updated_at = ?
                    WHERE action_id = ?
                    """,
                    (status, _json(result), error, _now(), action_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE orchestration_actions
                    SET status = ?, result_json = ?, last_error = ?, updated_at = ?
                    WHERE action_id = ?
                    """,
                    (status, _json(result), error, _now(), action_id),
                )

    def finalize_plan(self, plan_id: str, *, ok: bool, result: dict[str, Any], error: str | None = None) -> dict[str, Any]:
        status = "SUCCEEDED" if ok else "FAILED"
        with self._connect() as conn:
            conn.execute(
                "UPDATE orchestration_plans SET status = ?, result_json = ?, last_error = ?, updated_at = ? WHERE plan_id = ?",
                (status, _json(result), error, _now(), plan_id),
            )
        return self.get_plan(plan_id)


class HybridOrchestrationService:
    def __init__(self, store: HybridOrchestrationStore | None = None) -> None:
        self.store = store or HybridOrchestrationStore()

    async def plan(
        self,
        *,
        session_id: str,
        user_input: str,
        prefer_codex: bool,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        audit_id = self.store.write_audit(
            "plan_requested",
            {"prefer_codex": prefer_codex, "metadata_keys": sorted(metadata.keys())},
            session_id=session_id,
            status="DRAFT",
        )
        workflow = _detect_workflow(user_input)
        planner_mode = "codex"
        fallback_used = False
        fallback_reason: str | None = None
        if prefer_codex:
            actions, codex_ok, codex_reason = await _propose_actions_with_codex(user_input, workflow, metadata)
            if not codex_ok:
                planner_mode = "rule_fallback"
                fallback_used = True
                fallback_reason = codex_reason
                actions = _fallback_actions(user_input, workflow, metadata)
        else:
            planner_mode = "rule"
            actions = _fallback_actions(user_input, workflow, metadata)
        plan = self.store.create_plan(
            session_id=session_id,
            user_input=user_input,
            workflow=workflow,
            planner_mode=planner_mode,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            actions=actions,
        )
        self.store.write_audit(
            "plan_created",
            {"workflow": workflow, "planner_mode": planner_mode, "action_count": len(plan["actions"]), "request_audit_id": audit_id},
            session_id=session_id,
            plan_id=plan["plan_id"],
            status=plan["status"],
        )
        return {"ok": True, "audit_id": audit_id, "plan": plan}

    def confirm(
        self,
        *,
        session_id: str,
        plan_id: str,
        action_ids: list[str],
        confirmed_by: str,
        notes: str | None,
    ) -> dict[str, Any]:
        audit_id = self.store.write_audit(
            "confirm_requested",
            {"action_ids": action_ids, "confirmed_by": confirmed_by, "notes": notes},
            session_id=session_id,
            plan_id=plan_id,
            status="PENDING_CONFIRMATION",
        )
        plan = self.store.confirm_plan(plan_id, action_ids)
        self.store.write_audit(
            "plan_confirmed",
            {"selected_action_ids": plan["selected_action_ids"], "request_audit_id": audit_id},
            session_id=session_id,
            plan_id=plan_id,
            status=plan["status"],
        )
        return {"ok": True, "audit_id": audit_id, "plan": plan}

    async def execute(
        self,
        *,
        session_id: str,
        plan_id: str,
        idempotency_key: str | None,
        retry_failed_only: bool,
        dry_run: bool,
    ) -> dict[str, Any]:
        request_audit = self.store.write_audit(
            "execute_requested",
            {
                "idempotency_key": idempotency_key,
                "retry_failed_only": retry_failed_only,
                "dry_run": dry_run,
            },
            session_id=session_id,
            plan_id=plan_id,
            status="CONFIRMED",
        )
        plan = self.store.set_plan_execution_state(plan_id, idempotency_key)
        if plan["status"] == "SUCCEEDED" and idempotency_key and plan["idempotency_key"] == idempotency_key:
            return {"ok": True, "audit_id": request_audit, "plan": plan, "idempotent_hit": True}

        selected = set(plan["selected_action_ids"])
        action_results: list[dict[str, Any]] = []
        all_ok = True

        for action in plan["actions"]:
            action_id = action["action_id"]
            if action_id not in selected:
                continue
            if retry_failed_only and action["status"] not in {"FAILED", "CONFIRMED"}:
                continue
            if action["status"] == "SUCCEEDED":
                action_results.append({"action_id": action_id, "tool_name": action["tool_name"], "ok": True, "skipped": "already_succeeded"})
                continue
            if action["retry_count"] >= action["max_retries"] and action["status"] == "FAILED":
                all_ok = False
                action_results.append({"action_id": action_id, "tool_name": action["tool_name"], "ok": False, "error": "retry_limit_reached"})
                continue

            self.store.mark_action_running(action_id, idempotency_key)
            self.store.write_audit(
                "action_executing",
                {"tool_name": action["tool_name"], "payload_keys": sorted((action["payload"] or {}).keys())},
                session_id=session_id,
                plan_id=plan_id,
                action_id=action_id,
                status="EXECUTING",
            )
            try:
                if dry_run:
                    result = {
                        "ok": True,
                        "tool": action["tool_name"],
                        "summary": "Dry-run execution completed.",
                        "data": {"dry_run": True, "payload": action["payload"]},
                    }
                else:
                    result = await asyncio.wait_for(
                        toolbox_client.call_tool(
                            action["tool_name"],
                            action["payload"],
                            context={
                                "session_id": session_id,
                                "plan_id": plan_id,
                                "action_id": action_id,
                            },
                        ),
                        timeout=TOOL_EXECUTION_TIMEOUT_SECONDS,
                    )
                ok = bool(result.get("ok"))
                self.store.mark_action_result(
                    action_id,
                    ok=ok,
                    result=result if isinstance(result, dict) else {"raw": result},
                    error=None if ok else str(result.get("error") or "tool_call_failed"),
                    increment_retry=not ok,
                )
                self.store.write_audit(
                    "action_completed",
                    {"tool_name": action["tool_name"], "ok": ok, "request_audit_id": request_audit},
                    session_id=session_id,
                    plan_id=plan_id,
                    action_id=action_id,
                    status="SUCCEEDED" if ok else "FAILED",
                )
                action_results.append({"action_id": action_id, "tool_name": action["tool_name"], "ok": ok, "result": result})
                all_ok = all_ok and ok
            except Exception as exc:  # noqa: BLE001
                self.store.mark_action_result(
                    action_id,
                    ok=False,
                    result={"ok": False, "error": str(exc)},
                    error=str(exc),
                    increment_retry=True,
                )
                self.store.write_audit(
                    "action_failed",
                    {"tool_name": action["tool_name"], "error": str(exc), "request_audit_id": request_audit},
                    session_id=session_id,
                    plan_id=plan_id,
                    action_id=action_id,
                    status="FAILED",
                )
                action_results.append({"action_id": action_id, "tool_name": action["tool_name"], "ok": False, "error": str(exc)})
                all_ok = False

        final = self.store.finalize_plan(
            plan_id,
            ok=all_ok,
            result={"actions": action_results, "executed_count": len(action_results)},
            error=None if all_ok else "one_or_more_actions_failed",
        )
        self.store.write_audit(
            "plan_execution_finished",
            {"ok": all_ok, "executed_count": len(action_results), "request_audit_id": request_audit},
            session_id=session_id,
            plan_id=plan_id,
            status=final["status"],
        )
        return {"ok": all_ok, "audit_id": request_audit, "plan": final, "action_results": action_results}

    def audit_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        session_id: str | None = None,
        plan_id: str | None = None,
        action_id: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        audit_id = self.store.write_audit(
            event_type,
            payload,
            session_id=session_id,
            plan_id=plan_id,
            action_id=action_id,
            status=status,
        )
        return {"ok": True, "audit_id": audit_id}

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        return self.store.get_plan(plan_id)


def _detect_workflow(user_input: str) -> str:
    lowered = user_input.lower()
    if any(token in lowered for token in ["天气", "天文台", "brief", "risk", "新闻"]):
        return "daily_risk_briefing"
    if any(token in lowered for token in ["表格", "填表", "模板", "docx"]):
        return "smart_form_filling"
    return "hazard_intake"


async def _propose_actions_with_codex(
    user_input: str,
    workflow: str,
    metadata: dict[str, Any],
) -> tuple[list[dict[str, Any]], bool, str | None]:
    if not settings.llm_configured:
        return [], False, "LLM not configured. Downgraded to rule fallback."

    system_prompt = (
        "You are Codex planner for Chitung hybrid orchestration. "
        "Return strict JSON only with the shape: "
        "{\"proposed_actions\":[{\"tool_name\":\"...\",\"payload\":{},\"risk_level\":\"low|medium|high|critical\","
        "\"reason\":\"...\"}]}. "
        "Do not execute tools. Do not include shell/system commands."
    )
    user_payload = {
        "workflow": workflow,
        "user_input": user_input,
        "metadata": metadata,
        "allowed_tools_hint": [
            "fetch_hko_weather",
            "fetch_hk_safety_updates",
            "summarize_external_risks",
            "draft_daily_risk_briefing",
            "ingest_chat_hazards",
            "connect_hazard_actions",
            "search_form_templates",
            "prefill_form_fields",
            "generate_docx_from_template",
        ],
    }
    try:
        llm_result = await asyncio.wait_for(
            llm_gateway.complete_json(system_prompt=system_prompt, user_text=_json(user_payload)),
            timeout=PLANNER_TIMEOUT_SECONDS,
        )
        parsed = llm_result
        if "choices" in llm_result:
            choices = llm_result.get("choices") or []
            if choices and isinstance(choices[0], dict):
                message = choices[0].get("message") or {}
                content = message.get("content") if isinstance(message, dict) else ""
                if isinstance(content, str) and content.strip():
                    parsed = json.loads(content)
        actions_raw = parsed.get("proposed_actions", []) if isinstance(parsed, dict) else []
        actions = []
        for item in actions_raw:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool_name") or "").strip()
            if not tool_name:
                continue
            risk_level = str(item.get("risk_level") or "medium").lower()
            if risk_level not in RISK_LEVELS:
                risk_level = "medium"
            actions.append(
                {
                    "tool_name": tool_name,
                    "payload": item.get("payload") if isinstance(item.get("payload"), dict) else {},
                    "risk_level": risk_level,
                    "requires_confirmation": True,
                    "reason": item.get("reason") or "codex_proposed",
                }
            )
        actions = _filter_actions_by_workflow(actions, workflow)
        actions = actions[:MAX_ACTIONS_PER_PLAN]
        if not actions:
            return [], False, "Codex returned no valid proposed_actions."
        return actions, True, None
    except TimeoutError:
        return [], False, f"Codex planning timed out ({PLANNER_TIMEOUT_SECONDS}s)."
    except Exception as exc:  # noqa: BLE001
        return [], False, f"Codex planning failed: {exc}"


def _fallback_actions(user_input: str, workflow: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    if workflow == "daily_risk_briefing":
        return _filter_actions_by_workflow([
            {"tool_name": "fetch_hko_weather", "payload": {"lang": "tc"}, "risk_level": "medium", "requires_confirmation": True},
            {"tool_name": "fetch_hk_safety_updates", "payload": {"limit_per_source": 5}, "risk_level": "medium", "requires_confirmation": True},
            {
                "tool_name": "summarize_external_risks",
                "payload": {"weather_result": {"ok": True}, "safety_updates_result": {"ok": True}},
                "risk_level": "low",
                "requires_confirmation": True,
            },
            {
                "tool_name": "draft_daily_risk_briefing",
                "payload": {"weather_result": {"ok": True}, "safety_updates_result": {"ok": True}},
                "risk_level": "low",
                "requires_confirmation": True,
            },
        ], workflow)

    if workflow == "smart_form_filling":
        query = user_input[:120]
        return _filter_actions_by_workflow([
            {"tool_name": "search_form_templates", "payload": {"query": query, "limit": 5}, "risk_level": "low", "requires_confirmation": True},
            {
                "tool_name": "prefill_form_fields",
                "payload": {
                    "template_id": str(metadata.get("template_id") or "T006"),
                    "source_text": user_input,
                    "known_fields": metadata.get("known_fields") or {},
                },
                "risk_level": "medium",
                "requires_confirmation": True,
            },
            {
                "tool_name": "generate_docx_from_template",
                "payload": {
                    "template_id": str(metadata.get("template_id") or "T006"),
                    "fields": metadata.get("known_fields") or {},
                    "record": False,
                },
                "risk_level": "medium",
                "requires_confirmation": True,
            },
        ], workflow)

    return _filter_actions_by_workflow([
        {
            "tool_name": "ingest_chat_hazards",
            "payload": {"messages": [{"text": user_input, "chat_id": str(metadata.get("chat_id") or "local_chat"), "sender": str(metadata.get("user_id") or "local_user")}]},
            "risk_level": "medium",
            "requires_confirmation": True,
        },
        {"tool_name": "connect_hazard_actions", "payload": {"status": "open", "suggest_forms": True}, "risk_level": "low", "requires_confirmation": True},
    ], workflow)


def _filter_actions_by_workflow(actions: list[dict[str, Any]], workflow: str) -> list[dict[str, Any]]:
    allowed = WORKFLOW_ALLOWED_TOOLS.get(workflow, set())
    if not allowed:
        return actions
    filtered = [action for action in actions if str(action.get("tool_name") or "").strip() in allowed]
    return filtered


hybrid_orchestration_service = HybridOrchestrationService()
