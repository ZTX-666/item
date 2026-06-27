from __future__ import annotations

from chitung_center.coach_usage_service import build_automation_usage_snapshot, build_skill_usage_snapshot, build_workflow_usage_snapshot
from chitung_center.intent_router import route_intent
from chitung_center.orchestrator import _match_usage_coach_request
from chitung_center.skills import skill_loader


def test_three_usage_coach_skills_registered() -> None:
    for name in ("skill-usage-coach", "workflow-usage-coach", "automation-usage-coach"):
        info = skill_loader.get_info(name)
        assert info is not None
        assert info.tools == []
        config = skill_loader.read_config(name) or {}
        assert config.get("mode") == "conversation_only"
        assert config.get("can_execute_tools") is False


def test_usage_snapshots_build() -> None:
    skill = build_skill_usage_snapshot()
    workflow = build_workflow_usage_snapshot()
    automation = build_automation_usage_snapshot()
    assert skill["domain"] == "skill"
    assert workflow["domain"] == "workflow"
    assert automation["domain"] == "automation"
    assert "totals" in skill
    assert "templates" in workflow


def test_intent_routing_for_coaches() -> None:
    assert route_intent("Skill 使用教练，制度问答怎么用").intent == "skill_usage_coach"
    assert route_intent("工作流使用教练，帮我看最近跑过哪些流程").intent == "workflow_usage_coach"
    assert route_intent("自动化怎么配定时任务").intent == "automation_usage_coach"


def test_coach_request_detection() -> None:
    assert _match_usage_coach_request("Skill 使用教练") == "skill_usage_coach"
    assert _match_usage_coach_request("工作流使用教练") == "workflow_usage_coach"
    assert _match_usage_coach_request("自动化使用教练") == "automation_usage_coach"
