from __future__ import annotations

import sqlite3

from chitung_center.external_briefing_store import list_external_briefing_reports, persist_external_briefing_report


def test_persist_external_briefing_report_writes_sqlite_and_lists_latest(tmp_path):
    db_path = tmp_path / "safety_platform.db"

    saved = persist_external_briefing_report(
        {
            "title": "今日外部风险简报",
            "briefing_text": "# 今日外部风险简报\n- 关注吊运安全",
            "summary": "已生成今日外部风险图文简报草稿。",
            "workflow_run_id": "run-1",
            "report_images": [{"title": "天气图", "url": "https://example.test/weather.png"}],
            "report_links": [{"title": "劳工处安全提示", "url": "https://example.test/a", "source": "劳工处"}],
            "tool_results": [{"tool": "draft_daily_risk_briefing", "ok": True}],
            "config": {"area": "香港项目", "focus": "施工安全"},
        },
        db_path=db_path,
    )

    assert saved["ok"] is True
    assert saved["report_id"] == 1

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT title, briefing_text FROM external_risk_briefing_reports").fetchone()

    assert row == ("今日外部风险简报", "# 今日外部风险简报\n- 关注吊运安全")

    listed = list_external_briefing_reports(db_path=db_path)

    assert listed["ok"] is True
    assert listed["items"][0]["report_id"] == 1
    assert listed["items"][0]["report_images"][0]["title"] == "天气图"
    assert listed["items"][0]["report_links"][0]["source"] == "劳工处"


def test_external_briefing_reports_api_exposes_persisted_list(monkeypatch):
    from fastapi.testclient import TestClient

    from chitung_center.app import app

    monkeypatch.setattr(
        "chitung_center.app.list_external_briefing_reports",
        lambda limit=20: {
            "ok": True,
            "items": [
                {
                    "report_id": 7,
                    "title": "今日外部风险简报",
                    "briefing_text": "关注吊运安全。",
                    "report_images": [],
                    "report_links": [],
                    "tool_results": [],
                    "created_at": "2026-06-21T12:00:00",
                    "updated_at": "2026-06-21T12:00:00",
                }
            ],
        },
    )

    response = TestClient(app).get("/api/external-risk/briefing-reports")

    assert response.status_code == 200
    assert response.json()["items"][0]["report_id"] == 7
