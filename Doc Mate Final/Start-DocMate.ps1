$ErrorActionPreference = 'Stop'
$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Electron = Join-Path $AppDir 'node_modules\electron\dist\electron.exe'
$Log = Join-Path $AppDir '启动日志.txt'
if (-not (Test-Path (Join-Path $AppDir 'dist\index.html'))) {
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
