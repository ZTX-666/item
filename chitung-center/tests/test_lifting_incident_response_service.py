from __future__ import annotations

from pathlib import Path

from chitung_center.lifting_incident_response_service import (
    _compose_notification_text,
    _fallback_alert_text,
    compose_patrol_detection_report,
    is_lifting_related_card,
    is_lifting_related_text,
    normalize_whatsapp_phone,
)


def test_is_lifting_related_text():
    assert is_lifting_related_text("地盘发生吊运事故")
    assert is_lifting_related_text("Crane lifting incident")
    assert not is_lifting_related_text("酷热天气预警")


def test_is_lifting_related_card():
    assert is_lifting_related_card({"title": "工地的吊运意外", "priority": "P1"})
    assert not is_lifting_related_card({"title": "暴雨黄色预警", "priority": "P1"})


def test_fallback_alert_text_includes_patrol_and_case():
    bundle = _fallback_alert_text(
        {"title": "吊运事故", "priority": "P1"},
        {"summary": {"text": "发现 2 个需复核目标。"}},
        42,
    )
    text = _compose_notification_text(
        {**bundle, "poster_api_url": "/api/assets/lifting-safety-alert-poster"},
        {"summary": {"text": "发现 2 个需复核目标。"}},
        42,
    )
    assert "吊运" in bundle["alert_body"]
    assert "#42" in text
    assert "机手" in text


def test_normalize_whatsapp_phone():
    assert normalize_whatsapp_phone("+852 8494 1215") == "+85284941215"
    assert normalize_whatsapp_phone("84941215") == "+85284941215"


def test_compose_patrol_detection_report_writes_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "chitung_center.lifting_incident_response_service.settings",
        type("S", (), {"chitung_data_dir": tmp_path, "lifting_alert_whatsapp_to": "+85284941215"})(),
    )
    report = compose_patrol_detection_report(
        external_card={"title": "吊运事故", "priority": "P1", "summary": "业界案例"},
        patrol={
            "report_id": "video-test-001",
            "refined_prompt": "检查吊运警戒区",
            "summary": {"text": "发现 2 个需复核目标。"},
            "cameras": [{"camera_name": "施工區域01", "summary": {"text": "人员靠近吊机。"}}],
        },
        alert_bundle={"alert_title": "警示", "alert_body": "立即自查", "operator_reminders": ["确认绑扎点"]},
        case_id=7,
        workflow_run_id="wf-test",
    )
    assert report["report_id"] == "video-test-001"
    assert Path(report["markdown_path"]).exists()
    assert "吊运专项视觉检测报告" in report["markdown_text"]
    assert "84941215" not in report["whatsapp_text"]  # phone not in report body
    assert "video-test-001" in report["whatsapp_text"]
