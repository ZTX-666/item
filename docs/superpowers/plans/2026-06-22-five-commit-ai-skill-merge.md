# Five Commit AI Skill Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the useful functionality from commits `d3f2f9d`, `161159a`, `bba5d6a`, `73de5bd`, and `c2dcbb0` into the current `integration/whatsapp-publish-crawler` branch without regressing the existing WhatsApp AI skills.

**Architecture:** Treat WhatsApp and DocMate as sibling AI assistant skills. WhatsApp remains `whatsapp_sql_query` and `whatsapp_wacli_ops`; DocMate becomes its own document-editing skill/workflow, routed by the same LLM intent system. Shared files such as `ChatbotPanel.vue`, `chitungApi.ts`, `app.py`, and `models.py` must be edited additively.

**Tech Stack:** Python FastAPI services in `agent-toolbox` and `chitung-center`; Vue 3 frontend in `chitung-frontend`; local LLM routing through `chitung_center.llm_gateway`; pytest and npm verification.

## Global Constraints

- Current checkpoint commit is `448fc50 feat: integrate whatsapp assistant workflows`.
- Do not merge or cherry-pick the five commits wholesale into the live branch.
- Preserve current WhatsApp login, SQL query, wacli operation, group-name resolution, and send-confirmation behavior.
- DocMate must be an AI assistant skill parallel to WhatsApp, not a WhatsApp feature.
- Skip raw `Front End Logo/` files; only keep final frontend assets under `chitung-frontend/src/assets/logos/`.
- Keep the existing untracked `publish3.0/runtime/src/` untouched unless the user explicitly requests otherwise.
- Use small commits after each independently verified task.

---

## File Structure

- Modify `agent-toolbox/agent_toolbox/config.py`: cross-platform repo-relative defaults.
- Modify `agent-toolbox/.env.example`: optional override documentation while preserving current `publish3.0` wacli notes.
- Modify `agent-toolbox/agent_toolbox/tools/docmate_docx.py`: cross-run replacement plus new DocMate document and changeset helper tools.
- Modify `agent-toolbox/agent_toolbox/app.py`: expose new DocMate tool endpoints.
- Modify `chitung-center/chitung_center/llm_gateway.py`: add document JSON completion path.
- Modify `chitung-center/chitung_center/docmate_service.py`: LLM-first DocMate edit, retry, and commit flow.
- Modify `chitung-center/chitung_center/models.py`: add DocMate request models only.
- Modify `chitung-center/chitung_center/app.py`: add DocMate upload, download, commit, and retry API routes.
- Create or update `chitung-center/skills/docmate-edit/SKILL.md`: AI assistant skill instructions for DocMate.
- Modify `chitung-center/chitung_center/intent_router.py`: route document-edit intent to DocMate.
- Modify `chitung-center/chitung_center/workflow_templates.py`: add `workflow_docmate_edit`.
- Modify `chitung-center/chitung_center/orchestrator.py`: execute DocMate workflow through tools/cards.
- Modify `chitung-frontend/src/services/chitungApi.ts`: append DocMate API client functions.
- Create `chitung-frontend/src/composables/useDocmateSession.ts`: shared DocMate session state.
- Create `chitung-frontend/src/components/documents/DocmateDiffReview.vue`: diff review UI.
- Modify `chitung-frontend/src/pages/ShanshanDocPage.vue`: DocMate page experience.
- Modify `chitung-frontend/src/components/layout/ChatbotPanel.vue`: display DocMate skill cards without replacing current AI assistant flow.
- Add `chitung-frontend/src/assets/logos/*`: final brand and module logo assets.
- Modify `chitung-frontend/src/components/layout/ActivityBar.vue`, `PanelSidebar.vue`, `TopBar.vue`, and `style.css`: selective brand/design integration.

## Task 1: Path Defaults

**Files:**
- Modify: `agent-toolbox/agent_toolbox/config.py`
- Modify: `agent-toolbox/.env.example`
- Optional modify: `chitung-frontend/package-lock.json`

**Interfaces:**
- Consumes: existing `Settings` dataclass.
- Produces: repo-relative defaults for VLM, RTMP, and report paths.

- [ ] Add `REPO = ROOT.parent` in `config.py`.
- [ ] Change `VLM_DETECTION_DIR` default to `REPO / "vlm-detection"`.
- [ ] Change `VLM_PYTHON`, `RTMP_PYTHON`, and `REPORT_PYTHON` defaults to `python3`.
- [ ] Change RTMP and report script defaults to repo-relative paths.
- [ ] Keep current `WACLI_BIN`, `WACLI_WORKDIR`, and `publish3.0` guidance in `.env.example`.
- [ ] Run `PYTHONPATH=agent-toolbox python -m pytest agent-toolbox/tests/test_runner.py -q`.
- [ ] Commit with `chore: make toolbox paths repo relative`.

## Task 2: DocMate Toolbox Tools

**Files:**
- Modify: `agent-toolbox/agent_toolbox/tools/docmate_docx.py`
- Modify: `agent-toolbox/agent_toolbox/app.py`
- Test: add or update `agent-toolbox/tests/test_docmate_docx.py`

**Interfaces:**
- Produces tool names: `docmate_get_document`, `docmate_register_changeset`.
- Preserves existing tools: `docmate_read_docx`, `docmate_generate_changeset`, `docmate_preview_changeset`, `docmate_apply_changeset`.

- [ ] Write a failing test where a target string spans multiple Word runs and `docmate_apply_changeset` replaces it correctly.
- [ ] Add `_replace_in_paragraph` from `bba5d6a`, adapted to current helper names.
- [ ] Add request models for `GetDocumentRequest` and `RegisterChangesetRequest`.
- [ ] Add async endpoint wrappers in `agent_toolbox/app.py`.
- [ ] Verify all DocMate tool specs still register.
- [ ] Run `PYTHONPATH=agent-toolbox python -m pytest agent-toolbox/tests/test_docmate_docx.py -q`.
- [ ] Commit with `feat: add docmate document changeset tools`.

## Task 3: DocMate Center APIs

**Files:**
- Modify: `chitung-center/chitung_center/llm_gateway.py`
- Modify: `chitung-center/chitung_center/docmate_service.py`
- Modify: `chitung-center/chitung_center/models.py`
- Modify: `chitung-center/chitung_center/app.py`
- Test: add or update `chitung-center/tests/test_docmate_service.py`

**Interfaces:**
- Produces API routes: `/api/docmate/upload`, `/api/docmate/download`, `/api/docmate/commit`, `/api/docmate/retry`.
- Produces service functions: `commit_edits`, `retry_edits`.

- [ ] Write service tests with mocked `toolbox_client.call_tool` and mocked `llm_gateway.complete_document_json`.
- [ ] Add `complete_document_json` in `llm_gateway.py` with higher token budget and JSON-only output.
- [ ] Add upload and download routes using `settings.chitung_data_dir / "docmate_uploads"`.
- [ ] Add `DocmateCommitRequest` and `DocmateRetryRequest`.
- [ ] Implement LLM-first edit generation in `docmate_service.py`, falling back to existing toolbox generation when needed.
- [ ] Run `PYTHONPATH=chitung-center chitung-center/.venv/bin/pytest chitung-center/tests/test_docmate_service.py -q`.
- [ ] Commit with `feat: add docmate center editing APIs`.

## Task 4: DocMate As AI Assistant Skill

**Files:**
- Create: `chitung-center/skills/docmate-edit/SKILL.md`
- Modify: `chitung-center/chitung_center/intent_router.py`
- Modify: `chitung-center/chitung_center/workflow_templates.py`
- Modify: `chitung-center/chitung_center/orchestrator.py`
- Test: update `chitung-center/tests/test_orchestrator_capabilities.py`

**Interfaces:**
- Produces intent: `docmate_edit`.
- Produces workflow: `workflow_docmate_edit`.
- Produces skill name: `docmate-edit`.

- [ ] Add `docmate_edit` to allowed intents and LLM router prompt.
- [ ] Move document-edit keywords such as `改文档`, `替换`, `润色`, `docx`, `changeset`, and `DocMate` out of generic `document_form` routing where appropriate.
- [ ] Add `workflow_docmate_edit` as a sibling of `workflow_whatsapp_sql_query` and `workflow_whatsapp_wacli_ops`.
- [ ] Add skill instructions that say DocMate handles DOCX editing, diff preview, retry, and commit; it must not call WhatsApp tools.
- [ ] Ensure WhatsApp intents still route to WhatsApp skills.
- [ ] Run `PYTHONPATH=chitung-center chitung-center/.venv/bin/pytest chitung-center/tests/test_orchestrator_capabilities.py -q`.
- [ ] Commit with `feat: route docmate as assistant skill`.

## Task 5: DocMate Frontend Experience

**Files:**
- Modify: `chitung-frontend/src/services/chitungApi.ts`
- Create: `chitung-frontend/src/composables/useDocmateSession.ts`
- Create: `chitung-frontend/src/components/documents/DocmateDiffReview.vue`
- Modify: `chitung-frontend/src/pages/ShanshanDocPage.vue`
- Modify: `chitung-frontend/src/components/layout/ChatbotPanel.vue`

**Interfaces:**
- Consumes API functions: `docmateUpload`, `docmateCommit`, `docmateRetry`, `docmateDownloadUrl`.
- Produces shared state for document upload, preview cards, accepted change IDs, retry, and output path.

- [ ] Append DocMate API functions to `chitungApi.ts` without changing existing WhatsApp API functions.
- [ ] Add `useDocmateSession.ts` as a shared state composable.
- [ ] Add `DocmateDiffReview.vue` for accept, reject, retry, commit, and download states.
- [ ] Update `ShanshanDocPage.vue` to use the shared DocMate session.
- [ ] Update `ChatbotPanel.vue` additively: keep `useAiAssistant`, chat history, card actions, WhatsApp skill output, and tool-result rendering intact.
- [ ] Add a DocMate quick action such as `文档改稿`, but route through the normal AI assistant message flow.
- [ ] Run `cd chitung-frontend && npm run build`.
- [ ] Commit with `feat: add docmate assistant review UI`.

## Task 6: Brand Logos

**Files:**
- Add: `chitung-frontend/src/assets/logos/brand.jpg`
- Add: `chitung-frontend/src/assets/logos/center.png`
- Add: `chitung-frontend/src/assets/logos/docmate.png`
- Add: `chitung-frontend/src/assets/logos/guardian.png`
- Add: `chitung-frontend/src/assets/logos/lingxun.png`
- Add: `chitung-frontend/src/assets/logos/yaoyao.png`
- Modify: `chitung-frontend/src/components/layout/ActivityBar.vue`
- Modify: `chitung-frontend/src/components/layout/PanelSidebar.vue`
- Modify: `chitung-frontend/src/components/layout/TopBar.vue`
- Modify: `chitung-frontend/src/style.css`

**Interfaces:**
- Produces reusable logo imports for layout components.
- Preserves existing route paths and current menu entries.

- [ ] Copy only final logo assets from `c2dcbb0`.
- [ ] Do not add root `Front End Logo/` or `Read Me.docx`.
- [ ] Use image logos in topbar, activity bar, and panel sidebar.
- [ ] Keep module names consistent with the current project language; avoid accidental `零讯` vs `灵讯` drift.
- [ ] Run `cd chitung-frontend && npm run build`.
- [ ] Commit with `feat: apply product logo branding`.

## Task 7: Selective Design System Merge

**Files:**
- Modify: `chitung-frontend/src/style.css`
- Selectively modify: shared card, form, button, and page components touched by `73de5bd`
- Avoid wholesale overwrite: `chitung-frontend/src/pages/WhatsAppOpsPage.vue`
- Avoid wholesale overwrite: `chitung-frontend/src/components/layout/ChatbotPanel.vue`

**Interfaces:**
- Produces better contrast, focus states, buttons, input styling, and rail variables.
- Preserves current WhatsApp workbench behavior.

- [ ] Port global CSS tokens, focus, scrollbar, form, button, and surface rules from `73de5bd`.
- [ ] Review each page-level change manually; accept only visual improvements that do not remove current data flows.
- [ ] Run `cd chitung-frontend && npm run test:assistant && npm run test:whatsapp-ops && npm run build`.
- [ ] Use the in-app browser to inspect `/center/assistant`, `/lingxun/whatsapp`, and `/docmate` or the current Shanshan route.
- [ ] Commit with `style: refine shared frontend design system`.

## Task 8: Full Regression Verification

**Files:**
- No planned source edits unless a verification failure exposes a defect.

**Interfaces:**
- Confirms WhatsApp and DocMate can coexist as AI assistant skills.

- [ ] Run agent-toolbox tests:

```bash
PYTHONPATH=agent-toolbox chitung-center/.venv/bin/pytest agent-toolbox/tests/test_whatsapp_wacli.py agent-toolbox/tests/test_docmate_docx.py -q
```

- [ ] Run center tests:

```bash
PYTHONPATH=chitung-center chitung-center/.venv/bin/pytest \
  chitung-center/tests/test_orchestrator_capabilities.py \
  chitung-center/tests/test_whatsapp_adapter_service.py \
  chitung-center/tests/test_whatsapp_local_service.py \
  chitung-center/tests/test_docmate_service.py -q
```

- [ ] Run frontend tests:

```bash
cd chitung-frontend
npm run test:assistant
npm run test:whatsapp-ops
npm run build
```

- [ ] Browser smoke: ask AI assistant a WhatsApp request and confirm it still uses WhatsApp skill.
- [ ] Browser smoke: ask AI assistant a DocMate document-edit request and confirm it uses DocMate skill.
- [ ] Browser smoke: open WhatsApp console and confirm QR, pairing, SQL query, command tools still render.
- [ ] Final commit if verification fixes were needed.

## Execution Notes

- Direct full cherry-pick conflicts observed:
  - `d3f2f9d`: `agent-toolbox/.env.example`
  - `bba5d6a`: `chitung-frontend/src/components/layout/ChatbotPanel.vue`
  - `73de5bd`: `ChatbotPanel.vue`, `WhatsAppOpsPage.vue`
  - `c2dcbb0`: logos, `ActivityBar.vue`, `PanelSidebar.vue`, `style.css`
- `161159a` applies cleanly but should be treated as raw asset staging only.
- The safe implementation path is manual, additive, and skill-oriented.
