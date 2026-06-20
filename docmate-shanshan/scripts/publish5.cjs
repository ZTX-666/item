const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const dest = path.join(root, 'publish5')
const pkg = require('../package.json')

const INCLUDE_DIRS = ['src', 'electron', 'scripts', 'public']
const INCLUDE_FILES = [
  'package.json',
  'package-lock.json',
  'index.html',
  'vite.config.ts',
  'tsconfig.json',
  'tsconfig.node.json',
  'tsconfig.app.json',
  '.gitignore',
  'overview.md',
  'PROJECT_SPEC.md',
  'CURSOR_IMPLEMENTATION_GUIDE.md',
  'CODE_ANALYSIS_REPORT.md',
]

const EXCLUDE_DIR_NAMES = new Set([
  'node_modules',
  'dist',
  'release',
  'publish2',
  'publish3',
  'publish4',
  'publish5',
  'publish6',
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

function findPortableExe() {
  const releaseDir = path.join(root, 'release')
  if (!fs.existsSync(releaseDir)) return null
  const files = fs.readdirSync(releaseDir).filter((f) => f.endsWith('.exe') && !f.includes('unpacked'))
  if (files.length === 0) return null
  return path.join(releaseDir, files[0])
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

const portableSrc = findPortableExe()
let portableName = ''
if (portableSrc) {
  portableName = `DocMate闪闪文档 ${pkg.version}.exe`
  fs.copyFileSync(portableSrc, path.join(dest, portableName))
}

const launcherBat = `@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动 DocMate 闪闪文档 v${pkg.version} ...
if exist "${portableName || 'DocMate闪闪文档.exe'}" (
  start "" "${portableName || 'DocMate闪闪文档.exe'}"
) else (
  echo 未找到便携版程序，请先运行 npm run pack 重新打包。
  pause
)
`
fs.writeFileSync(path.join(dest, '启动DocMate.bat'), launcherBat, 'utf-8')

const userGuide = `DocMate 闪闪文档 v${pkg.version}
================================

【便携版 - 推荐】
双击「启动DocMate.bat」或直接运行「${portableName || 'DocMate闪闪文档.exe'}」。
无需安装，可复制到 U 盘或任意文件夹使用。
首次运行会在 exe 同目录生成 DocMateData 文件夹保存文稿与配置。

【核心用法】
1. 粘贴或输入文稿
2. 点击右侧 AI 助手，用语音或文字说修改要求
3. 在编辑器中查看修改对比（红删绿增）
4. 确认应用或跳过

【语音输入】
首次使用会自动下载 Whisper 语音模型（约 75MB），之后可离线语音识别。

【大模型配置】
AI 面板 → ⚙️ → 填写豆包 API 地址、Key、模型名。

【支持的文件格式】
.md / .txt / .html / .docx（导入）

【开发版】
如需修改源码，请安装 Node.js 18+，在本目录执行：
  npm install
  npm run build
  npm start
`

fs.writeFileSync(path.join(dest, '使用说明.txt'), userGuide, 'utf-8')

const devReadme = `# DocMate 闪闪文档 — 发布包 v${pkg.version}

本目录包含**便携版程序**与**完整源代码**，可直接分发或继续开发。

## 便携版（免安装）

| 文件 | 说明 |
|------|------|
| \`${portableName || 'DocMate闪闪文档.exe'}\` | Windows 便携版单文件 exe |
| \`启动DocMate.bat\` | 一键启动 |
| \`使用说明.txt\` | 用户使用指南 |

## 源代码

\`\`\`bash
cd publish5
npm install
npm run build
npm start          # 启动桌面应用
npm run electron:dev   # 开发模式（热更新）
npm run pack       # 重新打包便携版 exe
\`\`\`

## v${pkg.version} 新特性

- ✅ **写字板首屏** — 侧栏默认折叠，打开即写
- ✅ **智能意图路由** — 无需手动切换 6 种模式，说话即可
- ✅ **Whisper 本地语音** — 中国大陆可用，离线识别
- ✅ **编辑器内 Diff** — 红删绿增，人机协同确认
- ✅ **模糊文本匹配** — AI 定位偏差时自动纠错
- ✅ **修改历史** — 时间线回溯每次 AI 修改
- ✅ **.docx 导入** — mammoth 解析 Word 文档
- ✅ **便携版数据** — exe 同目录 DocMateData，随拷随走

## 项目结构

\`\`\`
publish5/
├── public/闪闪文档.png    # 品牌 Logo
├── src/                   # Vue 3 前端
├── electron/              # 主进程（语音、AI、文件系统）
├── scripts/               # 打包脚本
├── overview.md            # 产品优化建议报告
└── package.json
\`\`\`

## 注意事项

- 源码包**不含** node_modules，需 \`npm install\`
- 便携版用户数据在 exe 旁 \`DocMateData/\`
- 开发版用户数据在 \`%APPDATA%/docmate/\`（非便携模式）
`

fs.writeFileSync(path.join(dest, 'README.md'), devReadme, 'utf-8')

console.log('')
console.log('='.repeat(60))
console.log('已发布到 publish5/')
console.log('='.repeat(60))
console.log('')
console.log('包含目录:', INCLUDE_DIRS.join(', '))
console.log('包含文件:', copied.join(', '))
if (portableName) {
  console.log('便携版:', portableName)
} else {
  console.log('⚠ 未找到便携版 exe，请先运行 npm run pack')
}
console.log('')
console.log('用户使用: 双击 启动DocMate.bat')
console.log('开发使用: cd publish5 && npm install && npm start')
console.log('')
