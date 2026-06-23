# Long Term Memory

把当天与闪闪助手的关键对话压缩成长期记忆，并写入统一 Markdown 记忆文档。

## Rules

- 只记录长期有价值的内容：用户偏好、项目命名、架构决策、已完成能力、待验证风险和后续方向。
- 不记录 API key、token、密码、私人身份信息或一次性日志。
- 总结必须精简，优先使用中文 Markdown bullet。
- 所有长期记忆共用一个本地文档：`chitung-center/data/long_term_memory.md`。

## Trigger

- 用户说“发动长期记忆技能”“总结今日对话”“记住今天”“更新长期记忆”等。
- 技能会读取今日本地聊天记录，压缩后写入长期记忆文档。

## Tools

- `long_term_memory_read`
- `long_term_memory_save`
- `long_term_memory_summarize_today`

## Frontend

- 赤瞳中台新增“长期记忆”页面，可查看和手动编辑 Markdown。
- 闪闪助手后续交互会自动带入长期记忆摘要作为上下文。
