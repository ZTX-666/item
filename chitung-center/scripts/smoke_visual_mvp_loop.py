from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx


def _post(client: httpx.Client, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(url, json=payload)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return data


def _extract_case_id(confirm_result: dict[str, Any]) -> int:
    case_id = confirm_result.get("case_id")
    if case_id is not None:
        return int(case_id)
    tool_result = confirm_result.get("tool_result")
    if isinstance(tool_result, dict):
        case = (tool_result.get("data") or {}).get("case")
        if isinstance(case, dict):
            case_data = case.get("data")
            if isinstance(case_data, dict) and case_data.get("case_id") is not None:
                return int(case_data["case_id"])
    raise RuntimeError(f"Could not extract case_id from confirmation result: {json.dumps(confirm_result, ensure_ascii=False)}")


def run(center_url: str, source: str, area: str, contractor: str) -> dict[str, Any]:
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"Source image does not exist: {source}")

    base = center_url.rstrip("/")
    with httpx.Client(timeout=180.0) as client:
        health = client.get(f"{base}/health")
        health.raise_for_status()

        draft = _post(
            client,
            f"{base}/api/visual/patrol-draft",
            {
                "source": str(source_path),
                "area": area,
                "contractor": contractor,
                "analysis_mode": "yolo_only",
                "vlm_enabled": False,
            },
        )
        candidates = draft.get("candidates") or []
        if not draft.get("ok") or not candidates:
            raise RuntimeError(f"Patrol draft did not produce candidates: {json.dumps(draft, ensure_ascii=False)[:2000]}")

        confirm = _post(client, f"{base}/api/visual/confirm-candidate", draft.get("confirm_payload") or {})
        if not confirm.get("ok"):
            raise RuntimeError(f"Candidate confirmation failed: {json.dumps(confirm, ensure_ascii=False)}")

        case_id = _extract_case_id(confirm)
        notice = _post(client, f"{base}/api/cases/rectification-notice", {"case_id": case_id})
        notice_text = ((notice.get("notice") or {}).get("draft_text") or "").strip()
        if not notice.get("ok") or not notice_text:
            raise RuntimeError(f"Notice draft failed: {json.dumps(notice, ensure_ascii=False)}")

        hazards = client.get(f"{base}/api/hazards", params={"limit": 20})
        hazards.raise_for_status()
        hazard_items = hazards.json().get("items") or []
        if not any(int(item.get("id", -1)) == case_id for item in hazard_items):
            raise RuntimeError(f"Created case {case_id} was not returned by /api/hazards")

        return {
            "ok": True,
            "candidate_count": len(candidates),
            "case_id": case_id,
            "notice_preview": notice_text[:300],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the Chitung visual MVP loop against running local services.")
    parser.add_argument("--center-url", default="http://127.0.0.1:8999")
    parser.add_argument("--source", required=True, help="Absolute or relative local image path.")
    parser.add_argument("--area", default="B2")
    parser.add_argument("--contractor", default="Demo Contractor")
    args = parser.parse_args()

    try:
        result = run(args.center_url, args.source, args.area, args.contractor)
    except Exception as exc:
        print(f"SMOKE FAIL: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
