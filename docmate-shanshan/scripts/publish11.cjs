const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const dest = path.join(root, 'publish11')
const PUBLISH_NAME = 'publish11'

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
    console.warn('publish11 目录被占用，改为增量同步（请先关闭 DocMate）')
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
title DocMate 闪闪文档 v${pkg.version}（精简版）
echo.
echo  DocMate 闪闪文档 v${pkg.version}  [publish11 精简运行包]
echo  =======================================
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
  echo 错误: 缺少 dist/index.html，请使用完整版 publish10 或重新 release。
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
  `DocMate 闪闪文档 v${pkg.version} — publish11 精简运行包
==========================================

【启动】双击 启动DocMate.bat

【特点】
  · 仅含 electron/ + dist/ + public/，体积更小、安装更快
  · 不含 src/ openspec/ 开发文档（需改代码请用项目根目录或 publish10）

【首次使用】安装 Node.js 18+，启动时会自动 npm install（仅运行依赖）

【数据】DocMateData 在启动目录旁（便携模式）
`,
  'utf-8',
)

fs.writeFileSync(
  path.join(dest, 'README.md'),
  `# DocMate v${pkg.version} — publish11 精简运行包

| 操作 | 命令 |
|------|------|
| 启动 | 双击 \`启动DocMate.bat\` |

## 目录

- \`dist/\` — 预构建前端
- \`electron/\` — 主进程
- \`public/\` — 图标等资源

完整源码包见 \`publish10/\`。
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
