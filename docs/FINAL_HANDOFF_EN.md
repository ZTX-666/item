# Chitung Safety Intelligence Platform — Final Developer Handoff (English)

> **Repository:** https://github.com/ZTX-666/item  
> **Updated:** 2026-06-20  
> **Audience:** Full-stack engineers joining to finish integration, review, and MVP delivery  
> **Read this first.** Chinese docs with more product detail live under `docs/product/`.

---

## 1. What You Are Building

**Chitung Safety Intelligence Platform** is a **local-first AI workbench** for Hong Kong construction-site safety officers. It is **not** a single chatbot or a single vision tool. It connects:

- CCTV / RTMP video and VLM inspection  
- Feishu / WhatsApp messaging  
- Safety policy templates (159 forms)  
- Hazard cases, rectification, and audit trails  
- OCR / structured document input (Yaoyao Huidu)  
- Word report generation (DocMate / Shanshan)  
- External risk radar (weather, news, government alerts)

### Core principles (non‑negotiable)

1. **Local data stays local** — chat, images, DB, templates, audit logs.  
2. **Cloud is inference only** — LLM gets minimal, sanitized context.  
3. **Human confirmation required** — outbound messages, case closure, formal reports, ledger changes.  
4. **Frontend talks only to `chitung-center`** — never directly to toolbox, scripts, SQLite, or LLM APIs.

### Product modules (4+1 agents)

| Module | Role |
| --- | --- |
| **Chitung Center** | NL entry, intent routing, workflow orchestration, LLM gateway |
| **Chitung Guardian** | Visual patrol, hazard detection, rectification loop |
| **Chitung Lingxun** | WhatsApp / messaging archive and drafts |
| **Shanshan Docs (DocMate)** | Word editing and report generation |
| **Yaoyao Huidu** | OCR and structured field extraction |
| **AgentToolbox** | Unified HTTP/MCP tool layer (129+ tools) |

---

## 2. Repository Map

```
item/
├── chitung-frontend/          # Electron + Vue 3 desktop UI (port 5173)
├── chitung-center/            # FastAPI orchestration API (port 8999)
├── agent-toolbox/             # FastAPI tool gateway (port 8899)
├── rtmp-tools/                # RTMP snapshot utility
├── vlm-detection/             # Dual YOLO detection scripts
│   └── weights/               # YOLO .pt weights (Git LFS)
├── models/yaoyao/rapidocr/    # RapidOCR ONNX models (Git LFS)
├── scripts/nightly_patrol.py  # Standalone 11-camera patrol script
├── chitong-lingxun/           # WhatsApp desktop client (WPF)
├── docmate-shanshan/          # DocMate / Shanshan document editor
├── whatsapp-archive/          # WhatsApp archive backend + web UI
├── safety-policy-templates-20241025/  # 159 safety form templates
├── frontend-ui-prototype/     # UI mockups and interaction specs
├── external/                  # Vendored reference code (PaddleOCR, depth-VLM, etc.)
├── open-source-references/    # OSS reference implementations
├── fixtures/visual-samples/   # Site test images for RTMP fallback
└── docs/
    ├── FINAL_HANDOFF_EN.md    # ← this file
    ├── COLLABORATION_HANDOFF.md
    ├── UPLOAD_MANIFEST.md
    └── product/               # Detailed Chinese product & tech docs
```

### Git LFS (required after clone)

Large assets are in **Git LFS**:

```powershell
git lfs install
git clone https://github.com/ZTX-666/item.git
cd item
git lfs pull
```

| Asset | Path | Approx. size |
| --- | --- | --- |
| YOLO worker model | `vlm-detection/weights/worker/yolo26x_worker.pt` | ~113 MB |
| YOLO machinery model | `vlm-detection/weights/machinery/yolo26l_machinery.pt` | ~51 MB |
| RapidOCR det/rec/cls | `models/yaoyao/rapidocr/*.onnx` | ~16 MB total |

---

## 3. Architecture You Must Follow

```text
chitung-frontend (Vue/Electron)
        │  HTTP only
        ▼
chitung-center (FastAPI)
   intent router · workflow · LLM gateway · audit
        │  toolbox_client (httpx)
        ▼
agent-toolbox (FastAPI + MCP)
   tools · SQLite · file I/O · VLM/OCR/Feishu/WhatsApp
        │
        ├── local files / safety_platform.db (runtime, not in git)
        └── cloud LLM / VLM APIs (keys in .env only)
```

**Integration rule:** If a button exists in the UI, it must call a real `chitung-center` endpoint. Do not leave mock “success” states when the backend is down.

---

## 4. First-Hour Setup (Windows)

### 4.1 Prerequisites

- Python 3.11+ (3.13 tested)  
- Node.js 18+  
- Git + Git LFS  
- ffmpeg on PATH (for RTMP snapshot)  
- Optional: CUDA PyTorch if you want faster YOLO

### 4.2 Environment files

```powershell
cd item
copy agent-toolbox\.env.example agent-toolbox\.env
copy chitung-center\.env.example chitung-center\.env
copy chitung-frontend\.env.example chitung-frontend\.env
```

| Variable | Where | Purpose |
| --- | --- | --- |
| `VITE_CHITUNG_CENTER_URL` | `chitung-frontend/.env` | Frontend → center (default `http://127.0.0.1:8999`) |
| `AGENT_TOOLBOX_BASE_URL` | `chitung-center/.env` | Center → toolbox (default `http://127.0.0.1:8899`) |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | `chitung-center/.env` only | Cloud LLM gateway |
| `SECUREEYE_*` | `agent-toolbox/.env` | VLM vision API (e.g. GLM-4v) |
| `YAOYAO_MODEL_DIR` | `agent-toolbox/.env` | Point to `models/yaoyao/rapidocr` |
| `FEISHU_APP_*` | `agent-toolbox/.env` | Feishu bot (optional for MVP) |
| `VLM_DETECTION_DIR` | `agent-toolbox/.env` | Path to `vlm-detection` |

**Never commit `.env` files.**

### 4.3 Start services (in order)

```powershell
# Terminal 1 — AgentToolbox
cd agent-toolbox
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_server.py          # → http://127.0.0.1:8899

# Terminal 2 — Chitung Center
cd chitung-center
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_server.py          # → http://127.0.0.1:8999

# Terminal 3 — Frontend
cd chitung-frontend
npm install
npm run desktop:dev             # → http://127.0.0.1:5173
```

If ports are busy, use **8898 / 9000 / 5174** and update `.env` consistently.

### 4.4 Smoke checks

```powershell
Invoke-WebRequest http://127.0.0.1:8899/health
Invoke-WebRequest http://127.0.0.1:8999/health
```

Run toolbox tests for visual stack:

```powershell
cd agent-toolbox
python -m pytest tests/test_secureeye_vlm.py -v
```

---

## 5. Current Completion Status (Honest)

The repo is a **strong prototype**, not a finished product. Do not assume “tool registered” = “end-to-end works”.

| Area | ~Completion | Notes |
| --- | --- | --- |
| Three-layer skeleton | 70% | Services start; port/env drift was a past issue |
| AgentToolbox tool pool | 55% | 129+ tools registered; many need E2E wiring |
| Frontend shell | 60% | Some pages still show mock/fallback data |
| Center orchestration | 35% | Workflow engine & confirmation chain incomplete |
| E2E business loops | 25% | MVP loops below are the priority |
| Feishu mobile loop | 20% | Message parse + card confirm execution missing |
| Visual patrol E2E | 25% | YOLO+VLM hybrid works in script/API; case loop incomplete |
| Yaoyao OCR | 40% | Runtime + models in repo; center E2E needs hardening |
| Workflow/Skill productization | 15% | 24 workflows / 32 skills are planned, not implemented |

---

## 6. MVP Scope — What to Finish First

Ship **6 demonstrable loops** before expanding scope:

### Loop 1 — Hazard intake → rectification notice

```text
User NL input → intent → create_safety_case → generate_rectification_notice
→ confirmation card → human approve → audit + DB write
```

### Loop 2 — Daily external risk briefing

```text
fetch_hko_weather + fetch_hk_safety_updates → summarize → draft_daily_risk_briefing
→ confirm → save or send draft
```

### Loop 3 — Smart form filling

```text
search_form_templates → prefill_form_fields → generate_docx_from_template → form_records
```

### Loop 4 — Shanshan DocMate E2E

```text
read DOCX → generate changeset → preview → apply → export new DOCX
```

### Loop 5 — Yaoyao Huidu E2E

```text
POST /api/yaoyao/structured/draft → OCR regions → user edit fields
→ POST /api/yaoyao/structured/confirm → export_form_record
```

Key files:

- `agent-toolbox/agent_toolbox/tools/yaoyao_*.py`  
- `agent-toolbox/agent_toolbox/third_party/yaoyao/rapid_ocr_worker.py`  
- `chitung-center/chitung_center/yaoyao_structured_service.py`  
- `chitung-frontend/src/pages/YaoyaoStructuredInputPage.vue`

### Loop 6 — Feishu NL + confirmation card (mobile MVP)

```text
Feishu message → parse → route to /api/chat/message → toolbox chain
→ Feishu review card → button click → execute confirmed action → update card → audit
```

See `docs/product/飞书机器人五阶段实施工具清单.md` for the 10-tool Feishu MVP list.

---

## 7. Visual Patrol (Chitung Guardian) — Priority Integration

### Pipeline

```text
RTMP snapshot → YOLO dual-model detect → (optional) VLM enhance → candidates
→ human confirm → create safety case → evidence + audit
```

### API chain

| Step | Endpoint |
| --- | --- |
| Frontend → Center | `POST /api/visual/patrol-draft` |
| Center → Toolbox | `POST /tools/run_vlm_detection_batch` |
| Center → Toolbox (hybrid) | `POST /tools/secureeye_analyze_batch` |
| Center → Toolbox (hybrid) | `POST /tools/secureeye_merge_results` |

Hybrid request example:

```json
{
  "camera_url": "rtmp://...",
  "area": "B2",
  "count": 1,
  "analysis_mode": "hybrid",
  "vlm_enhance_conf_threshold": 0.6
}
```

Standalone script (no services required):

```powershell
cd scripts
python nightly_patrol.py --camera cam-slope-03
python nightly_patrol.py --loop --interval 7200
```

Key source files:

- `scripts/nightly_patrol.py`  
- `chitung-center/chitung_center/visual_patrol_service.py`  
- `agent-toolbox/agent_toolbox/tools/secureeye_vlm.py`  
- `chitung-frontend/src/pages/VisualPatrolPage.vue`

**Known issue:** Ezviz RTMP tokens may expire; script falls back to `fixtures/visual-samples/` images.

---

## 8. Yaoyao Huidu vs PaddleOCR — Clarification

| Layer | Technology | Location |
| --- | --- | --- |
| **Production OCR runtime** | RapidOCR (`rapidocr_onnxruntime`) | `agent-toolbox/.../yaoyao/` |
| **Bundled models** | PP-OCRv4 ONNX | `models/yaoyao/rapidocr/` (Git LFS) |
| **PaddleOCRSharp reference** | C# Windows OCR app | `external/paddle-ocr-sharp/` |

Runtime uses **`YAOYAO_MODEL_DIR`**, not Paddle DLLs. The C# code is for reference and Windows-native experiments.

---

## 9. P0 Engineering Tasks (Start Here)

### Week 1 — Trustworthy runtime

1. Fix port/env consistency (`CHITUNG_CENTER_PORT`, `AGENT_TOOLBOX_BASE_URL`, `VITE_CHITUNG_CENTER_URL`).  
2. Remove fake success / mock data on workbench and visual pages when backend is offline.  
3. Ensure `/health` on all three layers reflects real connectivity.

### Week 2 — Center orchestration

4. Implement unified `PendingConfirmation` + card action execution.  
5. Wire `orchestrator.handle_card_action()` to real toolbox chains.  
6. Persist `workflow_runs` / `workflow_steps` (minimal schema).

### Week 3 — MVP loops

7. Complete Loop 1 (hazard) and Loop 2 (daily briefing) E2E with audit.  
8. Complete Loop 5 (Yaoyao) and Loop 3 (form filling) E2E.  
9. Start Loop 6 (Feishu): `feishu_parse_message_event`, `route_feishu_message_to_center`, `feishu_parse_card_action`, `execute_confirmed_feishu_action`.

### Week 4 — Visual E2E

10. `capture_camera_snapshot → run_vlm_detection_batch → create_case_from_vlm` with human confirm.  
11. Visual page shows real task status, not fallback cameras.

---

## 10. Key Entry Points (Bookmark These)

```text
chitung-center/chitung_center/app.py              # All center routes
chitung-center/chitung_center/orchestrator.py      # Chat orchestration
chitung-center/chitung_center/visual_patrol_service.py
chitung-center/chitung_center/yaoyao_structured_service.py

agent-toolbox/agent_toolbox/app.py                # Tool route registration
agent-toolbox/agent_toolbox/registry.py
agent-toolbox/agent_toolbox/tools/secureeye_vlm.py
agent-toolbox/agent_toolbox/tools/feishu.py
agent-toolbox/agent_toolbox/tools/safety.py

chitung-frontend/src/services/chitungApi.ts       # Frontend API client
chitung-frontend/src/App.vue                      # Routes
```

---

## 11. Security & Git Rules

- **Do not commit:** `.env`, API keys, RTMP tokens, `workspace/`, `patrol-output/`, local DB files.  
- **Do not expose** AgentToolbox to the public internet without auth.  
- **All outbound messages** (Feishu/WhatsApp) require human confirmation.  
- **All tool calls** must write to audit logs.  
- Use **directory-based** `git add` on Windows (avoid Chinese filenames in CLI args).

Full upload script:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/github-upload-full.ps1
```

---

## 12. Acceptance Checklist (30 Minutes)

After setup, verify:

- [ ] `git lfs pull` — YOLO `.pt` and RapidOCR `.onnx` present locally  
- [ ] Toolbox / center / frontend health return 200  
- [ ] Frontend shows real center connection status (not mock)  
- [ ] `POST /api/visual/patrol-draft` with `analysis_mode=yolo_only` returns candidates  
- [ ] Hybrid mode returns `description` / `severity` fields  
- [ ] `POST /api/yaoyao/structured/draft` runs OCR using bundled models  
- [ ] `python scripts/nightly_patrol.py --camera cam-slope-03` produces report  
- [ ] No `.env` or secrets in git status  

---

## 13. Further Reading

| Document | Language | Topic |
| --- | --- | --- |
| `docs/COLLABORATION_HANDOFF.md` | Chinese | Quick start + API summary |
| `docs/UPLOAD_MANIFEST.md` | Chinese | What is / is not in the repo |
| `docs/product/` | Chinese | Product specs, Feishu 5-phase plan, visual guides |
| `frontend-ui-prototype/` | Chinese UI | Target UX and page layout |
| `CODE_RELATIONSHIP_GRAPH_2026-06-20.md` | Chinese | Module dependency graph |
| `models/yaoyao/README.md` | Chinese | OCR model setup |

---

## 14. One-Sentence Mission

**Turn this prototype into a local-first, human-in-the-loop safety workbench where officers can see hazards, ask questions, fill forms, draft notices, confirm actions on Feishu, and leave a full audit trail — without leaking site data to the cloud.**

Questions blocked on secrets (LLM keys, Feishu app, RTMP URLs) → ask the project owner. Everything else should be derivable from this repo.

---

*End of final handoff — good luck shipping the MVP.*
