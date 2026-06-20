# DocMate Agent 开发约定

> 需求真相源：`openspec/specs/`（OpenSpec 规范）。`PROJECT_SPEC.md` 为历史参考，新功能以 OpenSpec change 为准。

## 产品定位

DocMate（闪闪文档）— 语音/文字驱动的便携桌面文稿修改助手，面向机关/企业公文场景。**人机协同**：AI 只提建议，用户采纳/拒绝后替换。

## 核心约束（不可妥协）

1. **粘性选区**：选中文字保持蓝色高亮，点击 AI 面板不取消；再次点击选区才取消
2. **Diff 预览**：AI 修改必须先展示对比，用户明确采纳/拒绝
3. **API Key 安全**：LLM 调用在 `electron/` 主进程，不暴露到前端
4. **便携数据**：便携模式下数据在 exe 同目录 `DocMateData/`

## 技术栈

- Vue 3 + TypeScript + Tiptap（`src/`）
- Electron 主进程（`electron/*.cjs`）
- OpenAI 兼容 LLM API

## 开发命令

```bash
npm install
npm run electron:dev   # 热更新开发
npm start              # 生产模式启动
npm run pack           # 打包便携 exe
npm run release        # 版本 patch +1，构建并同步 publish8/
```

**功能性代码变更后必须执行 `npm run release`**（见 `.cursor/rules/auto-release.mdc`）。

## OpenSpec 工作流（Cursor）

| 命令 | 用途 |
|------|------|
| `/opsx-propose <描述>` | 新建变更，生成 proposal / design / specs / tasks |
| `/opsx-apply` | 按 tasks.md 实现 |
| `/opsx-archive` | 完成后归档，合并 spec 到 `openspec/specs/` |
| `/opsx-explore` | 探索想法，暂不立项 |

能力模块见 `openspec/specs/`：`editor-core`、`ai-assistant`、`voice-input`、`file-workspace`、`llm-config`、`knowledge-base`、`packaging-release`。

## 关键源码

| 模块 | 路径 |
|------|------|
| 编辑器 + 粘性选区 | `src/components/EditorPanel.vue`, `src/composables/useStickySelection.ts` |
| AI 面板 | `src/components/AiPanel.vue` |
| 编辑器 AI / Diff | `src/composables/useEditorAi.ts` |
| LLM 与 Agent | `electron/ai-services.cjs`, `electron/intent-router.cjs` |

## Phase 2 待办（见 spec 中 [PLANNED]）

- 连续对话改文档
- 企业 ASR 替换 Web Speech
- 快捷指令一键操作
