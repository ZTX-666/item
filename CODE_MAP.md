# Code Map

This document explains how the final code pieces relate to each other.

## 1. AgentToolbox

Path: `agent-toolbox`

AgentToolbox is the integration layer. It exposes local tools through:

- HTTP API: `run_server.py`
- MCP stdio adapter: `run_mcp.py`

Important files:

- `agent_toolbox/app.py`: FastAPI routes.
- `agent_toolbox/mcp_server.py`: MCP `tools/list` and `tools/call` implementation.
- `agent_toolbox/registry.py`: tool metadata and health checks.
- `agent_toolbox/tools/rtmp.py`: wrapper for RTMP screenshots.
- `agent_toolbox/tools/vlm.py`: wrapper for YOLO/VLM detection.
- `agent_toolbox/tools/whatsapp.py`: wrapper for WhatsApp archive backend.
- `agent_toolbox/tools/report.py`: wrapper for Word report generation.
- `agent_toolbox/tools/feishu.py`: Feishu webhook notification wrapper.
- `.env.example`: paths and ports.

AgentToolbox should be treated as the single entry point for external agents.

## 2. WhatsApp Archive

Path: `whatsapp-archive`

Subprojects:

- `app-server`: Node/Express backend.
- `app-web`: Vite/TypeScript browser UI.

Backend role:

- Reads local `whatscli` SQLite data.
- Provides chat list, message search, media serving, and media download APIs.

Important backend APIs:

- `GET /api/health`
- `GET /api/chats`
- `GET /api/messages`
- `GET /api/messages/search`
- `GET /api/media`
- `POST /api/media/download`

AgentToolbox calls `app-server` through HTTP.

## 3. Chitong Lingxun

Path: `chitong-lingxun`

Chitong Lingxun is the latest copied core source for the WPF WhatsApp desktop client.

Latest baseline:

- `publish3.0`

Important folders:

- `WacliDesktop`: WPF desktop client, product name `赤瞳灵讯`.
- `WacliDesktopLauncher`: launcher project.
- `cloud-sync-api`: FastAPI + MySQL cloud sync receiver.
- `hiagent-local-test`: local HiAgent bridge test scripts.
- `runtime-samples`: copied runtime config samples, excluding binary `runtime/bin`.

Important files:

- `publish3.0-memory.md`: latest UI and connection-state handoff note.
- `publish23-memory.md`: default database root and migration note.
- `publish20-memory.md`: cloud sync API and deployment note.
- `build-publish3.0.ps1`: latest build script.

Original runnable package:

```text
J:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\source\publish3.0
```

## 4. DocMate Shanshan

Path: `docmate-shanshan`

DocMate Shanshan is the latest copied core source for `DocMate / 闪闪文档`.

Version:

- `4.1.37`

Important folders:

- `src`: Vue 3 frontend and editor UI.
- `electron`: Electron main process, preload, AI services, file operations, export logic.
- `scripts`: release and publish scripts.
- `public`: app assets.
- `openspec`: product requirements and change records.

Important files:

- `package.json`: Electron/Vue/Tiptap dependencies and scripts.
- `HANDOFF_2026-06-15.md`: latest handoff note.
- `AGENTS.md`: development conventions.

Original runnable package:

```text
E:\ChinaOverseas Final\publish4\publish100\DocMate.vbs
```

Original portable executable:

```text
E:\ChinaOverseas Final\publish4\release\DocMate闪闪文档 4.1.37.exe
```

## 5. VLM Detection

Path: `vlm-detection`

Main entry:

- `detect.py`

Inputs:

- Single image path or image directory.
- Optional confidence threshold and device.

Outputs:

- Annotated images.
- `detections_*.json`

AgentToolbox calls this script through a subprocess and stores each run under its task workspace.

## 6. RTMP Tools

Path: `rtmp-tools`

Main entry:

- `rtmp_snapshot.py`

Inputs:

- RTMP URL.
- Count, interval, prefix, retry options.

Outputs:

- JPEG screenshots.

AgentToolbox calls this script through a subprocess.

## 7. Report Generators

Path: `report-generators`

Main entry:

- `generate_community_doc.py`

AgentToolbox imports `build_document()` from this file and saves the generated Word file into the task workspace. This avoids relying on the script's original hard-coded output path.

## Recommended Development Direction

Future tools should follow the same pattern:

1. Keep the original software focused on its own business logic.
2. Add a small wrapper under `agent-toolbox/agent_toolbox/tools`.
3. Register the tool metadata in `agent_toolbox/registry.py`.
4. Expose it through HTTP and MCP.
5. Let Feishu or other agent platforms call AgentToolbox, not the original software directly.
