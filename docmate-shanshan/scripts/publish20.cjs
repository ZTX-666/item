const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const dest = path.join(root, 'publish20')
const PUBLISH_NAME = 'publish20'

/** 运行时核心：预构建前端 + Electron 主进程，不含源码与开发文档 */
const INCLUDE_DIRS = ['electron', 'public']

const EXCLUDE_DIR_NAMES = new Set([
  'node_modules',
  'dist',
  'release',
  'src',
  'openspec',
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
  'publish20',
  '_asar_check',
  '.git',
  '.cursor',
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

function loadPkg() {
  return JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf-8'))
}

function buildRuntimePackageJson(pkg) {
  const electronVer = pkg.devDependencies?.electron || pkg.dependencies?.electron
  return {
    name: pkg.name,
    private: true,
    version: pkg.version,
    description: pkg.description,
    author: pkg.author,
    main: pkg.main,
    type: pkg.type,
    scripts: {
      start: 'electron .',
    },
    dependencies: {
      ...pkg.dependencies,
      ...(electronVer ? { electron: electronVer } : {}),
    },
  }
}

function clearDestExceptLocked() {
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true })
    return
  }
  try {
    fs.rmSync(dest, { recursive: true, force: true })
    fs.mkdirSync(dest, { recursive: true })
  } catch (err) {
    if (err.code !== 'EPERM' && err.code !== 'EBUSY') throw err
    console.warn('publish20 目录被占用，改为增量同步（请先关闭 DocMate）')
  }
}

clearDestExceptLocked()

for (const dir of INCLUDE_DIRS) {
  const srcDir = path.join(root, dir)
  if (fs.existsSync(srcDir)) {
    copyDir(srcDir, path.join(dest, dir))
  }
}

const distSrc = path.join(root, 'dist')
if (fs.existsSync(distSrc)) {
  copyDir(distSrc, path.join(dest, 'dist'))
} else {
  console.warn('警告: dist/ 不存在，请先 npm run build')
}

const pkg = loadPkg()
const runtimePkg = buildRuntimePackageJson(pkg)
fs.writeFileSync(path.join(dest, 'package.json'), `${JSON.stringify(runtimePkg, null, 2)}\n`, 'utf-8')

const launcherBat = `@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DocMate 闪闪文档 v${pkg.version}（Cursor 对标版）
echo.
echo  DocMate 闪闪文档 v${pkg.version}  [publish20 Cursor 对标运行包]
echo  =======================================
echo  Ctrl+K 内联修改 · Ctrl+L 问答 · Tab 采纳 · Esc 拒绝
echo.

if not exist "node_modules\\electron\\package.json" (
  echo [1/2] 首次运行，安装运行依赖（不含开发工具）...
  call npm install --omit=dev --no-audit --no-fund
  if errorlevel 1 (
    echo 依赖安装失败，请确认已安装 Node.js 18+
    pause
    exit /b 1
  )
  echo.
)

if not exist "dist\\index.html" (
  echo 错误: 缺少 dist/index.html，请重新 release。
  pause
  exit /b 1
)

echo [2/2] 正在启动...
call npm start
if errorlevel 1 pause
`

fs.writeFileSync(path.join(dest, '启动DocMate.bat'), launcherBat, 'utf-8')
fs.writeFileSync(path.join(root, '启动DocMate.bat'), launcherBat, 'utf-8')

fs.writeFileSync(
  path.join(dest, '使用说明.txt'),
  `DocMate 闪闪文档 v${pkg.version} — publish20 Cursor 对标运行包
==========================================

【启动】双击 启动DocMate.bat

【交互】
  · Ctrl+K — 选中/当前段落内联修改（Diff 预览）
  · Ctrl+L — 打开 Chat 问答（不直接改文档）
  · Tab — 采纳修改 · Esc — 拒绝 · 🔄 重新生成（最多 3 次）

【特点】
  · 仅含 electron/ + dist/ + public/，体积更小
  · 不含 src/ 源码（开发请用项目根目录）

【首次使用】安装 Node.js 18+，启动时会自动 npm install（仅运行依赖）

【数据】DocMateData 在启动目录旁（便携模式）
`,
  'utf-8',
)

fs.writeFileSync(
  path.join(dest, 'README.md'),
  `# DocMate v${pkg.version} — publish20 Cursor 对标运行包

| 快捷键 | 功能 |
|--------|------|
| Ctrl+K | 内联修改（单方案 + 重新生成） |
| Ctrl+L | Chat 问答 |
| Tab | 采纳 Diff |
| Esc | 拒绝 Diff |

启动：双击 \`启动DocMate.bat\`
`,
  'utf-8',
)

console.log('')
console.log('='.repeat(60))
console.log(`已发布精简运行包到 ${PUBLISH_NAME}/  v${pkg.version}`)
console.log('='.repeat(60))
console.log('')
console.log('核心:', [...INCLUDE_DIRS, 'dist'].join(', '))
console.log('依赖: npm install --omit=dev（仅运行时）')
console.log('启动: 启动DocMate.bat')
console.log('')
