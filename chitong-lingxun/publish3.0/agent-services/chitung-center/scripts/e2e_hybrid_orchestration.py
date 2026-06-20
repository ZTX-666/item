from __future__ import annotations

import asyncio
import json
from uuid import uuid4
from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chitung_center.app import app


async def run_one(client: httpx.AsyncClient, *, session_id: str, user_input: str, dry_run: bool = True) -> tuple[bool, str]:
    plan_resp = await client.post(
        "/plan",
        json={
            "session_id": session_id,
            "user_input": user_input,
            "prefer_codex": True,
            "metadata": {"source": "e2e_script"},
        },
    )
    plan_resp.raise_for_status()
    plan_data = plan_resp.json()
    plan = plan_data["plan"]
    plan_id = plan["plan_id"]
    safe_input = user_input.encode("cp950", "replace").decode("cp950")
    print(f"[E2E] /plan -> input={safe_input} status={plan['status']} planner_mode={plan['planner_mode']} actions={len(plan['actions'])}")

    action_ids = [action["action_id"] for action in plan["actions"]]
    confirm_resp = await client.post(
        "/confirm",
        json={
            "session_id": session_id,
            "plan_id": plan_id,
            "action_ids": action_ids,
            "confirmed_by": "e2e_tester",
            "notes": "approve all actions",
        },
    )
    confirm_resp.raise_for_status()
    confirm_data = confirm_resp.json()
    print(f"[E2E] /confirm -> status={confirm_data['plan']['status']} selected={len(confirm_data['plan']['selected_action_ids'])}")

    idem_key = f"exec_{session_id}"
    execute_resp = await client.post(
        "/execute",
        json={
            "session_id": session_id,
            "plan_id": plan_id,
            "idempotency_key": idem_key,
            "retry_failed_only": True,
            "dry_run": dry_run,
        },
    )
    execute_resp.raise_for_status()
    execute_data = execute_resp.json()
    print(f"[E2E] /execute -> ok={execute_data['ok']} final_status={execute_data['plan']['status']} action_results={len(execute_data['action_results'])}")

    # 验证幂等：同 idempotency_key 再次执行不应重复跑
    idempotent_resp = await client.post(
        "/execute",
        json={
            "session_id": session_id,
            "plan_id": plan_id,
            "idempotency_key": idem_key,
            "retry_failed_only": True,
            "dry_run": dry_run,
        },
    )
    idempotent_resp.raise_for_status()
    idempotent_data = idempotent_resp.json()
    print(f"[E2E] /execute(idempotent) -> idempotent_hit={idempotent_data.get('idempotent_hit', False)}")

    final_plan_resp = await client.get(f"/plan/{plan_id}")
    final_plan_resp.raise_for_status()
    final_plan = final_plan_resp.json()["plan"]
    print("[E2E] final_plan_snapshot=" + json.dumps(
        {
            "plan_id": final_plan["plan_id"],
            "status": final_plan["status"],
            "workflow": final_plan["workflow"],
            "planner_mode": final_plan["planner_mode"],
            "fallback_used": final_plan["fallback_used"],
        },
        ensure_ascii=False,
    ))
    return final_plan["status"] == "SUCCEEDED", plan_id


async def main() -> int:
    transport = httpx.ASGITransport(app=app)
    session_id = f"e2e_{uuid4().hex[:8]}"
    print(f"[E2E] base_session_id={session_id}")

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        workflows = [
            ("daily_risk", "请生成今天的天气和外部风险简报"),
            ("hazard_intake", "B2 区临边护栏缺失，请生成整改动作建议"),
            ("smart_form", "请帮我生成 T006 表格草稿并预填内容"),
        ]
        all_ok = True
        created_plan_ids: list[str] = []
        for suffix, user_input in workflows:
            ok, plan_id = await run_one(client, session_id=f"{session_id}_{suffix}", user_input=user_input, dry_run=True)
            all_ok = all_ok and ok
            created_plan_ids.append(plan_id)

        audit_resp = await client.post(
            "/audit/event",
            json={
                "event_type": "e2e_completed",
                "session_id": session_id,
                "status": "SUCCEEDED" if all_ok else "FAILED",
                "payload": {"plans": created_plan_ids, "workflow_count": len(workflows)},
            },
        )
        audit_resp.raise_for_status()
        audit_data = audit_resp.json()
        print(f"[E2E] /audit/event -> audit_id={audit_data['audit_id']} overall_ok={all_ok}")
        if not all_ok:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
