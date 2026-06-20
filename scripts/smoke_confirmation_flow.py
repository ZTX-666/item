#!/usr/bin/env python3
"""Smoke test for workflow confirmation tools (direct toolbox HTTP)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

TOOLBOX_BASE = os.environ.get("AGENT_TOOLBOX_BASE_URL", "http://127.0.0.1:8899").rstrip("/")


def post_tool(tool_name: str, payload: dict) -> dict:
    url = f"{TOOLBOX_BASE}/tools/{tool_name}"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def assert_ok(result: dict, step: str) -> None:
    if not result.get("ok"):
        raise AssertionError(f"{step} failed: {json.dumps(result, ensure_ascii=False)}")


def main() -> int:
    print(f"[smoke] toolbox={TOOLBOX_BASE}")

    try:
        health_req = urllib.request.Request(f"{TOOLBOX_BASE}/health", method="GET")
        with urllib.request.urlopen(health_req, timeout=10) as response:
            health = json.loads(response.read().decode("utf-8"))
        print(f"[smoke] health ok={health.get('ok')}")
    except urllib.error.URLError as exc:
        print(f"[smoke] toolbox unreachable: {exc}")
        return 2

    init = post_tool("init_workflow_confirmation_schema", {"include_indexes": True})
    assert_ok(init, "init_workflow_confirmation_schema")
    print("[smoke] schema initialized")

    run = post_tool(
        "create_workflow_run",
        {
            "workflow_name": "smoke_confirmation_flow",
            "title": "Smoke Test Run",
            "trigger_source": "smoke_script",
            "channel": "local_web",
            "user_id": "smoke_user",
        },
    )
    assert_ok(run, "create_workflow_run")
    workflow_run_id = run["data"]["workflow_run"]["workflow_run_id"]
    print(f"[smoke] workflow_run_id={workflow_run_id}")

    step = post_tool(
        "append_workflow_step",
        {
            "workflow_run_id": workflow_run_id,
            "step_name": "create_confirmation",
            "agent_name": "chitung-center",
            "status": "running",
        },
    )
    assert_ok(step, "append_workflow_step")
    workflow_step_id = step["data"]["workflow_step"]["workflow_step_id"]
    print(f"[smoke] workflow_step_id={workflow_step_id}")

    pending = post_tool(
        "create_pending_confirmation",
        {
            "action_type": "draft_group_message",
            "title": "Smoke pending confirmation",
            "summary": "Created by scripts/smoke_confirmation_flow.py",
            "payload": {
                "recipients": ["smoke-chat"],
                "body": "Smoke test message body",
                "channel": "feishu",
            },
            "risk_level": "low",
            "source_channel": "smoke_script",
            "workflow_run_id": workflow_run_id,
            "workflow_step_id": workflow_step_id,
            "idempotency_key": f"smoke-{workflow_run_id}",
        },
    )
    assert_ok(pending, "create_pending_confirmation")
    confirmation_id = pending["data"]["confirmation"]["confirmation_id"]
    print(f"[smoke] confirmation_id={confirmation_id}")

    listed = post_tool(
        "query_pending_confirmations",
        {"status": "pending", "workflow_run_id": workflow_run_id, "limit": 10},
    )
    assert_ok(listed, "query_pending_confirmations")
    items = listed["data"]["items"]
    if not any(item.get("confirmation_id") == confirmation_id for item in items):
        raise AssertionError("created confirmation not found in query results")
    print(f"[smoke] listed pending count={len(items)}")

    approved = post_tool(
        "resolve_pending_confirmation",
        {
            "confirmation_id": confirmation_id,
            "decision": "approve",
            "decided_by": "smoke_user",
            "notes": "Smoke approve",
        },
    )
    assert_ok(approved, "resolve_pending_confirmation approve")
    print("[smoke] approved confirmation")

    executed = post_tool(
        "resolve_pending_confirmation",
        {
            "confirmation_id": confirmation_id,
            "decision": "mark_executed",
            "decided_by": "smoke_user",
            "notes": "Smoke mark executed",
            "result_payload": {"smoke": True},
        },
    )
    assert_ok(executed, "resolve_pending_confirmation mark_executed")
    print("[smoke] marked executed")

    artifact = post_tool(
        "record_workflow_artifact",
        {
            "workflow_run_id": workflow_run_id,
            "workflow_step_id": workflow_step_id,
            "artifact_type": "smoke_report",
            "title": "Smoke artifact",
            "payload": {"confirmation_id": confirmation_id},
        },
    )
    assert_ok(artifact, "record_workflow_artifact")
    print("[smoke] artifact recorded")

    linked = post_tool(
        "link_workflow_event",
        {
            "workflow_run_id": workflow_run_id,
            "event_type": "smoke_completed",
            "source_type": "script",
            "source_id": confirmation_id,
            "payload": {"ok": True},
        },
    )
    assert_ok(linked, "link_workflow_event")
    print("[smoke] event linked")

    print("[smoke] PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"[smoke] FAIL: {exc}")
        raise SystemExit(1) from exc
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"[smoke] HTTP {exc.code}: {body}")
        raise SystemExit(1) from exc
