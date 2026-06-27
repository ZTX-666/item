# Skill 使用参考

## 内置 Skill 速查（赤瞳 Version4）

| display_name | skill name | 典型触发 |
|--------------|------------|----------|
| 制度知识问答 | knowledge-query | 制度、规程、知识库 |
| 每日风险简报 | daily-risk-briefing | 外部风险、简报 |
| 外部讯息监听 | external-info-monitor | 监听关键词、立即监听 |
| 长期记忆 | long-term-memory | 总结今日对话 |
| 视觉巡检 | visual-patrol | 摄像头、图片检测 |
| DocMate 编辑 | docmate-edit | docx 修改 |
| WhatsApp 运维 | whatsapp-wacli-ops | wacli 状态 |

## 本地 job 与 Skill 的关系

- `skill_test` job：用户在 Skill 页点「测试」
- `source_module` 映射：如 `rag` → knowledge-query
- Chat 成功应用 Skill 时，audit 可能有 `skill_applied` 事件

## 常见问题

**Q：Skill 和工作流区别？**  
A：Skill 是「怎么说、怎么回」；工作流是「一步步调工具」。

**Q：能否在对话里新建 Skill？**  
A：教练不能生成文件；请去 Skill 页「导入」Markdown，或使用内置 Skill。

**Q：Skill 停用会怎样？**  
A：路由仍可能识别，但 orchestrator 会提示已停用。
