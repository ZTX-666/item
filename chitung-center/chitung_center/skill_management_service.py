from __future__ import annotations

from typing import Any

from chitung_center.job_service import create_job, job_stats, list_jobs, mark_finished, mark_running
from chitung_center.skills import skill_loader
from chitung_center.toolbox_client import toolbox_client


def source_module_for_skill(name: str) -> str:
    mapping = {
        "external-info-monitor": "external_info_skill",
        "daily-risk-briefing": "external_info",
        "whatsapp-sql-query": "whatsapp",
        "whatsapp-wacli-ops": "whatsapp",
        "visual-patrol": "visual_patrol",
        "shanshan-doc": "docmate",
        "docmate-edit": "docmate",
        "knowledge-query": "rag",
        "long-term-memory": "long_term_memory",
    }
    return mapping.get(name, f"skill:{name}")


async def skill_operational_view(name: str) -> dict[str, Any]:
    info = skill_loader.get_info(name)
    if not info:
        return {"ok": False, "error": f"Skill not found: {name}"}
    config = skill_loader.read_config(name) or {}
    dependencies = await _dependency_status(info.tools)
    recent_runs = list_jobs(source_module=source_module_for_skill(name), limit=8).get("items", [])
    return {
        "ok": True,
        "name": name,
        "config": config,
        "dependencies": dependencies,
        "recent_runs": recent_runs,
        "stats": job_stats(),
    }


async def test_skill(name: str) -> dict[str, Any]:
    info = skill_loader.get_info(name)
    if not info:
        return {"ok": False, "error": f"Skill not found: {name}"}
    job = create_job(
        job_type="skill_test",
        title=f"测试 Skill：{name}",
        source_module=source_module_for_skill(name),
        request={"skill": name, "tools": info.tools},
    )
    job_id = str(job["job_id"])
    mark_running(job_id)
    dependencies = await _dependency_status(info.tools)
    ok = all(item.get("available", False) is not False for item in dependencies)
    result = {
        "ok": ok,
        "skill": name,
        "dependencies": dependencies,
        "message": "Skill 依赖检查完成。" if ok else "Skill 存在不可用依赖，请查看详情。",
    }
    mark_finished(job_id, result=result)
    return {"ok": ok, "job_id": job_id, "result": result}


async def _dependency_status(tools: list[str]) -> list[dict[str, Any]]:
    if not tools:
        return []
    health = await toolbox_client.health()
    checks = health.get("tools", {}) if isinstance(health.get("tools"), dict) else {}
    result: list[dict[str, Any]] = []
    for tool in tools:
        data = checks.get(tool)
        if isinstance(data, dict):
            result.append({"name": tool, **data})
        else:
            result.append({"name": tool, "available": None, "note": "未在健康检查中声明，可能是中台内部能力。"})
    return result
