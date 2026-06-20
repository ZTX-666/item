# Visual Patrol MVP Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify the first local Chitung MVP loop: visual/image detection draft, human confirmation, safety case creation, rectification notice draft, and persisted audit/ledger evidence.

**Architecture:** Keep the existing three-layer split. `chitung-center` owns workflow semantics and API responses; `agent-toolbox` owns detection, case creation, notice generation, and SQLite writes; the frontend/API caller remains a client.

**Tech Stack:** Python 3, FastAPI, Pydantic, pytest, httpx, SQLite, existing YOLO/VLM tooling under `vlm-detection`.

## Global Constraints

- Do not wire real WhatsApp or Feishu sending in this MVP.
- Do not implement scheduled patrols or before/after comparison in this MVP.
- Do not make the frontend call YOLO scripts or SQLite directly.
- Keep local image source support as the deterministic verification path; RTMP is optional for this milestone.
- Use TDD for behavior changes: write a failing test, verify it fails, then implement the minimal code.
- Preserve existing LFS model/weight files; do not commit regenerated binary assets.

---

## File Structure

- Modify `chitung-center/chitung_center/visual_patrol_service.py`: validate confirmation payloads, surface created `case_id`, preserve toolbox errors, and add audit evidence for confirmation.
- Modify `chitung-center/chitung_center/workflow_engine.py`: let chat/workflow visual patrol execute the local image flow when `metadata.source` or `metadata.image_path` exists.
- Modify `chitung-center/tests/test_visual_patrol_service.py`: add tests for source-image draft and confirmation error/success behavior.
- Create `chitung-center/tests/test_workflow_visual_mvp.py`: test chat/workflow visual source execution and no-source fallback.
- Create `chitung-center/scripts/smoke_visual_mvp_loop.py`: repeatable smoke script against running local services.
- Create local, uncommitted `.env` files only during execution if needed: `agent-toolbox/.env`, `chitung-center/.env`, and `chitung-frontend/.env`.

---

### Task 1: Harden Visual Confirmation and Surface Case IDs

**Files:**
- Modify: `chitung-center/chitung_center/visual_patrol_service.py`
- Test: `chitung-center/tests/test_visual_patrol_service.py`

**Interfaces:**
- Consumes: `VisualPatrolConfirmRequest` with `detections`, `task_id`, `image_path`, `area`, `contractor`, `description`.
- Produces: `confirm_visual_patrol_candidate(request) -> dict` containing `ok`, `message`, `case_id`, and `tool_result`.

- [ ] **Step 1: Write failing tests**

Add these tests to `chitung-center/tests/test_visual_patrol_service.py`:

```python
from chitung_center.visual_patrol_service import (
    build_visual_patrol_draft,
    confirm_visual_patrol_candidate,
)
from chitung_center.models import VisualPatrolConfirmRequest, VisualPatrolDraftRequest


@pytest.mark.asyncio
async def test_build_visual_patrol_draft_uses_local_source_without_snapshot():
    fake_vlm = {
        "ok": True,
        "task_id": "vlm-test-1",
        "data": {
            "detections": {
                "images": [
                    {
                        "image": "/tmp/site.jpg",
                        "detections": [
                            {
                                "class_name": "NO-Hardhat",
                                "confidence": 0.91,
                                "bbox_xyxy": [10, 20, 80, 120],
                            }
                        ],
                    }
                ]
            }
        },
    }

    with patch("chitung_center.visual_patrol_service.toolbox_client.call_tool", new_callable=AsyncMock) as call_tool:
        call_tool.return_value = fake_vlm
        result = await build_visual_patrol_draft(
            VisualPatrolDraftRequest(
                source="/tmp/site.jpg",
                area="B2",
                contractor="Demo Contractor",
                analysis_mode="yolo_only",
                vlm_enabled=False,
            )
        )

    assert result["ok"] is True
    assert result["snapshot"] is None
    assert result["source"] == "/tmp/site.jpg"
    assert result["candidates"]
    assert result["confirm_payload"]["detections"] == fake_vlm["data"]["detections"]
    assert result["confirm_payload"]["task_id"] == "vlm-test-1"
    call_tool.assert_awaited_once_with(
        "run_vlm_detection_batch",
        {"source": "/tmp/site.jpg", "conf": None, "worker_only": False, "machinery_only": False},
    )


@pytest.mark.asyncio
async def test_confirm_visual_patrol_candidate_rejects_empty_payload():
    result = await confirm_visual_patrol_candidate(VisualPatrolConfirmRequest())

    assert result["ok"] is False
    assert result["error"] == "missing_visual_evidence"
    assert "No visual detections" in result["message"]


@pytest.mark.asyncio
async def test_confirm_visual_patrol_candidate_returns_created_case_id():
    tool_result = {
        "ok": True,
        "data": {
            "case": {
                "data": {
                    "case_id": 42,
                    "case_key": "abc123",
                }
            }
        },
    }
    request = VisualPatrolConfirmRequest(
        detections={"images": [{"image": "/tmp/site.jpg", "detections": []}]},
        task_id="vlm-test-1",
        image_path="/tmp/site.jpg",
        area="B2",
        contractor="Demo Contractor",
        description="B2 visual safety candidate",
    )

    with patch("chitung_center.visual_patrol_service.toolbox_client.call_tool", new_callable=AsyncMock) as call_tool:
        call_tool.return_value = tool_result
        result = await confirm_visual_patrol_candidate(request)

    assert result["ok"] is True
    assert result["case_id"] == 42
    assert result["message"] == "Visual patrol candidate confirmed and converted to safety case."
    call_tool.assert_awaited_once_with(
        "create_case_from_vlm",
        {
            "detections": request.detections,
            "vlm_result_path": None,
            "task_id": "vlm-test-1",
            "image_path": "/tmp/site.jpg",
            "area": "B2",
            "contractor": "Demo Contractor",
            "description": "B2 visual safety candidate",
        },
    )
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd /Users/bytedance/Desktop/zhonghai_proj/item/chitung-center
python -m pytest tests/test_visual_patrol_service.py -q
```

Expected: at least the two confirmation tests fail because empty payloads are currently accepted and `case_id` is not surfaced.

- [ ] **Step 3: Implement minimal service changes**

In `chitung-center/chitung_center/visual_patrol_service.py`, update `confirm_visual_patrol_candidate` and add a helper:

```python
async def confirm_visual_patrol_candidate(request: VisualPatrolConfirmRequest) -> dict[str, Any]:
    """Confirm a visual patrol candidate and create a safety case."""
    if not _has_visual_evidence(request):
        return {
            "ok": False,
            "message": "No visual detections or evidence were provided for confirmation.",
            "error": "missing_visual_evidence",
            "tool_result": None,
        }

    result = await toolbox_client.call_tool(
        "create_case_from_vlm",
        {
            "detections": request.detections,
            "vlm_result_path": request.vlm_result_path,
            "task_id": request.task_id,
            "image_path": request.image_path,
            "area": request.area,
            "contractor": request.contractor,
            "description": request.description,
        },
    )
    case_id = _extract_created_case_id(result)
    audit_logger.write(
        "visual_candidate_confirmed",
        {
            "ok": bool(result.get("ok")),
            "case_id": case_id,
            "task_id": request.task_id,
            "image_path": request.image_path,
            "area": request.area,
        },
    )
    return {
        "ok": bool(result.get("ok")),
        "message": "Visual patrol candidate confirmed and converted to safety case.",
        "case_id": case_id,
        "tool_result": result,
    }


def _has_visual_evidence(request: VisualPatrolConfirmRequest) -> bool:
    return bool(request.detections or request.vlm_result_path or request.task_id or request.image_path)


def _extract_created_case_id(result: dict[str, Any]) -> int | None:
    data = result.get("data")
    if not isinstance(data, dict):
        return None
    case = data.get("case")
    if isinstance(case, dict):
        case_data = case.get("data")
        if isinstance(case_data, dict) and case_data.get("case_id") is not None:
            return int(case_data["case_id"])
        if case.get("case_id") is not None:
            return int(case["case_id"])
    if data.get("case_id") is not None:
        return int(data["case_id"])
    return None
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
cd /Users/bytedance/Desktop/zhonghai_proj/item/chitung-center
python -m pytest tests/test_visual_patrol_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/bytedance/Desktop/zhonghai_proj/item
git add chitung-center/chitung_center/visual_patrol_service.py chitung-center/tests/test_visual_patrol_service.py
git -c user.name='Codex' -c user.email='codex@local' commit -m "feat: harden visual patrol confirmation"
```

---

### Task 2: Execute Visual Patrol from Chat Workflow When Source Exists

**Files:**
- Modify: `chitung-center/chitung_center/workflow_engine.py`
- Create: `chitung-center/tests/test_workflow_visual_mvp.py`

**Interfaces:**
- Consumes: `ChatMessageRequest.metadata["source"]` or `ChatMessageRequest.metadata["image_path"]`.
- Produces: `WorkflowEngine._run_visual_patrol` that returns tool results and a `visual_patrol` card containing the draft when a source exists.

- [ ] **Step 1: Write failing tests**

Create `chitung-center/tests/test_workflow_visual_mvp.py`:

```python
from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.models import ChatMessageRequest
from chitung_center.workflow_engine import WorkflowEngine


@pytest.mark.asyncio
async def test_visual_workflow_runs_local_source_when_metadata_contains_source():
    draft = {
        "ok": True,
        "message": "Visual patrol draft generated.",
        "requires_confirmation": True,
        "source": "/tmp/site.jpg",
        "candidates": [{"id": "visual-vlm-test-1", "description": "No hardhat"}],
        "confirm_payload": {"task_id": "vlm-test-1", "image_path": "/tmp/site.jpg"},
    }
    request = ChatMessageRequest(
        message="识别这张照片",
        metadata={"source": "/tmp/site.jpg", "area": "B2", "contractor": "Demo Contractor"},
    )

    with patch("chitung_center.workflow_engine.build_visual_patrol_draft", new_callable=AsyncMock) as build_draft:
        build_draft.return_value = draft
        reply, tool_results, cards = await WorkflowEngine()._run_visual_patrol(request, "wf-1")

    assert "视觉巡检候选" in reply
    assert tool_results == [draft]
    assert len(cards) == 1
    assert cards[0].card_type == "visual_patrol"
    assert cards[0].data["draft"] == draft
    build_draft.assert_awaited_once()


@pytest.mark.asyncio
async def test_visual_workflow_keeps_page_card_without_source():
    request = ChatMessageRequest(message="检查摄像头")

    reply, tool_results, cards = await WorkflowEngine()._run_visual_patrol(request, "wf-1")

    assert "视觉巡检页面" in reply
    assert tool_results == []
    assert cards[0].actions[0]["id"] == "open_visual_patrol"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd /Users/bytedance/Desktop/zhonghai_proj/item/chitung-center
python -m pytest tests/test_workflow_visual_mvp.py -q
```

Expected: FAIL because `workflow_engine.py` does not import or call `build_visual_patrol_draft`.

- [ ] **Step 3: Implement minimal workflow changes**

In `chitung-center/chitung_center/workflow_engine.py`, import the needed request/service:

```python
from chitung_center.models import ActionCard, ChatMessageRequest, VisualPatrolDraftRequest
from chitung_center.visual_patrol_service import build_visual_patrol_draft
```

Then replace `_run_visual_patrol` with:

```python
    async def _run_visual_patrol(
        self,
        request: ChatMessageRequest,
        workflow_run_id: str,
    ) -> tuple[str, list[dict[str, Any]], list[ActionCard]]:
        source = request.metadata.get("source") or request.metadata.get("image_path")
        if source:
            draft = await build_visual_patrol_draft(
                VisualPatrolDraftRequest(
                    source=str(source),
                    area=request.metadata.get("area"),
                    contractor=request.metadata.get("contractor"),
                    conf=request.metadata.get("conf"),
                    analysis_mode=request.metadata.get("analysis_mode", "hybrid"),
                    vlm_enabled=bool(request.metadata.get("vlm_enabled", True)),
                    yolo_conf_threshold=float(request.metadata.get("yolo_conf_threshold", 0.45)),
                )
            )
            await workflow_store.link_event(
                workflow_run_id=workflow_run_id,
                event_type="visual_patrol_draft_created",
                source_type="image",
                source_id=str(source),
                payload={"ok": draft.get("ok"), "candidate_count": len(draft.get("candidates") or [])},
            )
            cards = [
                ActionCard(
                    card_type="visual_patrol",
                    title="视觉巡检候选",
                    summary=str(draft.get("message") or "已生成视觉巡检候选，等待人工确认。"),
                    actions=[{"id": "confirm_visual_candidate", "label": "确认入库"}],
                    data={"workflow_run_id": workflow_run_id, "draft": draft},
                )
            ]
            return "已基于本地图片生成视觉巡检候选，请人工确认后入库。", [draft], cards

        step = await _start_step(workflow_run_id, "patrol_draft", "赤瞳守护者", None)
        await workflow_store.update_step(
            workflow_step_id=step["workflow_step_id"],
            status="succeeded",
            output_payload={"hint": "Use /api/visual/patrol-draft from Visual Patrol page."},
        )
        cards = [
            ActionCard(
                card_type="visual_patrol",
                title="视觉巡检",
                summary="请前往「视觉巡检」页面配置 RTMP 后执行截图与检测；本工作流不在聊天内直接跑模型。",
                actions=[{"id": "open_visual_patrol", "label": "打开视觉巡检页"}],
                data={"workflow_run_id": workflow_run_id, "message": request.message},
            )
        ]
        return "已创建视觉巡检工作流，请到视觉巡检页面执行 RTMP/VLM 检测。", [], cards
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
cd /Users/bytedance/Desktop/zhonghai_proj/item/chitung-center
python -m pytest tests/test_workflow_visual_mvp.py tests/test_visual_patrol_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/bytedance/Desktop/zhonghai_proj/item
git add chitung-center/chitung_center/workflow_engine.py chitung-center/tests/test_workflow_visual_mvp.py
git -c user.name='Codex' -c user.email='codex@local' commit -m "feat: run visual workflow from local image source"
```

---

### Task 3: Add Repeatable Smoke Script for Running Services

**Files:**
- Create: `chitung-center/scripts/smoke_visual_mvp_loop.py`

**Interfaces:**
- Consumes: running `chitung-center` at `--center-url` and a local `--source` image path.
- Produces: CLI output with `candidate_count`, `case_id`, and rectification notice text preview; exits non-zero on failure.

- [ ] **Step 1: Write the smoke script**

Create `chitung-center/scripts/smoke_visual_mvp_loop.py`:

```python
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
```

- [ ] **Step 2: Run syntax check**

Run:

```bash
cd /Users/bytedance/Desktop/zhonghai_proj/item/chitung-center
python -m py_compile scripts/smoke_visual_mvp_loop.py
```

Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
cd /Users/bytedance/Desktop/zhonghai_proj/item
git add chitung-center/scripts/smoke_visual_mvp_loop.py
git -c user.name='Codex' -c user.email='codex@local' commit -m "test: add visual mvp smoke script"
```

---

### Task 4: Local Runtime Configuration and Verification

**Files:**
- Create locally, uncommitted if missing: `agent-toolbox/.env`
- Create locally, uncommitted if missing: `chitung-center/.env`
- Create locally, uncommitted if missing: `chitung-frontend/.env`

**Interfaces:**
- Consumes: current checkout path `/Users/bytedance/Desktop/zhonghai_proj/item`.
- Produces: services configured to use local paths and ports.

- [ ] **Step 1: Create local AgentToolbox env**

Create `agent-toolbox/.env` with:

```dotenv
AGENT_TOOLBOX_HOST=127.0.0.1
AGENT_TOOLBOX_PORT=8899
AGENT_TOOLBOX_ROOT=/Users/bytedance/Desktop/zhonghai_proj/item/agent-toolbox
AGENT_TOOLBOX_WORKSPACE=/Users/bytedance/Desktop/zhonghai_proj/item/agent-toolbox/workspace
VLM_DETECTION_DIR=/Users/bytedance/Desktop/zhonghai_proj/item/vlm-detection
VLM_PYTHON=python
RTMP_SNAPSHOT_SCRIPT=/Users/bytedance/Desktop/zhonghai_proj/item/rtmp-tools/rtmp_snapshot.py
RTMP_PYTHON=python
DEFAULT_RTMP_URL=
REPORT_SCRIPT=/Users/bytedance/Desktop/zhonghai_proj/item/report-generators/generate_community_doc.py
REPORT_PYTHON=python
WHATSAPP_ARCHIVE_BASE_URL=http://127.0.0.1:8787
FEISHU_WEBHOOK_URL=
FEISHU_WEBHOOK_SECRET=
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_VERIFICATION_TOKEN=
FEISHU_ENCRYPT_KEY=
FEISHU_API_BASE_URL=https://open.feishu.cn
SAFETY_POLICY_TEMPLATES_DIR=/Users/bytedance/Desktop/zhonghai_proj/item/safety-policy-templates-20241025
SAFETY_DATABASE_PATH=/Users/bytedance/Desktop/zhonghai_proj/item/agent-toolbox/workspace/safety_platform.db
YAOYAO_WORK_DIR=/Users/bytedance/Desktop/zhonghai_proj/item/agent-toolbox/workspace/yaoyao
YAOYAO_MODEL_DIR=/Users/bytedance/Desktop/zhonghai_proj/item/models/yaoyao/rapidocr
YAOYAO_PYTHON_BIN=
YAOYAO_WORKER_TIMEOUT=60
SECUREEYE_BASE_URL=https://api.openai.com/v1
SECUREEYE_API_KEY=
SECUREEYE_MODEL=gpt-4o
SECUREEYE_TIMEOUT_SECONDS=30
SECUREEYE_MAX_CONCURRENCY=4
YOLO_CONF_THRESHOLD=0.45
```

- [ ] **Step 2: Create local Chitung Center env**

Create `chitung-center/.env` with:

```dotenv
CHITUNG_CENTER_HOST=127.0.0.1
CHITUNG_CENTER_PORT=8999
AGENT_TOOLBOX_BASE_URL=http://127.0.0.1:8899
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
CHITUNG_DATA_DIR=/Users/bytedance/Desktop/zhonghai_proj/item/chitung-center/data
CHITUNG_SKILLS_DIR=/Users/bytedance/Desktop/zhonghai_proj/item/chitung-center/skills
CHITUNG_AUDIT_LOG=/Users/bytedance/Desktop/zhonghai_proj/item/chitung-center/data/audit.jsonl
ENABLE_FEISHU_ADAPTER=false
ENABLE_ZHT_ADAPTER=false
ENABLE_CHITONG_LINGXUN_ADAPTER=false
ENABLE_DOCMATE_ADAPTER=false
ENABLE_YAOYAO_HUIDU_ADAPTER=false
ENABLE_OPENCLAW_ADAPTER=false
```

- [ ] **Step 3: Create local frontend env**

Create `chitung-frontend/.env` with:

```dotenv
VITE_CHITUNG_CENTER_URL=http://127.0.0.1:8999
CHITUNG_CENTER_URL=http://127.0.0.1:8999
```

- [ ] **Step 4: Install/check Python dependencies**

Run:

```bash
cd /Users/bytedance/Desktop/zhonghai_proj/item/agent-toolbox
python -m pip install -r requirements.txt
cd /Users/bytedance/Desktop/zhonghai_proj/item/chitung-center
python -m pip install -r requirements.txt pytest
```

Expected: dependencies install or are already satisfied.

- [ ] **Step 5: Run unit tests**

Run:

```bash
cd /Users/bytedance/Desktop/zhonghai_proj/item/chitung-center
python -m pytest tests/test_visual_patrol_service.py tests/test_workflow_visual_mvp.py -q
```

Expected: PASS.

- [ ] **Step 6: Start local services**

In terminal 1:

```bash
cd /Users/bytedance/Desktop/zhonghai_proj/item/agent-toolbox
python run_server.py
```

In terminal 2:

```bash
cd /Users/bytedance/Desktop/zhonghai_proj/item/chitung-center
python run_server.py
```

Expected:

```text
agent-toolbox available at http://127.0.0.1:8899
chitung-center available at http://127.0.0.1:8999
```

- [ ] **Step 7: Run smoke script**

Use the bundled visual fixture image:

```bash
cd /Users/bytedance/Desktop/zhonghai_proj/item/chitung-center
python scripts/smoke_visual_mvp_loop.py --source /Users/bytedance/Desktop/zhonghai_proj/item/fixtures/visual-samples/snapshot_20260515_174839_351.jpg --area B2 --contractor "Demo Contractor"
```

Expected JSON:

```json
{
  "ok": true,
  "candidate_count": 1,
  "case_id": 1,
  "notice_preview": "整改通知草稿..."
}
```

- [ ] **Step 8: Commit tracked implementation files**

Do not commit `.env`, SQLite database files, task output folders, or binary model files. Commit only tracked source, tests, docs, and scripts:

```bash
cd /Users/bytedance/Desktop/zhonghai_proj/item
git status --short
git add chitung-center/chitung_center/visual_patrol_service.py \
  chitung-center/chitung_center/workflow_engine.py \
  chitung-center/tests/test_visual_patrol_service.py \
  chitung-center/tests/test_workflow_visual_mvp.py \
  chitung-center/scripts/smoke_visual_mvp_loop.py \
  docs/superpowers/plans/2026-06-20-visual-mvp-loop.md
git -c user.name='Codex' -c user.email='codex@local' commit -m "feat: complete visual mvp loop"
```
