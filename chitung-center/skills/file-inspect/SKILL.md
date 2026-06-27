# File Inspect

读取 workspace 及允许目录内的本地文件，支持代码、PDF、DOCX、Jupyter、Office 文本等。

## Rules

- 只能读取配置允许的路径根目录下的文件，禁止越权访问。
- 大文件与二进制文件返回摘要；图片文件提示使用 OCR 工具。
- 读取制度、报告、日志时，应提取与安全问题相关的段落，不要原样 dump 全文到聊天窗口。
- 目录请求返回文件列表，便于用户选择下一步操作。

## Preferred Tools

- `read_local_file`

## Boundaries

- 不写入或修改文件（写入请走 DocMate / 智能填表流程）
- 不读取 `.env`、密钥、私钥等敏感文件（即使路径可达也应拒绝展示）
