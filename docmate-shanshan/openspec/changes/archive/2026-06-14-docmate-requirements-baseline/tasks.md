## 1. 规范校验

- [x] 1.1 运行 `openspec validate docmate-requirements-baseline` 确保 proposal/design/specs/tasks 格式正确
- [x] 1.2 对照 v4.1.5 源码逐项确认已实现需求无遗漏（editor-core、ai-assistant 等）

## 2. 合并基线规范

- [x] 2.1 执行 `openspec archive docmate-requirements-baseline` 将 delta specs 写入 `openspec/specs/`
- [x] 2.2 确认 7 个 capability 目录均存在于 `openspec/specs/`

## 3. 项目指引

- [x] 3.1 在 README 增加 OpenSpec 工作流说明（init 已完成、斜杠命令用法）
- [x] 3.2 创建 `AGENTS.md`：开发约定、release 规则、spec 为需求真相源

## 4. 后续开发入口（Phase 2 候选 change）

- [ ] 4.1 为「连续对话改文档」创建独立 change（`/opsx-propose continuous-edit-dialogue`）
- [ ] 4.2 为「企业 ASR 替换 Web Speech」创建独立 change（`/opsx-propose enterprise-asr`）
- [ ] 4.3 为「快捷指令一键操作」创建独立 change（`/opsx-propose quick-commands`）
