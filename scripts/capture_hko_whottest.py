"""One-shot capture of HKO weather warnings into risk_cards."""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent-toolbox"))
sys.path.insert(0, str(ROOT / "chitung-center"))

os.environ.setdefault("SAFETY_DATABASE_PATH", str(ROOT / "chitung-center" / "data" / "chitung_platform.db"))

from agent_toolbox.tools.external_risk import (  # noqa: E402
    ExternalRiskPersistRequest,
    HkoWeatherFetchRequest,
    _persist_cards,
    fetch_hko_weather,
    generate_risk_cards,
    persist_external_risk_items,
)
from chitung_center.external_monitor_store import create_run, finish_run, ingest_workflow_result  # noqa: E402


def main() -> None:
    weather = fetch_hko_weather(HkoWeatherFetchRequest(lang="tc"))
    if not weather.ok:
        raise SystemExit(f"HKO fetch failed: {weather.errors}")

    payload = weather.model_dump()
    cards = generate_risk_cards(weather_result=payload, safety_updates_result=None, items=[])
    persist_external_risk_items(ExternalRiskPersistRequest(weather_result=payload, source_batch="manual_capture"))
    saved = _persist_cards(cards)

    db_path = os.environ["SAFETY_DATABASE_PATH"]
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM risk_cards WHERE title LIKE '特别天气提示：{%'")

    run = create_run()
    result = {"ok": True, "workflow_run_id": "manual-whot-capture", "results": [payload, {"ok": True, "source": "draft_daily_risk_briefing", "cards": cards}]}
    summary = ingest_workflow_result(run["run_id"], result, lookback_hours=24)
    summary["card_count"] = len(cards)
    summary["source_count"] = 1
    summary["trigger"] = "manual_capture_whottest"
    finish_run(run["run_id"], status="success", workflow_run_id="manual-whot-capture", summary=summary)

    print(f"Captured {len(cards)} weather card(s); persisted={saved.get('persisted')} updated={saved.get('updated')}")
    for card in cards:
        print(f"- {card['title']}")
        if card.get("summary"):
            print(f"  {card['summary']}")


if __name__ == "__main__":
    main()
