const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const dest = path.join(root, 'publish50')
const PUBLISH_NAME = 'publish50'

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
  'publish31',
  'publish40',
  'publish50',
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
    scripts: { start: 'electron .' },
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
    console.warn('publish50 目录被占用，改为增量同步（请先关闭 DocMate）')
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
fs.writeFileSync(
  path.join(dest, 'package.json'),
  `${JSON.stringify(buildRuntimePackageJson(pkg), null, 2)}\n`,
  'utf-8',
)

const ELECTRON_REL = 'node_modules\\electron\\dist\\electron.exe'

function writeLaunchers(pkg) {
  const launcherBat = `@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "APP_DIR=%~dp0"
set "ELECTRON=%APP_DIR%${ELECTRON_REL}"
set "LOG=%APP_DIR%启动日志.txt"
title DocMate 闪闪文档 v${pkg.version}

if not exist "%APP_DIR%dist\\index.html" (
  echo [错误] 缺少 dist\\index.html，请重新 release
  pause
  exit /b 1
)

if not exist "%ELECTRON%" (
  echo 首次运行：正在安装依赖（约 1-3 分钟，请稍候）...
  where node >nul 2>&1
  if errorlevel 1 (
    echo.
    echo [错误] 未找到 Node.js，无法自动安装依赖。
    echo 请先安装 Node.js LTS: https://nodejs.org/
    echo 或双击「安装依赖.bat」后再试。
    pause
    exit /b 1
  )
  call npm install --omit=dev --no-audit --no-fund >> "%LOG%" 2>&1
  if errorlevel 1 (
    echo [错误] 依赖安装失败，详情见: %LOG%
    pause
    exit /b 1
  )
)

echo 正在启动 DocMate v${pkg.version} ...
start "" "%ELECTRON%" "%APP_DIR%"
exit /b 0
`

  const installBat = `@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "LOG=%~dp0启动日志.txt"
title DocMate 安装依赖
echo 正在安装 DocMate 运行依赖，请稍候...
where node >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 Node.js。请先安装: https://nodejs.org/
  pause
  exit /b 1
)
call npm install --omit=dev --no-audit --no-fund >> "%LOG%" 2>&1
if errorlevel 1 (
  echo 安装失败，日志: %LOG%
  type "%LOG%"
  pause
  exit /b 1
)
echo 安装完成。请双击 DocMate.vbs 启动。
pause
`

  const vbsLauncher = `Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
electron = appDir & "\\node_modules\\electron\\dist\\electron.exe"
installBat = appDir & "\\install-deps.bat"
If Not fso.FileExists(electron) Then
  shell.Run Chr(34) & installBat & Chr(34), 1, True
  If Not fso.FileExists(electron) Then
    MsgBox "Failed to install dependencies. Please run install-deps.bat or install Node.js LTS.", 48, "DocMate"
    WScript.Quit 1
  End If
End If
shell.CurrentDirectory = appDir
shell.Run Chr(34) & electron & Chr(34) & " " & Chr(34) & appDir & Chr(34), 1, False
`

  const psLauncher = `$ErrorActionPreference = 'Stop'
$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Electron = Join-Path $AppDir 'node_modules\\electron\\dist\\electron.exe'
$Log = Join-Path $AppDir '启动日志.txt'
if (-not (Test-Path (Join-Path $AppDir 'dist\\index.html'))) {
  Write-Host '[错误] 缺少 dist，请重新 release' -ForegroundColor Red
  Read-Host '按 Enter 退出'
  exit 1
}
if (-not (Test-Path $Electron)) {
  Write-Host '首次运行：安装依赖中...' -ForegroundColor Yellow
  if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host '[错误] 未找到 Node.js: https://nodejs.org/' -ForegroundColor Red
    Read-Host '按 Enter 退出'
    exit 1
  }
  Push-Location $AppDir
  npm install --omit=dev --no-audit --no-fund *>> $Log
  if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "安装失败，见 $Log"; Read-Host '按 Enter 退出'; exit 1 }
  Pop-Location
}
Start-Process -FilePath $Electron -ArgumentList $AppDir -WorkingDirectory $AppDir
`

  for (const dir of [dest, root]) {
    fs.writeFileSync(path.join(dir, '启动DocMate.bat'), launcherBat, 'utf-8')
    fs.writeFileSync(path.join(dir, '安装依赖.bat'), installBat, 'utf-8')
    fs.writeFileSync(path.join(dir, 'install-deps.bat'), installBat, 'utf-8')
    fs.writeFileSync(path.join(dir, 'DocMate.vbs'), vbsLauncher, 'ascii')
    fs.writeFileSync(path.join(dir, 'Start-DocMate.ps1'), psLauncher, 'utf-8')
  }
}

writeLaunchers(pkg)

try {
  console.log('正在安装 publish50 运行依赖（首次约 1 分钟）…')
  const { execSync } = require('child_process')
  execSync('npm install --omit=dev --no-audit --no-fund', {
    cwd: dest,
    stdio: 'inherit',
    shell: true,
  })
  console.log('依赖安装完成，可直接双击 DocMate.vbs 启动')
} catch (err) {
  console.warn('自动安装依赖失败，请手动在 publish50 目录运行: npm install --omit=dev')
  console.warn(err.message || err)
}

fs.writeFileSync(
  path.join(dest, '使用说明.txt'),
  `DocMate v${pkg.version} — publish50

【推荐启动】双击 DocMate.vbs 或 启动DocMate.bat

【本版优化】
· 删除命令：后端验证失败时 clarify/段落兜底，跳过二次 LLM
· 前端定位：paragraph_text + 关键词片段匹配
· Regenerate：清除 Diff 前保存文本锚，🔄 改为小图标按钮
· Bubble Menu 无选区可走 Agent 自动定位
· Agent 面板 Diff 纯展示，采纳/拒绝统一走编辑器 InlineDiffMenu
· 本地段落评分阈值优化（60/20）+ 短关键词 + 结尾段 boost
`,
  'utf-8',
)

console.log('')
console.log('='.repeat(60))
console.log(`已发布到 ${PUBLISH_NAME}/  v${pkg.version}`)
console.log('='.repeat(60))
console.log('')
