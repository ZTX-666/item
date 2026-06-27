from __future__ import annotations

import json
from collections import Counter
from typing import Any

from chitung_center.config import settings
from chitung_center.job_service import job_stats, list_jobs
from chitung_center.skill_management_service import source_module_for_skill
from chitung_center.skills import skill_loader
from chitung_center.workflow_templates import WORKFLOW_TEMPLATES, list_workflow_templates


def build_skill_usage_snapshot() -> dict[str, Any]:
    skills = skill_loader.list_skills()
    jobs = list_jobs(limit=200).get("items") or []
    stats = job_stats()

    module_to_skill: dict[str, str] = {}
    for skill in skills:
        module_to_skill[source_module_for_skill(skill.name)] = skill.name

    skill_job_counts: Counter[str] = Counter()
    skill_recent: dict[str, list[dict[str, Any]]] = {skill.name: [] for skill in skills}
    for job in jobs:
        if not isinstance(job, dict):
            continue
        module = str(job.get("source_module") or "")
        skill_name = module_to_skill.get(module)
        if not skill_name and module.startswith("skill:"):
            skill_name = module.split(":", 1)[1]
        if not skill_name:
            req = job.get("request") if isinstance(job.get("request"), dict) else {}
            if str(job.get("job_type") or "") == "skill_test":
                skill_name = str(req.get("skill") or "")
        if not skill_name:
            continue
        skill_job_counts[skill_name] += 1
        bucket = skill_recent.setdefault(skill_name, [])
        if len(bucket) < 5:
            bucket.append(_compact_job(job))

    skill_rows = []
    for skill in skills:
        skill_rows.append(
            {
                "name": skill.name,
                "display_name": skill.display_name,
                "enabled": skill.enabled,
                "intents": skill.intents,
                "tools_count": len(skill.tools),
                "tools": skill.tools[:8],
                "triggers": skill.triggers[:6],
                "run_count": skill_job_counts.get(skill.name, 0),
                "recent_runs": skill_recent.get(skill.name, []),
            }
        )
    skill_rows.sort(key=lambda row: (row["run_count"], row["enabled"]), reverse=True)

    audit_skill_hits = _audit_event_counts(["skill_applied", "skill_enhance_failed"], limit=400)

    return {
        "domain": "skill",
        "totals": {
            "skill_count": len(skills),
            "enabled_skill_count": sum(1 for skill in skills if skill.enabled),
            "skill_test_jobs": sum(1 for job in jobs if str(job.get("job_type") or "") == "skill_test"),
            "job_total": stats.get("total", 0),
        },
        "skills": skill_rows,
        "most_used_skills": [row for row in skill_rows if row["run_count"] > 0][:5],
        "never_run_skills": [row["display_name"] for row in skill_rows if row["run_count"] == 0][:8],
        "audit_skill_events": audit_skill_hits,
    }


def build_workflow_usage_snapshot() -> dict[str, Any]:
    jobs = list_jobs(limit=300).get("items") or []
    templates = list_workflow_templates()
    workflow_jobs = [job for job in jobs if str(job.get("job_type") or "") == "agent_workflow"]

    by_workflow: Counter[str] = Counter()
    by_status: Counter[str] = Counter()
    by_intent: Counter[str] = Counter()
    recent: list[dict[str, Any]] = []

    for job in workflow_jobs:
        if not isinstance(job, dict):
            continue
        req = job.get("request") if isinstance(job.get("request"), dict) else {}
        workflow_name = str(req.get("workflow_name") or "unknown")
        intent = str(req.get("intent") or "unknown")
        status = str(job.get("status") or "unknown")
        by_workflow[workflow_name] += 1
        by_intent[intent] += 1
        by_status[status] += 1
        if len(recent) < 8:
            recent.append(
                {
                    "title": job.get("title"),
                    "workflow_name": workflow_name,
                    "intent": intent,
                    "status": status,
                    "error": job.get("error"),
                    "created_at": job.get("created_at"),
                }
            )

    template_usage = []
    for item in templates:
        name = str(item.get("workflow_name") or "")
        template_usage.append({**item, "run_count": by_workflow.get(name, 0)})
    template_usage.sort(key=lambda row: row["run_count"], reverse=True)

    return {
        "domain": "workflow",
        "totals": {
            "workflow_template_count": len(templates),
            "agent_workflow_jobs": len(workflow_jobs),
            "success_jobs": by_status.get("success", 0),
            "failed_jobs": by_status.get("failed", 0),
            "running_jobs": by_status.get("running", 0),
        },
        "by_workflow": dict(by_workflow.most_common(12)),
        "by_intent": dict(by_intent.most_common(12)),
        "templates": template_usage,
        "recent_runs": recent,
        "unused_templates": [
            item["title"]
            for item in template_usage
            if item["run_count"] == 0 and not str(item.get("workflow_name") or "").startswith("workflow_daily_safety")
        ][:6],
    }


def build_automation_usage_snapshot() -> dict[str, Any]:
    jobs = list_jobs(limit=300).get("items") or []
    automation_templates = [
        {
            "workflow_name": item.workflow_name,
            "title": item.title,
            "description": item.description,
            "intent": item.intent,
            "step_count": len(item.steps),
            "confirmation_steps": sum(1 for step in item.steps if step.requires_confirmation),
        }
        for item in WORKFLOW_TEMPLATES.values()
        if str(item.intent).startswith("automation_") or "auto" in item.workflow_name
    ]

    automation_jobs: list[dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        req = job.get("request") if isinstance(job.get("request"), dict) else {}
        workflow_name = str(req.get("workflow_name") or "")
        intent = str(req.get("intent") or "")
        title = str(job.get("title") or "")
        source = str(job.get("source_module") or "")
        if (
            intent.startswith("automation_")
            or "automation" in workflow_name
            or "自动化" in title
            or source == "automation_scheduler"
        ):
            automation_jobs.append(job)

    by_workflow: Counter[str] = Counter()
    by_status: Counter[str] = Counter()
    recent: list[dict[str, Any]] = []
    for job in automation_jobs:
        req = job.get("request") if isinstance(job.get("request"), dict) else {}
        workflow_name = str(req.get("workflow_name") or "unknown")
        by_workflow[workflow_name] += 1
        by_status[str(job.get("status") or "unknown")] += 1
        if len(recent) < 8:
            recent.append(_compact_job(job))

    return {
        "domain": "automation",
        "totals": {
            "automation_template_count": len(automation_templates),
            "backend_automation_jobs": len(automation_jobs),
            "success_jobs": by_status.get("success", 0),
            "failed_jobs": by_status.get("failed", 0),
        },
        "templates": automation_templates,
        "by_workflow": dict(by_workflow.most_common(10)),
        "recent_runs": recent,
        "frontend_storage_note": (
            "Automation 页任务保存在浏览器 localStorage：chitung.automation.tasks.v2 / "
            "chitung.automation.runs.v2。教练结合后端 job 记录 + 页面操作指引。"
        ),
    }


def build_usage_snapshot(domain: str) -> dict[str, Any]:
    if domain == "skill":
        return build_skill_usage_snapshot()
    if domain == "workflow":
        return build_workflow_usage_snapshot()
    if domain == "automation":
        return build_automation_usage_snapshot()
    raise ValueError(f"unsupported coach domain: {domain}")


def _compact_job(job: dict[str, Any]) -> dict[str, Any]:
    req = job.get("request") if isinstance(job.get("request"), dict) else {}
    return {
        "job_id": job.get("job_id"),
        "title": job.get("title"),
        "status": job.get("status"),
        "job_type": job.get("job_type"),
        "source_module": job.get("source_module"),
        "workflow_name": req.get("workflow_name"),
        "intent": req.get("intent"),
        "error": job.get("error"),
        "created_at": job.get("created_at"),
    }


def _audit_event_counts(event_types: list[str], *, limit: int = 300) -> dict[str, int]:
    path = settings.chitung_audit_log
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return {}
    counts: Counter[str] = Counter()
    for line in lines[-limit:]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = str(event.get("event_type") or "")
        if event_type in event_types:
            counts[event_type] += 1
    return dict(counts)
