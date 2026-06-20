# 2026-06-20 夜间预开发工具说明

> 范围：仅新增非 RTMP / YOLO / VLM 工具准备代码。未修改视觉检测链路、RTMP 脚本、YOLO/VLM 配置、`vlm_workflows.py` 或视觉前端页面。

## 1. 新增文件

### `agent-toolbox/agent_toolbox/tools/confirmations.py`

用途：为明天的人工确认闭环和 Workflow Engine 提供本地 SQLite 工具。

已包含：

- `workflow_runs`
- `workflow_steps`
- `pending_confirmations`
- `workflow_artifacts`
- `workflow_event_links`

主要函数：

- `init_workflow_confirmation_schema`
- `create_workflow_run`
- `append_workflow_step`
- `update_workflow_step`
- `create_pending_confirmation`
- `query_pending_confirmations`
- `resolve_pending_confirmation`
- `record_workflow_artifact`
- `link_workflow_event`

已提供 `CONFIRMATION_TOOL_SPECS`，明天可直接接入 `registry.py`。

### `agent-toolbox/agent_toolbox/tools/feishu_events.py`

用途：为飞书自然语言入口和卡片按钮回调提供解析工具。

主要函数：

- `feishu_parse_message_event`
- `feishu_parse_card_action`
- `feishu_event_to_platform_message`
- `feishu_build_center_route_payload`

已提供 `FEISHU_EVENT_TOOL_SPECS`，明天可直接接入 `registry.py`。

## 2. 明天接入建议

### 2.1 注册 ToolSpec

在 `agent-toolbox/agent_toolbox/registry.py` 中追加：

```python
from .tools.confirmations import CONFIRMATION_TOOL_SPECS
from .tools.feishu_events import FEISHU_EVENT_TOOL_SPECS
```

并在 `tool_specs()` 返回值末尾追加：

```python
return (
    specs
    + ALL_DOCMATE_SPECS
    + CONFIRMATION_TOOL_SPECS
    + FEISHU_EVENT_TOOL_SPECS
    + future_tool_specs()
    + workflow_tool_specs()
)
```

### 2.2 接入 `_call_tool`

在 `agent-toolbox/agent_toolbox/mcp_server.py` 和 HTTP `/tools/{tool_name}` 使用的分发逻辑中增加：

```python
from .tools.confirmations import (
    WorkflowSchemaInitRequest,
    WorkflowRunCreateRequest,
    WorkflowStepAppendRequest,
    WorkflowStepUpdateRequest,
    PendingConfirmationCreateRequest,
    PendingConfirmationQueryRequest,
    PendingConfirmationResolveRequest,
    WorkflowArtifactRecordRequest,
    WorkflowEventLinkRequest,
    init_workflow_confirmation_schema,
    create_workflow_run,
    append_workflow_step,
    update_workflow_step,
    create_pending_confirmation,
    query_pending_confirmations,
    resolve_pending_confirmation,
    record_workflow_artifact,
    link_workflow_event,
)
from .tools.feishu_events import (
    FeishuMessageParseRequest,
    FeishuCardActionParseRequest,
    FeishuPlatformMessageRequest,
    FeishuCenterRoutePayloadRequest,
    feishu_parse_message_event,
    feishu_parse_card_action,
    feishu_event_to_platform_message,
    feishu_build_center_route_payload,
)
```

建议先只接以下 P0 工具：

```text
init_workflow_confirmation_schema
create_pending_confirmation
query_pending_confirmations
resolve_pending_confirmation
feishu_parse_message_event
feishu_parse_card_action
feishu_build_center_route_payload
```

### 2.3 中台接线顺序

建议顺序：

1. 飞书回调先调用 `feishu_build_center_route_payload`。
2. 将返回的 `center_payload` POST 到 `chitung-center /api/chat/message`。
3. 中台生成高风险动作时调用 `create_pending_confirmation`。
4. 本地前端或飞书卡片按钮调用 `resolve_pending_confirmation`。
5. 确认后再执行真实工具，例如发送飞书、生成整改通知、关闭案件。

## 3. MVP 数据流

```text
飞书消息
  -> feishu_parse_message_event
  -> feishu_build_center_route_payload
  -> chitung-center /api/chat/message
  -> create_workflow_run
  -> append_workflow_step
  -> create_pending_confirmation
  -> 飞书/本地确认卡
  -> feishu_parse_card_action
  -> resolve_pending_confirmation
  -> 执行真实业务工具
  -> record_workflow_artifact / link_workflow_event
```

## 4. 注意事项

- 当前新增工具默认使用 `settings.safety_database_path`。
- 当前新增工具不会主动发送飞书消息。
- 当前新增工具不会调用 RTMP / YOLO / VLM。
- `resolve_pending_confirmation(decision="approve")` 只表示人工批准，真实业务动作仍应由中台下一步执行。
- 建议明天先把确认状态和实际执行解耦：`approved -> executing -> executed/failed`。
