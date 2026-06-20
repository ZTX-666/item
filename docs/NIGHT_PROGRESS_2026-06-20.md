# 2026-06-20 夜间集成进度留痕

> 范围：非 RTMP / YOLO / VLM。视觉检测链路由另一 AI 负责，本批次未改相关文件。

## 批次目标

把昨晚预开发的 `confirmations` / `feishu_events` 工具接到三层栈，并补齐明天接线所需的最小中台、前端与回归脚本。

## 已完成

### 1. AgentToolbox 接入

| 文件 | 状态 | 说明 |
|------|------|------|
| `agent-toolbox/agent_toolbox/registry.py` | ✅ | 注册 13 个新 ToolSpec |
| `agent-toolbox/agent_toolbox/mcp_server.py` | ✅ | MCP `_call_tool` 分发 |
| `agent-toolbox/agent_toolbox/app.py` | ✅ | HTTP `/tools/*` 路由 13 条 |

### 2. 赤瞳中台服务层

| 文件 | 状态 | 说明 |
|------|------|------|
| `chitung-center/chitung_center/workflow_store.py` | ✅ 新增 | 工作流 run/step/artifact/event 薄封装 |
| `chitung-center/chitung_center/confirmation_service.py` | ✅ 新增 | 待确认 CRUD、卡片动作、批准执行 |
| `chitung-center/chitung_center/feishu_adapter_service.py` | ✅ 新增 | 飞书回调 → 解析 → 聊天/卡片确认 |
| `chitung-center/chitung_center/orchestrator.py` | ✅ | `handle_card_action` 接入确认流 |
| `chitung-center/chitung_center/models.py` | ✅ | `ConfirmationResolveApiRequest`、`FeishuEventWebhookRequest` |
| `chitung-center/chitung_center/app.py` | ✅ | `/api/confirmations`、`/api/confirmations/resolve`、`/integrations/feishu/events` |

### 3. 前端

| 文件 | 状态 | 说明 |
|------|------|------|
| `chitung-frontend/src/pages/PendingConfirmationsPage.vue` | ✅ 新增 | 待确认列表 + 批准/拒绝 |
| `chitung-frontend/src/services/chitungApi.ts` | ✅ | `getPendingConfirmations`、`resolvePendingConfirmation`、`sendCardAction` |
| `chitung-frontend/src/types/domain.ts` | ✅ | `PendingConfirmation` 类型 |
| `chitung-frontend/src/App.vue` | ✅ | 路由挂接 |
| `chitung-frontend/src/components/layout/Sidebar.vue` | ✅ | 「待确认」菜单 |
| `chitung-frontend/src/pages/WorkbenchPage.vue` | ✅ | 去掉硬编码 mock，后端失败时清空并留错 |

### 4. 回归与文档

| 文件 | 状态 | 说明 |
|------|------|------|
| `scripts/smoke_confirmation_flow.py` | ✅ 新增 | 直连 toolbox 的确认流冒烟 |
| `docs/NIGHT_TOOL_PREP_2026-06-20.md` | ✅ | 昨夜工具说明（仍有效） |
| `docs/NIGHT_PROGRESS_2026-06-20.md` | ✅ | 本文件 |

## API 速查（明天接线）

```text
GET  /api/confirmations?status=pending
POST /api/confirmations/resolve  { confirmation_id, decision, user_id?, notes? }
POST /api/chat/card-action       { action_id, card_data, user_id?, channel? }
POST /integrations/feishu/events { payload: <飞书原始事件> }
```

## 冒烟命令

```powershell
# 先启动 agent-toolbox (:8899)
python scripts/smoke_confirmation_flow.py
# 可选：指定地址
$env:AGENT_TOOLBOX_BASE_URL="http://127.0.0.1:8899"
```

## 仍待明天 / 后续（有意未做）

1. ~~**Workflow 编排器**~~ → **已补 P0 五模板 + `/api/workflows/*`**（2026-06-20 续）
2. ~~**飞书外发闭环**~~ → **未配置时本地归档 + `mark_executed(simulated)`**（不再误标 failed）
3. ~~**卡片 → 待确认页深链**~~ → **工作台卡片动作自动跳转待确认**
4. ~~**视觉页伪在线**~~ → **CameraGrid 去掉 fallback LIVE；未配置 RTMP 显示空状态**
5. **视觉 / RTMP / YOLO / VLM 模型链**：仅 UX 边界修复，检测脚本与权重环境仍由另一开发者推进

## 自检记录

- `python -m py_compile`：✅ 本批次相关 Python 文件通过
- 未改文件：`rtmp-tools`、`vlm-detection`、`secureeye_vlm`、`vlm_workflows.py`、`VisualPatrolPage.vue` 及视觉检测配置

## 变更时间线

- 23:xx — 完成 `confirmations.py` / `feishu_events.py` 初版
- 00:xx — 接入 registry / mcp_server
- 01:xx — 本批次：app.py 路由、中台三服务、前端待确认页、去 mock、冒烟脚本
