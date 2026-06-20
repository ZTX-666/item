## 1. 后端

- [x] 1.1 normalizeRevisionResult 优先使用 selected_text 作为 old_text，且只保留 1 个 option
- [x] 1.2 修改 revise/polish/oral prompt 为「生成 1 个最佳最终版本」

## 2. 前端替换

- [x] 2.1 resolveReplaceRange 在有有效 hint 时直接信任坐标
- [x] 2.2 acceptReview 用 lockFrom/lockTo 直接 replaceDocumentRange
- [x] 2.3 showInlineReview 用文档 slice 作为 review.oldText

## 3. 设置与测试

- [x] 3.1 移除 ModelSettingsModal 多方案数量选项，默认 optionCount=1
- [x] 3.2 新增 scripts/test-revision-replace.cjs 并运行通过
- [x] 3.3 openspec validate + archive
