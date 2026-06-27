# 自动化使用参考

## 自动化类工作流模板

| workflow_name | 标题 | 确认步骤 |
|---------------|------|----------|
| workflow_daily_safety_briefing_auto | 每日安全简报自动化 | 简报草稿 + 发送确认 |
| workflow_p1_external_info_alert | P1 外部讯息提醒 | 待确认 + 告警发送 |
| workflow_visual_patrol_closed_loop | 视觉巡检闭环 | 草稿 + 整改 + 复查 |
| workflow_whatsapp_risk_ingestion | WhatsApp 风险入库 | 分类 + 待确认 |

## Automation 页面（前端）

- 路由：`#/center/automation`
- 本地存储键：
  - `chitung.automation.tasks.v2` — 任务定义
  - `chitung.automation.runs.v2` — 运行记录
- 建议流程：模板 → 填 prompt/schedule → 保存 → 手动运行 → 再启用定时

## RRULE / 调度（初学者）

- 演示日：先用「每 6 小时」或「手动运行」，避免等太久
- 保存后若未运行：检查任务开关、浏览器是否关页（本地 scheduler 依赖页面）

## 验收清单

- [ ] Automation 页能看到任务且已启用
- [ ] 手动运行产生 run 记录
- [ ] 执行中心有对应 job（若已接后端）
- [ ] 需确认的步骤出现在待确认页

## 与工作流教练分工

- 问「Chat 怎么触发一次」→ 转 **工作流使用教练**
- 问「Skill 是什么」→ 转 **Skill 使用教练**
