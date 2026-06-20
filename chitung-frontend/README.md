# Chitung Frontend

赤瞳安全智能平台正式桌面工作台。界面基于 `frontend-ui-prototype/ui-mockups-feishu-light` 抽取，交付形态优先定义为 Electron 桌面软件，而不是浏览器网页。

## 技术栈

- Electron
- Vue 3
- Vite
- TypeScript

## 运行桌面开发版

```powershell
cd "J:\China Oversea  Final\FinalAgentSuite\chitung-frontend"
npm install
copy .env.example .env
npm run desktop:dev
```

默认连接 `FinalAgentSuite\chitung-center`：

```text
http://127.0.0.1:8999
```

验证前后端是否打通：

```powershell
npm run smoke:backend
```

该命令会检查 `/health`、`/api/runtime/status`、`/api/workbench/summary` 和 `/api/settings/llm`。

## 构建

```powershell
npm run build
npm run desktop:build
```

`desktop:build` 会生成 Electron 目录构建；正式安装包使用 `npm run desktop:dist`。

## 桌面本地服务

Electron 启动时会先检查：

```text
http://127.0.0.1:8899/health
http://127.0.0.1:8999/health
```

如果 AgentToolbox 或 Chitung Center 未运行，桌面壳会尝试自动启动：

```text
FinalAgentSuite\agent-toolbox\run_server.py
FinalAgentSuite\chitung-center\run_server.py
```

设置 `CHITUNG_AUTOSTART_SERVICES=false` 可关闭自动启动。日志写入 Electron `userData/service-logs`。

`build/app-icon.svg` 是当前临时图标源文件；正式 Windows 安装包建议导出为 `.ico` 后再配置到 `electron-builder`。

## 模型调用边界

前端只允许调用 `chitung-center`，不保存任何大模型 Key。

```text
chitung-frontend
  -> VITE_CHITUNG_CENTER_URL
  -> chitung-center LLM Gateway
  -> 统一大模型 API
```

`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 只应配置在 `FinalAgentSuite\chitung-center\.env`。

桌面工作台提供“系统设置”面板，可保存统一大模型 API。配置会写入本机 `chitung-center\.env`，并立即刷新中台运行状态。

## AI 文档改写交互

文档写作和填表参考 DocMate / 闪闪文档模式：

- AI 先生成修改预览，不直接覆盖正式文档。
- 删除内容用红色 `-` 行展示，新增内容用绿色 `+` 行展示。
- 面板顶部显示 Cursor 式 `+N`、`-N` 修改统计。
- 高风险文档动作必须人工点击“采纳修改”后才进入正式写入流程。
- “拒绝”和“重新生成”保留为一等操作，便于现场安全主任审核。

## 智能填表流程

桌面工作台的“智能填表”按钮调用 `chitung-center`：

```text
POST /api/forms/smart-draft
  -> search_form_templates
  -> prefill_form_fields
  -> generate_docx_from_template(record=false)
  -> DocumentDiffPanel
  -> 人工采纳
  -> POST /api/forms/accept-draft
  -> export_form_record(status=accepted)
```

草稿阶段会生成 DOCX 草稿路径和字段预填结果，但不会写入正式表单记录。

## 视觉巡检流程

```text
POST /api/visual/patrol-draft
  -> capture_camera_snapshot
  -> run_vlm_detection_batch
  -> 生成视觉隐患候选
  -> 人工确认
  -> POST /api/visual/confirm-candidate
  -> create_case_from_vlm
```

候选阶段不直接入库，只有人工点击“确认入库”后才创建隐患 case。

## 隐患闭环后半段

活跃隐患列表支持：

- `POST /api/cases/rectification-notice`：生成整改通知草稿。
- `POST /api/cases/contractor-confirm`：记录分包商确认和期限。
- `POST /api/cases/close-review`：复查后关闭隐患。

## 当前已完成

- Electron `main` / `preload` 桌面壳
- `AppShell`
- `TopBar`
- `Sidebar`
- `CommandBar`
- `StatusStrip`
- `CameraGrid`
- `ActiveHazards`
- `ProgressChain`
- `ActivityFeed`
- `DocumentDiffPanel`
- Smart form draft / accept flow
- `WorkbenchPage`
- `chitungApi` client

## 下一步

1. 增加工作流 SSE 或轮询接口，驱动 `ProgressChain`。
2. 将隐患、摄像头、活动流 mock 数据替换为 `chitung-center` API。
3. 组件化 10 个 UI 原型页面。
4. 接入隐患台账、视觉巡检、智能填表三个优先工作流。
