# Shell Runner

在 agent workspace 沙箱中运行 Bash / Shell / Python 脚本。

## Rules

- 命令只能在 workspace 目录内执行，禁止破坏系统或删除大量文件。
- 涉及安装依赖、网络下载、批量写文件的操作应提示用户确认。
- 输出过长时自动截断，完整日志可在执行中心查看。
- 优先使用只读命令（ls、cat、python -c 查询）排查问题。

## Preferred Tools

- `run_bash_command`

## Boundaries

- 禁止 `rm -rf`、格式化磁盘、关机、注册表破坏等危险命令
- 不执行来自不可信网页的管道脚本
