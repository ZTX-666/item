## Context

DocMate 是 Electron + Vue 3 + Tiptap 的便携桌面文稿助手，面向机关/企业公文修改场景。当前 v4.1.5 已实现核心编辑与 AI 能力，但需求文档 `PROJECT_SPEC.md`（1330 行）与代码演进不同步，路线图 Phase 1 多项已勾选但未更新。

技术栈固定：Vue 3 + TypeScript 前端、`electron/*.cjs` 主进程代理 LLM、Tiptap/ProseMirror 编辑器、OpenAI 兼容 API。

## Goals / Non-Goals

**Goals:**

- 将产品能力拆为 7 个 OpenSpec 模块，每个模块有 SHALL 级需求与可测场景
- 标注实现状态，供后续 change 引用
- 固化「粘性选区 + Diff 采纳/拒绝 + 人机协同」为核心约束

**Non-Goals:**

- 本次不编写或修改业务代码
- 不启动 Phase 3 企业级功能（登录、审计、Word 导出）
- 不替换 Web Speech 为讯飞/腾讯云 ASR（留待独立 change）

## Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 需求真相源 | OpenSpec `openspec/specs/` | 与 Cursor `/opsx-*` 工作流集成；`PROJECT_SPEC.md` 降级为历史参考 |
| 模块划分 | 7 个 capability | 与源码目录（editor / ai / electron / scripts）大致对齐 |
| 规范粒度 | 用户可感知行为 + 关键边界 | 避免绑定具体函数名，便于 refactor |
| 待办管理 | spec 内标注 `[PLANNED]` 需求 | archive 后进入主 spec，apply 时按 tasks 逐项关闭 |

## Risks / Trade-offs

- **[Risk] PROJECT_SPEC 与 OpenSpec 双轨** → archive 本 change 后，新功能只改 OpenSpec delta，逐步废弃 PROJECT_SPEC 路线图章节
- **[Risk] 规范过细导致维护负担** → 仅对核心路径写 SHALL；实现细节留在 design/tasks
- **[Risk] 用户未重启 Cursor** → 斜杠命令需重启 IDE 后生效（init 已提示）

## Migration Plan

1. 完成本 change 全部 artifact → `/opsx-apply` 执行 tasks（仅文档同步，无代码）
2. `/opsx-archive` 将 delta specs 合并到 `openspec/specs/`
3. 后续每个功能：`/opsx-propose "功能名"` → apply → archive

## Open Questions

- Phase 2 中「连续对话改文档」与当前「问答模式」边界是否合并？
- 企业部署是否仍走便携 exe，还是独立安装包 + 云端同步？
