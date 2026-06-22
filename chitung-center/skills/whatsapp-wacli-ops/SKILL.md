# WhatsApp wacli Ops

用自然语言执行安全的 WhatsApp `wacli` 只读命令，支持登录状态、诊断、消息搜索、聊天、群组、联系人、历史覆盖、存储和通话检查。

## Rules

- 只运行只读命令；不得发送、编辑、删除、撤回、转发消息，不得退出登录，不得切换账号，不得修改群组、联系人、频道或个人资料。
- 清理类命令只能使用 `--dry-run` 预览，不允许 `--confirm`。
- 优先使用结构化、限量输出，避免一次返回过多聊天内容。
- 涉及手机号、JID、群成员和消息内容时，只返回必要摘要。
- 如果用户要求写入或高风险操作，应说明当前 Skill 只支持只读诊断，并建议改到人工确认流程。

## Tools

- `whatsapp_command_run`
- `whatsapp_search`
- `whatsapp_groups_wacli`
