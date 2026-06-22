# WhatsApp SQLite Query

用自然语言读取本地 WhatsApp `wacli.db`，查看表名、消息、聊天、联系人、群组、通话和状态数据。

## Rules

- 只允许只读查询；不得执行 INSERT、UPDATE、DELETE、DROP、ALTER、PRAGMA、VACUUM 或多语句 SQL。
- 默认读取本地 `wacli.db`，不要读取或展示 `session.db` 的会话密钥内容。
- 用户明确给出 SELECT 时，保留其查询意图并限制返回行数。
- 用户没有给出 SQL 时，根据问题选择安全预设查询：表名、最新消息、聊天列表、联系人、群组、通话或状态。
- 回复先说明查询结果数量和字段，再提示可到 WhatsApp 控制台继续检查。

## Tools

- `whatsapp_sql_tables`
- `whatsapp_sql_query`
