const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const dest = path.join(root, 'publish4')

const INCLUDE_DIRS = ['src', 'electron', 'scripts']
const INCLUDE_FILES = [
  'package.json',
  'package-lock.json',
  'index.html',
  'vite.config.ts',
  'tsconfig.json',
  'tsconfig.node.json',
  'tsconfig.app.json',
  '.gitignore',
  'PROJECT_SPEC.md',
  'CURSOR_IMPLEMENTATION_GUIDE.md',
  'CODE_ANALYSIS_REPORT.md',
  '启动文稿修改助手.bat',
]

const EXCLUDE_DIR_NAMES = new Set([
  'node_modules',
  'dist',
  'release',
  'publish2',
  'publish3',
  'publish4',
  'publish5',
  '_asar_check',
  '.git',
])

function copyDir(from, to) {
  fs.mkdirSync(to, { recursive: true })
  for (const entry of fs.readdirSync(from, { withFileTypes: true })) {
    if (EXCLUDE_DIR_NAMES.has(entry.name)) continue
    const srcPath = path.join(from, entry.name)
    const destPath = path.join(to, entry.name)
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath)
    } else {
      fs.copyFileSync(srcPath, destPath)
    }
  }
}

function copyFile(name) {
  const src = path.join(root, name)
  if (!fs.existsSync(src)) return false
  fs.copyFileSync(src, path.join(dest, name))
  return true
}

if (fs.existsSync(dest)) {
  fs.rmSync(dest, { recursive: true, force: true })
}
fs.mkdirSync(dest, { recursive: true })

for (const dir of INCLUDE_DIRS) {
  const srcDir = path.join(root, dir)
  if (fs.existsSync(srcDir)) {
    copyDir(srcDir, path.join(dest, dir))
  }
}

const copied = []
for (const file of INCLUDE_FILES) {
  if (copyFile(file)) copied.push(file)
}

const readme = `# 文稿修改助手 — 源代码包 (v${require('../package.json').version})

本目录为**完整源代码**，可复制到另一台电脑继续开发。

## 🚀 新功能 (v4.0)

- ✅ **支持多种文件格式** - .md, .txt, .html, .htm, .doc, .docx, .rtf
- ✅ **文件导入功能** - 可以从外部导入文件到工作区
- ✅ **优化代码体积** - CSS 减少 23%
- ✅ **增强编码支持** - UTF-8 with BOM, UTF-16LE
- ✅ **改进错误处理** - 更友好的错误提示

## 环境要求

- Node.js 18+（推荐 20 LTS）
- npm 9+

## 快速开始

\`\`\`bash
# 1. 进入目录
cd publish4

# 2. 安装依赖
npm install

# 3. 构建前端
npm run build

# 4. 启动桌面应用
npm start
\`\`\`

## 开发模式（热更新）

\`\`\`bash
npm run electron:dev
\`\`\`

需同时启动 Vite 开发服务器和 Electron。

## 打包可执行程序

\`\`\`bash
# 输出到 release/win-unpacked/
npm run pack

# 复制到 publish4 发布目录
npm run publish4
\`\`\`

## 项目结构

\`\`\`
publish4/
├── src/                 # Vue 3 前端源码
│   ├── components/      # UI 组件（编辑器、Agent 面板等）
│   ├── composables/     # 组合式逻辑
│   ├── api/             # AI 接口封装
│   └── styles/          # 优化后的主题样式
├── electron/            # Electron 主进程
│   ├── main.cjs         # 窗口、IPC、文件系统（支持多格式）
│   ├── preload.cjs      # 安全桥接
│   ├── llm.cjs          # 大模型调用
│   └── ai-services.cjs  # 修改/润色/问答/风险等
├── scripts/             # 打包脚本
├── package.json
└── vite.config.ts
\`\`\`

## 主要功能模块

| Agent 模式 | 源码位置 |
|-----------|----------|
| 修改 | \`electron/ai-services.cjs\` → \`processRevise\` |
| 润色 | \`processPolish\` |
| 问答 | \`processQA\`（流式） |
| 风险扫描 | \`processRisk\` |
| 口语转正式 | \`processOral\` |
| 智能表格 | \`processTable\` |

## 大模型配置

应用内：Agent 面板 → ⚙️ → 填写 API 地址、Key、模型名。

默认配置保存在用户目录：
\`%APPDATA%/doc-editor-assistant/llm-settings.json\`

## 支持的文件格式

| 格式 | 支持程度 |
|------|----------|
| .md | ✅ 完整支持（Markdown 转 HTML） |
| .txt | ✅ 完整支持（自动编码检测） |
| .html, .htm | ✅ 完整支持 |
| .docx | ⚠️ 提示安装依赖 |
| .doc | ⚠️ 建议转换格式 |
| .rtf | ⚠️ 简化处理 |

## 文档

- \`PROJECT_SPEC.md\` — 产品需求与架构
- \`CURSOR_IMPLEMENTATION_GUIDE.md\` — 功能实现指南
- \`CODE_ANALYSIS_REPORT.md\` — 代码分析与优化报告

## 注意事项

- 本包**不含** \`node_modules\`，到新电脑后必须 \`npm install\`
- 用户文稿保存在 \`%APPDATA%/doc-editor-assistant/workspace/\`，不随源码迁移
- 修改后执行 \`npm run pack\` 重新生成 exe
- 首次使用建议查看 \`CODE_ANALYSIS_REPORT.md\` 了解优化内容
`

fs.writeFileSync(path.join(dest, 'README.md'), readme, 'utf-8')

console.log('')
console.log('='.repeat(60))
console.log('源代码已打包到 publish4/')
console.log('='.repeat(60))
console.log('')
console.log('包含目录:', INCLUDE_DIRS.join(', '))
console.log('包含文件:', copied.join(', '))
console.log('')
console.log('📦 新功能:')
console.log('  ✅ 支持 .md, .txt, .html, .doc, .docx, .rtf 格式')
console.log('  ✅ 新增文件导入功能')
console.log('  ✅ CSS 体积减少 23%')
console.log('  ✅ 增强编码支持 (UTF-8 BOM, UTF-16LE)')
console.log('')
console.log('🚀 到新电脑后执行:')
console.log('  cd publish4')
console.log('  npm install')
console.log('  npm run build && npm start')
console.log('')
