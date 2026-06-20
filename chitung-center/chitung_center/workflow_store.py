from __future__ import annotations

from typing import Any

from chitung_center.toolbox_client import toolbox_client


async def ensure_schema() -> dict[str, Any]:
    return await toolbox_client.call_tool("init_workflow_confirmation_schema", {"include_indexes": True})


async def create_run(
    *,
    workflow_name: str,
    title: str | None = None,
    trigger_source: str = "manual",
    trigger_payload: dict[str, Any] | None = None,
    channel: str = "local_web",
    user_id: str = "local_user",
    status: str = "planned",
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await toolbox_client.call_tool(
        "create_workflow_run",
        {
            "workflow_name": workflow_name,
            "title": title,
            "trigger_source": trigger_source,
            "trigger_payload": trigger_payload or {},
            "channel": channel,
            "user_id": user_id,
            "status": status,
            "idempotency_key": idempotency_key,
            "metadata": metadata or {},
        },
    )


async def append_step(
    *,
    workflow_run_id: str,
    step_name: str,
    agent_name: str | None = None,
    tool_name: str | None = None,
    input_payload: dict[str, Any] | None = None,
    output_payload: dict[str, Any] | None = None,
    status: str = "planned",
    error: str | None = None,
) -> dict[str, Any]:
    return await toolbox_client.call_tool(
        "append_workflow_step",
        {
            "workflow_run_id": workflow_run_id,
            "step_name": step_name,
            "agent_name": agent_name,
            "tool_name": tool_name,
            "input_payload": input_payload or {},
            "output_payload": output_payload or {},
            "status": status,
            "error": error,
        },
    )


async def update_step(
    *,
    workflow_step_id: str,
    status: str,
    output_payload: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return await toolbox_client.call_tool(
        "update_workflow_step",
        {
            "workflow_step_id": workflow_step_id,
            "status": status,
            "output_payload": output_payload or {},
            "error": error,
        },
    )


async def record_artifact(
    *,
    artifact_type: str,
    workflow_run_id: str | None = None,
    workflow_step_id: str | None = None,
    title: str | None = None,
    path: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await toolbox_client.call_tool(
        "record_workflow_artifact",
        {
            "workflow_run_id": workflow_run_id,
            "workflow_step_id": workflow_step_id,
            "artifact_type": artifact_type,
            "title": title,
            "path": path,
            "payload": payload or {},
        },
    )


async def link_event(
    *,
    workflow_run_id: str,
    event_type: str,
    source_type: str,
    source_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await toolbox_client.call_tool(
        "link_workflow_event",
        {
            "workflow_run_id": workflow_run_id,
            "event_type": event_type,
            "source_type": source_type,
            "source_id": source_id,
            "payload": payload or {},
        },
    )
