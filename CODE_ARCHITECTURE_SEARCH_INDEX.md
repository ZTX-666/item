# FinalAgentSuite Code Architecture Search Index

本文件用于两件事：

1. 快速看懂当前代码架构（前端/中台/工具层如何协作）。
2. 以后只靠一个 `md` 就能按功能搜索到相关代码位置。

---

## 1) 总体架构（当前可运行）

```text
chitung-frontend (Vue/Electron)
  -> chitung-center (orchestration + llm gateway + workflow api)
    -> agent-toolbox (HTTP/MCP tool execution)
      -> local tools/data (vlm, rtmp, whatsapp archive, sqlite, docs)
```

核心分层职责：

- `chitung-frontend`：工作台 UI、系统配置、交互确认入口。
- `chitung-center`：意图/流程编排、状态机、审计、统一 LLM 网关。
- `agent-toolbox`：工具执行统一网关（HTTP + MCP），对接本地能力。

---

## 2) 核心目录职责

### `chitung-frontend`

- 主页面：`chitung-frontend/src/pages/WorkbenchPage.vue`
- API 客户端：`chitung-frontend/src/services/chitungApi.ts`
- 类型定义：`chitung-frontend/src/types/domain.ts`
- 系统配置面板：`chitung-frontend/src/components/system/SystemSettingsPanel.vue`
- 混合编排面板（新）：`chitung-frontend/src/components/system/HybridOrchestrationPanel.vue`

### `chitung-center`

- API 聚合入口：`chitung-center/chitung_center/app.py`
- 混合编排状态机（新）：`chitung-center/chitung_center/hybrid_orchestration.py`
- 传统聊天编排：`chitung-center/chitung_center/orchestrator.py`
- 中台模型网关：`chitung-center/chitung_center/llm_gateway.py`
- 中台审计：`chitung-center/chitung_center/audit.py`
- 调用工具层客户端：`chitung-center/chitung_center/toolbox_client.py`

### `agent-toolbox`

- API 入口：`agent-toolbox/agent_toolbox/app.py`
- 工具目录：`agent-toolbox/agent_toolbox/tools/`
- 工具注册：`agent-toolbox/agent_toolbox/registry.py`
- MCP 工具入口：`agent-toolbox/agent_toolbox/mcp_server.py`
- 命令执行器：`agent-toolbox/agent_toolbox/runner.py`

---

## 3) 核心 API（中台）

文件：`chitung-center/chitung_center/app.py`

- 运行与配置
  - `GET /health`
  - `GET /api/runtime/status`
  - `GET/POST /api/settings/llm`
  - `GET/POST /api/settings/connectors`
- 聊天与业务流程
  - `POST /api/chat/message`
  - `POST /api/chat/card-action`
  - `POST /api/forms/smart-draft`
  - `POST /api/visual/patrol-draft`
- 混合编排（新增）
  - `POST /plan`
  - `POST /confirm`
  - `POST /execute`
  - `POST /audit/event`
  - `GET /plan/{plan_id}`

---

## 4) 核心 API（工具层）

文件：`agent-toolbox/agent_toolbox/app.py`

高频工具接口（节选）：

- 风险天气：`/tools/fetch_hko_weather`, `/tools/fetch_hk_safety_updates`, `/tools/draft_daily_risk_briefing`
- 隐患流程：`/tools/ingest_chat_hazards`, `/tools/connect_hazard_actions`
- 表格流程：`/tools/search_form_templates`, `/tools/prefill_form_fields`, `/tools/generate_docx_from_template`
- 视觉流程：`/tools/capture_camera_snapshot`, `/tools/run_vlm_detection_batch`, `/tools/create_case_from_vlm`
- 飞书：`/tools/notify_feishu`, `/integrations/feishu/events`

---

## 5) 混合编排状态机（Codex + Chitung）

文件：`chitung-center/chitung_center/hybrid_orchestration.py`

状态：

`DRAFT -> PLANNED -> PENDING_CONFIRMATION -> CONFIRMED -> EXECUTING -> SUCCEEDED/FAILED`

强约束：

- 未确认动作禁止执行。
- Codex 仅返回 `proposed_actions`，不直接执行工具。
- 所有状态转移和工具调用写审计（含 `session_id/plan_id/action_id/audit_id`）。

相关文档：`chitung-center/docs/CODEX_CHITUNG_HYBRID_MVP.md`

---

## 6) “按功能找代码”速查表

| 你要改什么 | 先看这些文件 |
| --- | --- |
| 聊天回复逻辑 | `chitung-center/chitung_center/orchestrator.py`, `intent_router.py` |
| Codex 混合编排 | `chitung-center/chitung_center/hybrid_orchestration.py`, `app.py` |
| 中台模型配置保存 | `chitung-center/chitung_center/settings_service.py`, `config.py` |
| 前端聊天按钮行为 | `chitung-frontend/src/pages/WorkbenchPage.vue`, `services/chitungApi.ts` |
| 表格生成流程 | `chitung-center/chitung_center/smart_form_service.py`, `agent-toolbox/.../tools/forms.py` |
| 视觉巡检流程 | `chitung-center/chitung_center/visual_patrol_service.py`, `agent-toolbox/.../tools/vlm_workflows.py` |
| 飞书事件接入 | `agent-toolbox/agent_toolbox/tools/feishu.py`, `app.py` |
| 审计日志字段 | `chitung-center/chitung_center/audit.py`, `hybrid_orchestration.py` |

---

## 7) 推荐搜索关键词（直接用 rg）

> 目标：让后续维护者不用遍历目录，按关键词直达代码。

- 混合编排：`/plan`, `PENDING_CONFIRMATION`, `idempotency_key`, `retry_failed_only`
- 审计链路：`audit_id`, `write_audit`, `tool_call_requested`
- 规则降级：`rule_fallback`, `fallback_used`, `planner_mode`
- 表格链路：`smart-draft`, `prefill_form_fields`, `generate_docx_from_template`
- 视觉链路：`patrol-draft`, `run_vlm_detection_batch`, `create_case_from_vlm`
- 飞书链路：`feishu`, `integrations/feishu/events`, `send_interactive_card`

---

## 8) 当前 review 结论（核心）

1. 架构边界清晰：UI / 编排 / 执行 三层已成立。
2. `agent-toolbox` 工具覆盖很广，但部分工具仍是占位语义（需按业务优先级补实）。
3. `chitung-center` 传统聊天编排与新混合编排并存，后续建议统一入口策略，避免双轨维护复杂度上升。
4. 前端已接入混合编排面板，建议后续将 `plan/confirm/execute` 的状态与主工作台进度条进一步合并。

---

## 9) 迁移建议（前端原型 -> 正式前端）

原型目录：`frontend-ui-prototype/ui-mockups-feishu-light/`

建议采用“组件迁移 + 后端对齐”策略：

1. 先迁 `10-AI对话助手` 交互卡片到现有 Vue 组件。
2. 再迁 `01-工作台主页` 的布局 token 到 `WorkbenchPage.vue`。
3. 对每个迁移模块绑定真实 API，而不是仅复制静态 HTML。

详细迁移表见：`frontend-ui-prototype/MIGRATION_TO_CHITUNG_FRONTEND.md`
