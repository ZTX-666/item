from __future__ import annotations

import json

from agent_toolbox.tools.external_risk import ExternalRiskFetchRequest, fetch_hk_safety_updates


def test_fetch_safety_updates_uses_daily_risk_skill_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "sources": [
                    {"id": "labour_department", "enabled": True},
                    {"id": "hk01", "enabled": False},
                ],
                "keyword_groups": [
                    {"include": ["吊運", "天秤"], "exclude": []},
                    {"include": ["酷熱"], "exclude": []},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    calls: list[tuple[str, list[str], list[str]]] = []

    def fake_fetch_source_items(source, source_config, req, seen_urls, errors):
        calls.append((source, list(req.sources), list(req.keywords)))
        return []

    monkeypatch.setattr("agent_toolbox.tools.external_risk._skill_config_path", lambda: config_path)
    monkeypatch.setattr("agent_toolbox.tools.external_risk._fetch_source_items", fake_fetch_source_items)

    fetch_hk_safety_updates(ExternalRiskFetchRequest())

    assert calls == [("labour_department", ["labour_department"], ["吊運", "天秤", "酷熱"])]


def test_fetch_safety_updates_parses_government_press_rss(monkeypatch):
    class FakeResponse:
        url = "https://www.info.gov.hk/gia/rss/general_zh.xml"
        encoding = "utf-8"
        apparent_encoding = "utf-8"
        text = """<?xml version="1.0" encoding="utf-8"?>
        <rss><channel><item>
          <title>劳工处高度关注一宗地盘吊運工業意外</title>
          <link>https://www.info.gov.hk/gia/general/202606/21/P202606210001.htm</link>
          <description>涉及建造业职安风险。</description>
          <pubDate>Sun, 21 Jun 2026 08:00:00 +0800</pubDate>
        </item></channel></rss>"""

        def raise_for_status(self):
            return None

    monkeypatch.setattr("agent_toolbox.tools.external_risk._read_skill_config", lambda: {})
    monkeypatch.setattr("agent_toolbox.tools.external_risk.requests.get", lambda *args, **kwargs: FakeResponse())

    result = fetch_hk_safety_updates(
        ExternalRiskFetchRequest(sources=["gov_press_rss"], keywords=["地盘", "吊運", "工業意外"], limit_per_source=5)
    )

    assert result.ok is True
    assert result.items[0]["source"] == "gov_press_rss"
    assert result.items[0]["title"] == "劳工处高度关注一宗地盘吊運工業意外"
    assert result.items[0]["url"].endswith("P202606210001.htm")
