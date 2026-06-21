## Why

用户反馈 AI 返回多个修改方案后，点击采纳无法正确写回原文。根因是：① 后端默认生成 3 个方案但前端只展示第一个；② 采纳时用 `old_text` 字符串匹配定位，与粘性选区坐标不一致时替换失败。产品策略应改为「一锤定音」——每次只输出一个最佳修改版本，采纳时优先用选区坐标直接替换。

## What Changes

- AI 修改/润色/口语转正式仅返回 **1 个最终方案**（移除多方案设置）
- 后端 `old_text` 优先使用用户选中文本，避免 LLM 定位偏差
- 前端采纳时 **直接用 lockFrom/lockTo 坐标替换**，不再依赖字符串二次匹配
- `resolveReplaceRange` 在有有效 hint 时信任坐标
- 新增 `scripts/test-revision-replace.cjs` 自动化验证

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `editor-core`: 采纳 AI 修改时必须用选区坐标可靠写回文档
- `ai-assistant`: 修改类任务只返回一个最终方案，不再提供多选项

## Impact

- `electron/ai-services.cjs`, `electron/llm.cjs`
- `src/composables/useEditorAi.ts`, `src/utils/editorReplace.ts`
- `src/components/ModelSettingsModal.vue`
- `openspec/specs/editor-core`, `openspec/specs/ai-assistant`
