## Context

当前修改链路：选区 → AI 返回 `{ old_text, options[] }` → 内联 Diff 预览 → 采纳 → `applyReplacement(oldText, newText, hint)`。当 `old_text` 与编辑器内实际 slice 不完全一致时，`resolveReplaceRange` 拒绝 hint 并回退文本搜索，导致采纳失败。

## Goals / Non-Goals

**Goals:**
- 每次修改只产出一个可直接采纳的最终版本
- 有粘性选区时，采纳 100% 用坐标替换
- 有自动化测试覆盖 normalize + 文本对齐

**Non-Goals:**
- 不恢复 OptionPicker 多方案 UI
- 不改 QA/风险扫描流程

## Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 方案数量 | 固定 1 | 用户明确要求一锤定音 |
| old_text 来源 | 选中文本 > LLM 对齐 | 选区是 ground truth |
| 替换定位 | hint 坐标优先 | 避免 fuzzy match 失败 |
| 设置 UI | 移除「方案数量」 | 防止误配 |

## Risks / Trade-offs

- **[Risk] 用户曾保存 optionCount=3 的设置** → 加载后强制 clamp 为 1
- **[Risk] 无选区时仍依赖 old_text 对齐** → 保留 alignOldText + findRangeInDocument 回退
