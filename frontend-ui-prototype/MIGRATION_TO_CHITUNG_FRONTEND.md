# Frontend Prototype Migration to Chitung Frontend

目标：把 `frontend-ui-prototype/ui-mockups-feishu-light` 的“最新原型风格”迁移到当前可运行代码（`chitung-frontend` + `chitung-center`）。

---

## 1) 结论

- `frontend-ui-prototype` 是 **最新静态原型源**（无 `package.json`，不可直接作为生产前端运行）。
- `chitung-frontend` 是 **正式运行前端**（Vue + Electron + 真实后端调用）。
- 迁移策略应是：**样式/交互抽取 + API 对齐**，不是直接拷贝 HTML。

---

## 2) 原型 -> 代码映射

| 原型页面（feishu-light） | 当前正式代码位置 | 状态 |
| --- | --- | --- |
| `01-工作台主页.html` | `src/pages/WorkbenchPage.vue` | 已迁移基础结构，需继续细化视觉 token |
| `02-隐患台账.html` | `src/components/hazards/HazardLedgerPanel.vue` | 已有功能基础，需对齐表格样式 |
| `03-视觉巡检.html` | `src/components/cards/CameraGrid.vue` | 已打通后端，需对齐卡片布局 |
| `04-智能填表.html` | `src/components/forms/FormTemplateBrowserPanel.vue` + `DocumentDiffPanel.vue` | 已打通流程，UI 可继续飞书化 |
| `05-WhatsApp消息管理.html` | （暂无独立页面） | 待迁移 |
| `06-整改通知.html` | `WorkbenchPage.vue` 通知确认片段 | 已有简版，待组件化 |
| `07-每日简报.html` | `WorkbenchPage.vue` + risk briefing 片段 | 已有简版，待丰富 |
| `08-风险雷达.html` | `WorkbenchPage.vue` 片段 | 待模块化 |
| `09-机械与LALG管理.html` | （暂无独立页面） | 待迁移 |
| `10-AI对话助手.html` | `CommandBar` + `HybridOrchestrationPanel` | 已有功能基础，待升级为独立视图 |

---

## 3) 与“最新后端代码”的对齐点

当前后端新增混合编排 API（`chitung-center/chitung_center/app.py`）：

- `POST /plan`
- `POST /confirm`
- `POST /execute`
- `POST /audit/event`
- `GET /plan/{plan_id}`

前端已接入：

- `src/services/chitungApi.ts` 已新增对应 client 方法
- `src/components/system/HybridOrchestrationPanel.vue` 已支持计划创建与分步执行
- `src/pages/WorkbenchPage.vue` 已完成事件绑定

---

## 4) 下一批迁移建议（按优先级）

### P0（本轮建议先做）

1. 把 `10-AI对话助手` 做成单独 Vue 页面（含对话历史左栏 + 右侧消息流）。
2. 把 `06-整改通知` 卡片抽成通用 `ReviewCard` 组件，复用到 `/confirm` 流程。
3. 把 `01-工作台主页` 的 design token 落到统一 CSS 变量文件，减少页面局部样式分散。

### P1

1. 新建 WhatsApp 管理页（对接 `list_whatsapp_groups/draft_group_message/send_group_message_with_confirm`）。
2. 新建风险雷达页（对接天气与外部风险工具链）。
3. 新建机械与 LALG 页（先做数据结构与筛选 UI，后接后端）。

### P2

1. 统一“进度链 + 审计ID + plan_id”显示，便于演示和排障。
2. 把所有确认动作切换成统一状态机视图（DRAFT -> ... -> SUCCEEDED/FAILED）。

---

## 5) 避坑说明

1. 不建议把静态 HTML 整页复制到 Vue；优先抽 Token、卡片、布局结构。
2. 不建议把 `plan -> confirm -> execute` 自动串跑；应保持分步手动确认，避免“卡住”感。
3. 不建议前端直接拿 key 调大模型；统一经 `chitung-center` 配置与网关。

---

## 6) 验收标准（迁移完成判定）

1. 原型关键交互在 Vue 中可运行（非静态展示）。
2. 每个交互至少有一个真实后端 API 对接。
3. 能拿到 `audit_id/plan_id/action_id` 并可回溯。
4. 页面风格与 `ui-mockups-feishu-light` 视觉一致度达到可演示级。
