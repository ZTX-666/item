## Why

DocMate（闪闪文档）已迭代至 v4.1.5，功能分散在 `PROJECT_SPEC.md`、README 与源码注释中，缺少与 Cursor/OpenSpec 对齐的**单一需求真相源**。引入 OpenSpec 后，需要先把现有能力与待办项梳理成可执行的规范基线，后续每次功能变更才能按 propose → apply → archive 流程推进，避免 AI 开发时偏离产品方向。

## What Changes

- 建立 DocMate 产品能力规范基线（按模块拆分 spec）
- 对照 `PROJECT_SPEC.md` 路线图，标注**已实现 / 部分实现 / 未实现**
- 明确核心交互原则（粘性选区、人机协同、Diff 采纳/拒绝）为不可妥协约束
- 列出 Phase 2–4 待办优先级，供后续 OpenSpec 变更引用
- 不修改运行时行为；本次变更仅产出规划文档

## Capabilities

### New Capabilities

- `editor-core`: Tiptap 编辑器、粘性选区、Diff 高亮、手动编辑与 AI 修改并存
- `ai-assistant`: 修改/润色/问答/风险/口语转正式/智能表格及意图路由
- `voice-input`: 语音输入（Web Speech + Electron 转写）
- `file-workspace`: 便携工作区、文件树、导入/新建/保存
- `llm-config`: 在线大模型配置、连接测试、离线模拟
- `knowledge-base`: 用户知识库注入 Prompt
- `packaging-release`: Electron 便携版打包与 publish 同步流程

### Modified Capabilities

（无——`openspec/specs/` 尚无既有规范，全部为新建基线）

## Impact

- 新增 `openspec/specs/` 下 7 个能力规范文件
- 后续功能开发以 delta change 修改对应 spec，而非直接改 `PROJECT_SPEC.md`
- 与 Cursor 斜杠命令（`/opsx-propose`、`/opsx-apply`）形成闭环
- 不影响 `src/`、`electron/` 源码与 `npm run release` 流程
