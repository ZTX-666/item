# Visual Patrol MVP Loop Design

## Goal

Build the first end-to-end Chitung Safety Platform MVP loop on this local checkout:

```text
local image or RTMP snapshot
  -> YOLO/VLM visual patrol draft
  -> human confirmation
  -> safety case creation
  -> rectification notice draft
  -> SQLite/audit trace
```

The goal is not to finish every reserved workflow. The goal is to prove that the three-layer architecture works as a real local workflow: `chitung-frontend` or API caller talks to `chitung-center`, `chitung-center` calls `agent-toolbox`, and `agent-toolbox` executes detection/case/document tools and persists the result.

## Recommended Approach

Use the existing visual patrol path as the first real workflow and make it reliable with a local-image fallback. This is the lowest-risk route because the repository already has:

- `chitung-center` routes for patrol draft, confirmation, case workflow, and reports.
- `agent-toolbox` tools for `run_vlm_detection_batch`, `create_case_from_vlm`, `generate_rectification_notice`, and SQLite persistence.
- YOLO weights and OCR/VLM assets downloaded into the local checkout.

Alternatives considered:

- Smart form first: useful, but current DOCX output is mostly template-copy behavior, so the first milestone would become a document engine project.
- Chat hazard first: fastest to demo, but it proves less of the platform because classification is rule-based text matching.

## Scope

In scope:

- Configure both Python services for this local macOS checkout.
- Make the visual patrol path accept a local image source as a first-class input.
- Ensure candidate confirmation creates or reuses a safety case with enough fields for later workflow actions.
- Ensure the rectification notice endpoint produces a useful draft from the created case.
- Ensure SQLite records and audit events are created.
- Add tests for the service-level workflow behavior that does not require a live camera.
- Provide one repeatable local verification command or script for the full loop.

Out of scope for this first loop:

- Real WhatsApp sending.
- Real Feishu approval card delivery.
- Scheduled patrol service.
- Before/after image comparison.
- Full 24-workflow implementation.
- Perfect DOCX field filling.

## Architecture

The MVP keeps the current three-layer split.

`chitung-frontend` stays a client. It may call `POST /api/visual/patrol-draft`, `POST /api/visual/confirm-candidate`, and `POST /api/cases/rectification-notice`, but it must not call YOLO scripts or SQLite directly.

`chitung-center` owns workflow semantics. It resolves default project/camera settings, calls toolbox tools, returns reviewable candidates, and writes audit events. It should support both direct API calls and the Visual Patrol page.

`agent-toolbox` owns privileged execution. It runs detection, creates safety cases, generates rectification-notice text, and writes SQLite records.

## Data Flow

1. A user provides `source` as a local image path, or chooses a configured camera.
2. `chitung-center` calls `agent-toolbox.run_vlm_detection_batch`.
3. `agent-toolbox` runs `vlm-detection/detect.py` and returns structured detections.
4. `chitung-center` builds review candidates and a `confirm_payload`.
5. A user confirms one candidate through `POST /api/visual/confirm-candidate`.
6. `agent-toolbox.create_case_from_vlm` classifies the detection payload and creates a `safety_cases` row.
7. A user or API caller runs `POST /api/cases/rectification-notice` with the created `case_id`.
8. `agent-toolbox.generate_rectification_notice` returns a draft and `update_safety_case_status` records the notice-drafted status.
9. The workflow can be verified by querying `/api/hazards` and the local SQLite database.

## Error Handling

- If no RTMP URL is configured and no `source` is provided, `/api/visual/patrol-draft` returns a clear error and no case is created.
- If YOLO fails, the center response must preserve the toolbox error and not return a fake candidate.
- If candidate confirmation lacks detection data, confirmation should fail with a clear validation error instead of creating an empty case.
- If rectification notice generation receives a missing case ID, the endpoint should return a useful API error.
- If LLM/VLM enhancement is not configured, the MVP may fall back to YOLO-only detection and mark `analysis_mode` accordingly.

## Testing

Tests should focus on behavior that proves the local workflow:

- `build_visual_patrol_draft` uses a provided local image `source` and returns a candidate plus confirmation payload.
- `confirm_visual_patrol_candidate` calls `create_case_from_vlm` with the candidate data and returns the created case ID.
- `draft_rectification_notice` returns notice text and updates the case status.
- `WorkflowEngine._run_visual_patrol` should either run the local source workflow when metadata contains `source`, or continue to return the page-open card when no source exists.
- A smoke script should run the full loop against local services after dependencies are installed.

## Acceptance Criteria

The MVP is complete when all of these are true on this checkout:

- `agent-toolbox` starts on `127.0.0.1:8899`.
- `chitung-center` starts on `127.0.0.1:8999`.
- A local image source can be submitted to `/api/visual/patrol-draft`.
- The response contains at least one candidate when the detector returns detections.
- Confirming the candidate creates a `safety_cases` record.
- `/api/cases/rectification-notice` returns a non-empty draft for that case.
- `/api/hazards` shows the created case.
- Automated tests cover the source-image flow, confirmation flow, and notice-draft flow.
- Manual verification steps are documented in the implementation plan.
