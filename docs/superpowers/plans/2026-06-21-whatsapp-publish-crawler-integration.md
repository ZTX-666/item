# WhatsApp, Publish3.0, And Crawler Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the useful work from the WhatsApp/publish branch and the Hong Kong safety crawler MVP into the current safety intelligence platform without losing the RAG, video patrol, briefing persistence, and feed work already on `codex/merge-origin-main-20260621`.

**Architecture:** Treat WhatsApp as a first-class runtime integration in the root app, keep `publish3.0/` as a packaged desktop delivery artifact, and migrate the crawler MVP into the existing external-risk toolchain instead of merging its unrelated repository root. SQLite remains the persistence layer surfaced by `chitung-center` APIs and Vue pages.

**Tech Stack:** Python/FastAPI, Vue/Vite, Node CCTV gateway, SQLite, wacli/WhatsApp archive service, Git LFS for large binaries.

## Global Constraints

- Base branch: `codex/merge-origin-main-20260621`.
- Working branch: `integration/whatsapp-publish-crawler`.
- Do not merge `hk-site-safety-crawler-mvp` with unrelated history directly.
- Preserve current RAG, external briefing, CCTV, VLM, and Feishu behavior.
- Write failing tests before changing production code for each behavior change.
- Use Git LFS for large runtime binaries.

---

### Task 1: Restore WhatsApp Runtime Integration

**Files:**
- Modify: `agent-toolbox/agent_toolbox/tools/whatsapp.py`
- Modify: `agent-toolbox/agent_toolbox/app.py`
- Modify: `agent-toolbox/agent_toolbox/mcp_server.py`
- Modify: `agent-toolbox/agent_toolbox/registry.py`
- Modify: `agent-toolbox/agent_toolbox/config.py`
- Create/Modify tests under `agent-toolbox/tests/`
- Create: `chitung-center/chitung_center/whatsapp_adapter_service.py`
- Modify: `chitung-center/chitung_center/app.py`
- Modify: `chitung-center/chitung_center/models.py`
- Modify: `chitung-frontend/src/pages/WhatsAppOpsPage.vue`
- Modify: `chitung-frontend/src/services/chitungApi.ts`

**Interfaces:**
- Produces toolbox tools: `whatsapp_search`, `whatsapp_download_media`, `whatsapp_list_groups`, `whatsapp_refresh_groups`, `whatsapp_send_text`, `whatsapp_auth_start`, `whatsapp_auth_status`, `whatsapp_auth_stop`, `whatsapp_auth_logout`, `whatsapp_sync_start`, `whatsapp_sync_status`, `whatsapp_sync_stop`.
- Produces center API endpoints under `/api/whatsapp/*` and `/integrations/whatsapp/events`.
- Consumes `WHATSAPP_ARCHIVE_BASE_URL`, `WACLI_BIN`, `WACLI_STORE_DIR`, and `WACLI_WORKDIR`.

- [ ] Add failing agent-toolbox tests for wacli-backed group listing and confirmed send.
- [ ] Restore minimal wacli helpers and WhatsApp tool methods.
- [ ] Add failing chitung-center tests for WhatsApp event adapter and API routing.
- [ ] Restore adapter service and API endpoints.
- [ ] Update frontend API wrappers and WhatsApp page controls.
- [ ] Run `agent-toolbox` and `chitung-center` tests plus frontend build.
- [ ] Commit WhatsApp integration.

### Task 2: Merge Publish3.0 Delivery Package

**Files:**
- Add/modify: `publish3.0/**`
- Review: `.gitattributes`

**Interfaces:**
- Consumes the root platform services and copies packaged versions into `publish3.0/agent-services`.
- Produces Windows desktop/package assets under `publish3.0/`.

- [ ] Cherry-pick `8523fca`, `2b68a77`, and `74f88d2`.
- [ ] Confirm large binaries are tracked through Git LFS or explicitly accepted.
- [ ] Review `publish3.0/runtime/environment.json` for machine-specific paths and document the limitation.
- [ ] Run repository smoke tests that are available on macOS.
- [ ] Commit publish package integration if cherry-pick is not already a clean commit.

### Task 3: Migrate Hong Kong Safety Crawler MVP

**Files:**
- Create: `agent-toolbox/agent_toolbox/tools/hk_site_safety_crawler/`
- Create: `agent-toolbox/config/crawler/`
- Modify: `agent-toolbox/agent_toolbox/tools/external_risk.py`
- Modify: `agent-toolbox/agent_toolbox/registry.py`
- Modify: `agent-toolbox/agent_toolbox/app.py`
- Modify: `agent-toolbox/tests/`
- Modify as needed: `chitung-center/chitung_center/workflow_engine.py`
- Modify as needed: `chitung-frontend/src/pages/ExternalRiskMonitorPage.vue`

**Interfaces:**
- Produces a callable external-risk crawler function/tool returning normalized items, risk cards, and source metadata.
- Consumes crawler skill YAML files and source configuration.
- Feeds existing external briefing persistence and frontend report display.

- [ ] Add failing tests for loading crawler source/skill config and keyword filtering.
- [ ] Copy crawler package into the existing agent-toolbox namespace.
- [ ] Expose crawler through external-risk tools without duplicating frontend persistence.
- [ ] Add tests for brief generation using crawler items.
- [ ] Run agent-toolbox, chitung-center, frontend, and CCTV verification.
- [ ] Commit crawler migration.

### Task 4: Final Verification And Push

- [ ] Run `cd agent-toolbox && .venv/bin/python -m pytest tests -q`.
- [ ] Run `cd chitung-center && .venv/bin/python -m pytest tests -q`.
- [ ] Run `cd chitung-frontend && npm run build && npm run test:yaoyao-feed`.
- [ ] Run `cd cctv-gateway && npm test`.
- [ ] Verify `git status --short --branch` is clean after commit.
- [ ] Push `integration/whatsapp-publish-crawler`.
