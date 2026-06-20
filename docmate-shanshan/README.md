# 文稿修改助手 — 源代码包 (v1.1.1)

本目录为**完整源代码**，可复制到另一台电脑继续开发。

## 环境要求

- Node.js 18+（推荐 20 LTS）
- npm 9+

## 快速开始

```bash
# 1. 进入目录
cd publish3

# 2. 安装依赖
npm install

# 3. 构建前端
npm run build

# 4. 启动桌面应用
npm start
```

## 开发模式（热更新）

```bash
npm run electron:dev
```

需同时启动 Vite 开发服务器和 Electron。

## 打包可执行程序

```bash
# 输出到 release/win-unpacked/
npm run pack

# 复制到 publish2 发布目录
npm run publish2
```

## 项目结构

```
publish3/
├── src/                 # Vue 3 前端源码
│   ├── components/      # UI 组件（编辑器、Agent 面板等）
│   ├── composables/     # 组合式逻辑
│   ├── api/             # AI 接口封装
│   └── styles/          # Cursor 风格主题
├── electron/            # Electron 主进程
│   ├── main.cjs         # 窗口、IPC、文件系统
│   ├── preload.cjs      # 安全桥接
│   ├── llm.cjs          # 大模型调用
│   └── ai-services.cjs  # 修改/润色/问答/风险等
├── scripts/             # 打包脚本
├── package.json
└── vite.config.ts
```

## 主要功能模块

| Agent 模式 | 源码位置 |
|-----------|----------|
| 修改 | `electron/ai-services.cjs` → `processRevise` |
| 润色 | `processPolish` |
| 问答 | `processQA`（流式） |
| 风险扫描 | `processRisk` |
| 口语转正式 | `processOral` |
| 智能表格 | `processTable` |

## 大模型配置

应用内：Agent 面板 → ⚙️ → 填写 API 地址、Key、模型名。

默认配置保存在用户目录：
`%APPDATA%/doc-editor-assistant/llm-settings.json`

## 文档

- `openspec/specs/` — **需求真相源**（OpenSpec 规范，配合 Cursor `/opsx-*` 命令）
- `AGENTS.md` — AI/Cursor 开发约定
- `PROJECT_SPEC.md` — 历史产品需求与架构参考
- `CURSOR_IMPLEMENTATION_GUIDE.md` — 功能实现指南

## OpenSpec + Cursor 开发

已初始化 OpenSpec（`openspec init --tools cursor`）。**重启 Cursor** 后可用斜杠命令：

| 命令 | 说明 |
|------|------|
| `/opsx-propose` | 新建功能变更（生成 proposal / design / specs / tasks） |
| `/opsx-apply` | 按 tasks 实现代码 |
| `/opsx-archive` | 归档已完成变更 |

```bash
npm install -g @fission-ai/openspec@latest   # 全局 CLI（已安装）
openspec list                                 # 查看进行中的 change
openspec view                                 # 交互式规范仪表盘
```

## 注意事项

- 本包**不含** `node_modules`，到新电脑后必须 `npm install`
- 用户文稿保存在 `%APPDATA%/doc-editor-assistant/workspace/`，不随源码迁移
- 修改后执行 `npm run pack` 重新生成 exe
