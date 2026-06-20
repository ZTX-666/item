const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const dest = path.join(root, 'publish7')
const PUBLISH_NAME = 'publish7'

const INCLUDE_DIRS = ['src', 'electron', 'public']
const INCLUDE_SCRIPTS = ['release.cjs', 'publish7.cjs', 'test-llm.cjs']
const INCLUDE_FILES = [
  'package.json',
  'package-lock.json',
  'index.html',
  'vite.config.ts',
  'tsconfig.json',
  'tsconfig.node.json',
  'tsconfig.app.json',
  'overview.md',
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
  'publish7',
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

function loadPkg() {
  return JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf-8'))
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

const scriptsDest = path.join(dest, 'scripts')
fs.mkdirSync(scriptsDest, { recursive: true })
for (const script of INCLUDE_SCRIPTS) {
  const src = path.join(root, 'scripts', script)
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, path.join(scriptsDest, script))
  }
}

const cursorRulesSrc = path.join(root, '.cursor', 'rules', 'auto-release.mdc')
if (fs.existsSync(cursorRulesSrc)) {
  const rulesDest = path.join(dest, '.cursor', 'rules')
  fs.mkdirSync(rulesDest, { recursive: true })
  fs.copyFileSync(cursorRulesSrc, path.join(rulesDest, 'auto-release.mdc'))
}

const redesignSrc = 'c:\\Users\\ber\\WorkBuddy\\2026-06-14-09-52-04\\selection-redesign.md'
if (fs.existsSync(redesignSrc)) {
  fs.copyFileSync(redesignSrc, path.join(dest, 'selection-redesign.md'))
}

const copied = []
for (const file of INCLUDE_FILES) {
  if (copyFile(file)) copied.push(file)
}

const pkg = loadPkg()
const portableSrc = findPortableExe()
let portableName = ''
if (portableSrc) {
  portableName = `DocMate闪闪文档 ${pkg.version}.exe`
  fs.copyFileSync(portableSrc, path.join(dest, portableName))
}

fs.writeFileSync(
  path.join(dest, '启动DocMate.bat'),
  `@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动 DocMate 闪闪文档 v${pkg.version} ...
if exist "${portableName}" (
  start "" "${portableName}"
) else (
  echo 未找到便携版，请在本目录执行: npm install ^&^& npm run release
  pause
)
`,
  'utf-8',
)

fs.writeFileSync(
  path.join(dest, '使用说明.txt'),
  `DocMate 闪闪文档 v${pkg.version}
================================

【便携版】双击 启动DocMate.bat 或 ${portableName}

【选即说】选中文字 → 选区上方操作条 → 说话/输入 → 编辑器内确认采纳

【问答/历史/设置】右侧 DocMate 面板

【配置 API】AI 面板 → 设置 → 启用在线大模型

【数据目录】exe 同目录 DocMateData（便携模式）

【开发】
  cd ${PUBLISH_NAME}
  npm install
  npm start
`,
  'utf-8',
)

fs.writeFileSync(
  path.join(dest, 'README.md'),
  `# DocMate 闪闪文档 v${pkg.version}

精简发布包：便携 exe + 完整可编译源码。

## 快速开始

| 用途 | 操作 |
|------|------|
| 直接使用 | 双击 \`启动DocMate.bat\` |
| 开发调试 | \`npm install\` → \`npm start\` |
| 重新打包 | \`npm run release\` |

## 交互（选即说）

1. 选中文字，选区上方出现 Bubble 操作条
2. 语音或输入修改要求
3. 编辑器内 Inline Diff，就地采纳/拒绝

右侧 AI 面板：问答、修改历史、大模型与知识库设置。

详见 \`selection-redesign.md\` 与 \`overview.md\`。
`,
  'utf-8',
)

console.log('')
console.log('='.repeat(60))
console.log(`已精简发布到 ${PUBLISH_NAME}/  v${pkg.version}`)
console.log('='.repeat(60))
console.log('')
console.log('源码目录:', INCLUDE_DIRS.join(', '))
console.log('脚本:', INCLUDE_SCRIPTS.join(', '))
console.log('配置文件:', copied.join(', '))
if (portableName) console.log('便携版:', portableName)
console.log('')
