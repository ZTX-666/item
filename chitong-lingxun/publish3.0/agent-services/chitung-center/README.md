# Chitung Center

`chitung-center` is the lightweight agent base for the Chitong Safety Platform.

It is intentionally separate from `AgentToolbox`:

- **Chitung Center** understands user intent, loads skills, calls the cloud LLM, builds cards, and orchestrates tasks.
- **AgentToolbox** executes local tools such as VLM, OCR, WhatsApp search/send, DOCX generation, and SQLite writes.

## First MVP Target

One closed loop plus three demo highlights:

1. Chat hazard input -> AI classification -> safety case -> notification draft -> human confirmation.
2. CCTV/RTMP snapshot -> VLM detection -> visual hazard candidate.
3. Template search -> form prefill -> Word generation.
4. Weather/news risk -> daily safety briefing.

## Run

```powershell
cd "J:\China Oversea  Final\FinalAgentSuite\chitung-center"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python run_server.py
```

Default endpoint:

```text
http://127.0.0.1:8999
```

## Key Endpoints

```text
GET  /health
GET  /api/skills
POST /api/chat/message
POST /api/chat/card-action
GET  /api/integrations
GET  /api/workbench/summary
GET  /api/settings/llm
POST /api/settings/llm
POST /api/documents/revision-preview
POST /api/forms/smart-draft
POST /api/forms/accept-draft
POST /api/hazards/{case_id}/status
POST /api/visual/patrol-draft
POST /api/visual/confirm-candidate
POST /api/cases/rectification-notice
POST /api/cases/contractor-confirm
POST /api/cases/close-review
```

## LLM Settings

- `GET /api/settings/llm` returns masked local LLM configuration status.
- `POST /api/settings/llm` writes `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` to the local `.env`, then updates the running settings object.
- The desktop app uses these endpoints so operators do not need to manually edit `.env` during normal setup.

## Document And Form Flow

- `/api/documents/revision-preview` calls the shared LLM Gateway when `revised_text` is not provided, then returns DocMate-style diff lines with `+N` / `-N` counts. If the LLM is not configured or fails, it returns a deterministic fallback draft.
- `/api/forms/smart-draft` searches templates, pre-fills fields, generates a DOCX draft with `record=false`, and returns a diff preview. This stage does not write a final form record.
- `/api/forms/accept-draft` writes the accepted payload to `form_records`. The desktop UI should call this only after a human accepts the diff.

## Visual Patrol Flow

- `/api/visual/patrol-draft` runs RTMP snapshot capture when no source is provided, runs VLM detection, and returns a visual hazard candidate. It does not create a case.
- `/api/visual/confirm-candidate` converts the confirmed visual candidate to a safety case through AgentToolbox.

## Case Closure Flow

- `/api/cases/rectification-notice` drafts a rectification notice and marks the case as notice drafted.
- `/api/cases/contractor-confirm` records contractor assignment/confirmation and marks the case accordingly.
- `/api/cases/close-review` closes the case after human review and optional evidence paths.

## Extension Policy

Only `SKILL.md` files may be added dynamically. Skills are instructions and tool orchestration hints only. They cannot execute scripts, access the filesystem, call the network, or send messages directly.

All privileged actions must go through built-in tools in AgentToolbox and be audited.
