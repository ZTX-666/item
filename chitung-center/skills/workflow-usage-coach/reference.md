# 工作流使用参考

## Chat 即时工作流

| workflow_name | 标题 | Chat 示例 |
|---------------|------|-----------|
| workflow_daily_risk_briefing | 每日外部风险简报 | 生成今日外部风险简报 |
| workflow_knowledge_query | 制度条款检索 | 临边作业制度要求 |
| workflow_visual_patrol | 视觉巡检 | 对现场照片做安全检测 |
| workflow_hazard_intake | 隐患 intake | 这里有护栏缺失隐患 |
| workflow_docmate_edit | DocMate 编辑 | 润色这份 docx |

## 含确认点的工作流（演示亮点）

- 任何 `requires_confirmation` 步骤 → 必须展示 `#/guardian/confirmations`
- 失败时常见原因：LLM 超时、工具不可用、用户拒绝确认

## 验收清单模板

- [ ] Chat 有 reply + cards
- [ ] `#/center/execution` 出现 agent_workflow job 且 success
- [ ] 待确认卡片可打开（如适用）
- [ ] 引用/报告内容符合预期

## 演示保守策略

- 优先跑本地记录里 success 次数多的 workflow
- 视觉用样例图；外部抓取展示历史卡片
