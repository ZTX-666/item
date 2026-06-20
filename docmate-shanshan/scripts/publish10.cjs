const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const dest = path.join(root, 'publish10')
const PUBLISH_NAME = 'publish10'

const INCLUDE_DIRS = ['src', 'electron', 'public', 'openspec']
const INCLUDE_SCRIPTS = [
  'release.cjs',
  'publish10.cjs',
  'test-llm.cjs',
  'test-revision-replace.cjs',
]
const INCLUDE_FILES = [
  'package.json',
  'package-lock.json',
  'index.html',
  'vite.config.ts',
  'tsconfig.json',
  'tsconfig.node.json',
  'tsconfig.app.json',
  'overview.md',
  'AGENTS.md',
  'README.md',
  'PROJECT_SPEC.md',
  'CURSOR_IMPLEMENTATION_GUIDE.md',
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
  'publish8',
  'publish9',
  'publish10',
  'publish11',
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

function copyOptionalDir(relPath) {
  const src = path.join(root, relPath)
  if (!fs.existsSync(src)) return false
  copyDir(src, path.join(dest, relPath))
  return true
}

function loadPkg() {
  return JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf-8'))
}

function clearDestExceptLocked() {
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true })
    return
  }
  try {
    fs.rmSync(dest, { recursive: true, force: true })
    fs.mkdirSync(dest, { recursive: true })
    return
  } catch (err) {
    if (err.code !== 'EPERM' && err.code !== 'EBUSY') throw err
    console.warn('publish10 目录被占用，改为增量同步（请先关闭正在运行的 DocMate）')
  }
}

clearDestExceptLocked()

for (const dir of INCLUDE_DIRS) {
  const srcDir = path.join(root, dir)
  if (fs.existsSync(srcDir)) {
    copyDir(srcDir, path.join(dest, dir))
  }
}

copyOptionalDir('.cursor')

const scriptsDest = path.join(dest, 'scripts')
fs.mkdirSync(scriptsDest, { recursive: true })
for (const script of INCLUDE_SCRIPTS) {
  const src = path.join(root, 'scripts', script)
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, path.join(scriptsDest, script))
  }
}

const copied = []
for (const file of INCLUDE_FILES) {
  if (copyFile(file)) copied.push(file)
}

const distSrc = path.join(root, 'dist')
if (fs.existsSync(distSrc)) {
  copyDir(distSrc, path.join(dest, 'dist'))
} else {
  console.warn('警告: dist/ 不存在，release 前请先 npm run build')
}

const pkg = loadPkg()

const launcherBat = `@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DocMate 闪闪文档 v${pkg.version}
echo.
echo  DocMate 闪闪文档 v${pkg.version}
echo  ==============================
echo.

if not exist "node_modules\\electron" (
  echo [1/2] 正在安装依赖...
  call npm install
  if errorlevel 1 (
    echo 依赖安装失败，请检查 Node.js 是否已安装。
    pause
    exit /b 1
  )
  echo.
)

if not exist "dist\\index.html" (
  echo 正在构建前端...
  call npm run build
  if errorlevel 1 (
    echo 构建失败。
    pause
    exit /b 1
  )
  echo.
)

echo 正在启动...
call npm start
if errorlevel 1 pause
`

fs.writeFileSync(path.join(dest, '启动DocMate.bat'), launcherBat, 'utf-8')
fs.writeFileSync(path.join(root, '启动DocMate.bat'), launcherBat, 'utf-8')

fs.writeFileSync(
  path.join(dest, '使用说明.txt'),
  `DocMate 闪闪文档 v${pkg.version}
================================

【推荐】双击 启动DocMate.bat 启动应用（无需打包 exe）

【首次使用】
  1. 安装 Node.js 18+（https://nodejs.org）
  2. 双击 启动DocMate.bat（会自动 npm install）

【开发】
  cd ${PUBLISH_NAME}
  npm install
  npm start
  npm run release

【可选打包 exe】
  npm run pack

【数据目录】便携模式数据在 exe/启动目录旁的 DocMateData
`,
  'utf-8',
)

fs.writeFileSync(
  path.join(dest, 'README.md'),
  `# DocMate 闪闪文档 v${pkg.version}（完整发布包 publish10）

本目录为**每次 release 自动生成的完整交付包**：可运行源码 + OpenSpec 规范 + 启动脚本。

## 快速开始

| 用途 | 操作 |
|------|------|
| 直接使用 | 双击 \`启动DocMate.bat\` |
| 开发调试 | \`npm install\` → \`npm start\` |
| 重新发布 | \`npm run release\` |
| 可选打包 exe | \`npm run pack\` |

## 目录说明

- \`src/\` \`electron/\` — 应用源码
- \`openspec/\` — OpenSpec 需求规范
- \`.cursor/\` — Cursor 斜杠命令与 Skill
- \`AGENTS.md\` — AI 开发约定
- \`启动DocMate.bat\` — 一键启动（自动安装依赖）

## AI 助手

默认使用智谱 GLM（glm-5.1），可在设置中修改 API。
`,
  'utf-8',
)

console.log('')
console.log('='.repeat(60))
console.log(`已发布完整包到 ${PUBLISH_NAME}/  v${pkg.version}`)
console.log('='.repeat(60))
console.log('')
console.log('源码:', INCLUDE_DIRS.join(', '))
console.log('文档:', copied.filter((f) => f.endsWith('.md')).join(', '))
console.log('脚本:', INCLUDE_SCRIPTS.join(', '))
console.log('前端:', fs.existsSync(path.join(dest, 'dist', 'index.html')) ? 'dist/' : '(缺失，启动时会自动 build)')
console.log('启动: 启动DocMate.bat')
console.log('')
