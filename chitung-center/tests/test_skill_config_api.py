from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))


def test_skill_detail_returns_sidecar_config(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from chitung_center.app import app
    from chitung_center.skills import SkillLoader

    skill_dir = tmp_path / "daily-risk-briefing"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Daily Risk Briefing\n\n生成每日安全风险简报。", encoding="utf-8")
    (skill_dir / "config.json").write_text(
        json.dumps({"sources": [{"id": "hko_weather", "enabled": True}], "keyword_groups": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr("chitung_center.app.skill_loader", SkillLoader(tmp_path))

    response = TestClient(app).get("/api/skills/daily-risk-briefing")

    assert response.status_code == 200
    data = response.json()
    assert data["config"]["sources"][0]["id"] == "hko_weather"


def test_skill_config_api_updates_sidecar_config(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from chitung_center.app import app
    from chitung_center.skills import SkillLoader

    skill_dir = tmp_path / "daily-risk-briefing"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Daily Risk Briefing\n\n生成每日安全风险简报。", encoding="utf-8")
    monkeypatch.setattr("chitung_center.app.skill_loader", SkillLoader(tmp_path))

    payload = {"config": {"sources": [{"id": "gov_press_rss", "enabled": False}], "keyword_groups": []}}
    response = TestClient(app).put("/api/skills/daily-risk-briefing/config", json=payload)

    assert response.status_code == 200
    assert response.json()["config"]["sources"][0]["id"] == "gov_press_rss"
    saved = json.loads((skill_dir / "config.json").read_text(encoding="utf-8"))
    assert saved["sources"][0]["enabled"] is False
