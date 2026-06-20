const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const dest = path.join(root, 'publish30')
const PUBLISH_NAME = 'publish30'

/** 运行时核心：预构建前端 + Electron 主进程 */
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
  'publish30',
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
    console.warn('publish30 目录被占用，改为增量同步（请先关闭 DocMate）')
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
title DocMate 闪闪文档 v${pkg.version}（Agent 版）
echo.
echo  DocMate 闪闪文档 v${pkg.version}  [publish30 Agent 无选区改稿]
echo  =======================================
  echo  Agent：无选区增删改 · Apply / Tab 采纳 · Esc 拒绝 · 🔄 重新生成
echo.

if not exist "node_modules\\electron\\package.json" (
  echo [1/2] 首次运行，安装运行依赖...
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
  `DocMate 闪闪文档 v${pkg.version} — publish30
==========================================

【启动】双击 启动DocMate.bat

【Cursor 式 Agent 改稿（无需选中）】
  · 打开右侧 Agent（Ctrl+M）
  · 直接说：「第二段改正式」「删掉第三段」「在文末加一段总结」
  · 系统自动定位段落 → 编辑器显示 Diff → 采纳写回

【有选区时】选中文字后，编辑器上方操作条可快速修改

【首次使用】Node.js 18+，首次启动自动 npm install
`,
  'utf-8',
)

fs.writeFileSync(
  path.join(dest, 'README.md'),
  `# DocMate v${pkg.version} — publish30

基于 publish11，增强 **Cursor Agent 式无选区增删改**。

| 操作 | 说明 |
|------|------|
| Ctrl+M | 打开 Agent |
| Agent 指令 | 「第 N 段…」「删除…」「新增…」无需鼠标选中 |
| 确认 | 编辑器 Diff 预览 → 采纳/拒绝 |

启动：\`启动DocMate.bat\`
`,
  'utf-8',
)

console.log('')
console.log('='.repeat(60))
console.log(`已发布到 ${PUBLISH_NAME}/  v${pkg.version}`)
console.log('='.repeat(60))
console.log('')
