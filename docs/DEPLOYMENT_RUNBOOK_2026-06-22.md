# Deployment Runbook: AI Skills, DocMate, WhatsApp wacli

This runbook is for a fresh checkout of the current integration branch after the
DocMate skill, WhatsApp wacli skill, and frontend branding merges.

## Scope

The branch includes:

- Chitung Center AI assistant skills and workflows:
  - `docmate-edit`
  - `whatsapp-wacli-ops`
  - `whatsapp-sql-query`
- AgentToolbox APIs for DocMate document operations and WhatsApp local tools.
- Frontend pages and assistant quick actions for DocMate and WhatsApp.
- Cross-platform repo-relative defaults for local tool paths.

Real local `.env` files and secrets are intentionally not committed. Use the
tracked `.env.example` files as templates only when an override is needed.

## Prerequisites

- Git
- Python 3.11+ recommended
- Node.js 20+ recommended
- npm
- Optional for WhatsApp sync/login:
  - `wacli` binary or the bundled `publish3.0/runtime/bin/wacli.exe` on Windows
  - A local wacli store containing `wacli.db`
- Optional for WhatsApp archive search/download:
  - `whatsapp-archive/app-server` running on `http://127.0.0.1:8787`
- Optional for high-quality DocMate AI rewrites:
  - `LLM_API_KEY` or one of the compatible Zhipu/GLM/DocMate API keys

## Checkout

```bash
git clone <repo-url> item
cd item
git checkout integration/whatsapp-publish-crawler
git pull
```

To pin an exact revision, use the commit hash provided by the maintainer:

```bash
git checkout <commit-hash>
```

## Environment Files

Do not commit real `.env` files.

Create local env files only if defaults are not enough:

```bash
cp agent-toolbox/.env.example agent-toolbox/.env
cp chitung-center/.env.example chitung-center/.env
cp chitung-frontend/.env.example chitung-frontend/.env
```

Default ports:

- AgentToolbox: `http://127.0.0.1:8899`
- Chitung Center: `http://127.0.0.1:8999`
- Chitung Frontend: `http://127.0.0.1:5173`
- WhatsApp archive app-server: `http://127.0.0.1:8787`

Important optional variables:

- `agent-toolbox/.env`
  - `WHATSAPP_ARCHIVE_BASE_URL=http://127.0.0.1:8787`
  - `WACLI_BIN`
  - `WACLI_WORKDIR`
  - `WACLI_STORE_DIR`
  - `WHATSCLI_DB_PATH` if the legacy archive server must read a specific DB
- `chitung-center/.env`
  - `AGENT_TOOLBOX_BASE_URL=http://127.0.0.1:8899`
  - `LLM_BASE_URL`
  - `LLM_API_KEY`
  - `LLM_MODEL`
  - or `GLM_API_KEY` / `ZHIPU_API_KEY` / `DOCMATE_API_KEY`
- `chitung-frontend/.env`
  - `VITE_CHITUNG_CENTER_URL=http://127.0.0.1:8999`

The merged path handling resolves most repo-local tools automatically. Set
absolute paths only when your local layout is non-standard.

## Install Dependencies

AgentToolbox:

```bash
cd agent-toolbox
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cd ..
```

Chitung Center:

```bash
cd chitung-center
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cd ..
```

Chitung Frontend:

```bash
cd chitung-frontend
npm install
cd ..
```

Optional WhatsApp archive app-server:

```bash
cd whatsapp-archive/app-server
npm install
cd ../..
```

## Startup Order

Start AgentToolbox:

```bash
cd agent-toolbox
.venv/bin/python run_server.py
```

Start Chitung Center in another terminal:

```bash
cd chitung-center
.venv/bin/python run_server.py
```

Start the frontend in another terminal:

```bash
cd chitung-frontend
npm run dev -- --host 127.0.0.1
```

Optional: start WhatsApp archive app-server in another terminal:

```bash
cd whatsapp-archive/app-server
WHATSCLI_DB_PATH=/absolute/path/to/wacli.db npm start
```

When `WHATSCLI_DB_PATH` is omitted, the archive server searches its default
store directory. For this integrated workbench, pointing it at the same
`wacli.db` used by AgentToolbox is usually the least surprising setup.

## Verification

Backend health:

```bash
curl -sS http://127.0.0.1:8899/health
curl -sS http://127.0.0.1:8999/health
curl -sS -I http://127.0.0.1:5173/
```

If the optional WhatsApp archive server is running:

```bash
curl -sS http://127.0.0.1:8787/api/health
```

Expected pages:

- `http://127.0.0.1:5173/#/center/assistant`
  - AI assistant page.
  - Should expose WhatsApp and DocMate skill/workflow entry points.
- `http://127.0.0.1:5173/#/docmate/documents`
  - DocMate document review workspace.
- `http://127.0.0.1:5173/#/lingxun/whatsapp`
  - WhatsApp console, login pairing, data browsing, SQLite query, and command tools.

Regression checks used during the merge:

```bash
PYTHONPATH=agent-toolbox chitung-center/.venv/bin/pytest \
  agent-toolbox/tests/test_docmate_docx.py \
  agent-toolbox/tests/test_whatsapp_wacli.py -q

PYTHONPATH=chitung-center chitung-center/.venv/bin/pytest \
  chitung-center/tests/test_docmate_service.py \
  chitung-center/tests/test_orchestrator_capabilities.py \
  chitung-center/tests/test_whatsapp_adapter_service.py \
  chitung-center/tests/test_whatsapp_local_service.py -q

cd chitung-frontend
npm run test:assistant
npm run test:whatsapp-ops
node scripts/verify-docmate-frontend-contract.mjs
npm run build
```

For full local confidence:

```bash
cd agent-toolbox
PYTHONPATH=. ../chitung-center/.venv/bin/pytest tests -q

cd ../chitung-center
PYTHONPATH=. .venv/bin/pytest tests -q
```

## WhatsApp Notes

- QR/pairing login and message sync are handled by `wacli` through AgentToolbox.
- Data browsing and SQLite query read from the local `wacli.db`.
- Natural-language WhatsApp requests should go through the `whatsapp-wacli-ops`
  and `whatsapp-sql-query` skills in Chitung Center.
- Group names can be used by the assistant, but the implementation may resolve
  them to JIDs internally before calling wacli.
- Sending messages is a write operation. Keep it gated by the workflow safety
  rules and user confirmation policy.
- If `whatsapp_archive` is unavailable in `/health`, archive search/download
  through `whatsapp-archive/app-server` will fail, but local wacli-backed
  status, SQLite, and command operations can still work.

## DocMate Notes

- The assistant has a dedicated `docmate-edit` skill and workflow.
- The frontend document page uploads `.docx`, reads the document through
  AgentToolbox, requests AI changes through Chitung Center, reviews diffs, and
  applies changes through AgentToolbox.
- Configure the LLM in `chitung-center/.env`. If no compatible key is present,
  DocMate behavior is limited to local/fallback paths.

## Troubleshooting

- Port already in use:

  ```bash
  lsof -nP -iTCP:8899 -sTCP:LISTEN
  lsof -nP -iTCP:8999 -sTCP:LISTEN
  lsof -nP -iTCP:5173 -sTCP:LISTEN
  ```

- Frontend still reads old backend URL:
  - Restart Vite after changing `chitung-frontend/.env`.

- Center cannot reach AgentToolbox:
  - Check `AGENT_TOOLBOX_BASE_URL`.
  - Confirm `curl http://127.0.0.1:8899/health` works.

- WhatsApp archive search fails:
  - Start `whatsapp-archive/app-server`.
  - Point `WHATSCLI_DB_PATH` to the correct `wacli.db`.
  - Confirm `curl http://127.0.0.1:8787/api/health` returns `ok: true`.

- wacli commands fail:
  - Confirm `WACLI_BIN`, `WACLI_WORKDIR`, and `WACLI_STORE_DIR`.
  - Confirm login status in `#/lingxun/whatsapp`.
  - Run `wacli doctor` from the command tool for diagnostics.

- Git LFS hook is unavailable during commit:
  - Install Git LFS locally if this repo requires it.
  - Do not bypass hooks when committing large or binary assets.

## Security

- Keep API keys in local `.env` files only.
- Do not expose AgentToolbox, Chitung Center, or WhatsApp archive services to the
  public internet without authentication.
- Do not commit local WhatsApp databases, session stores, QR payloads, or logs.
