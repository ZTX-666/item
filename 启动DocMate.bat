@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "APP_DIR=%~dp0"
set "ELECTRON=%APP_DIR%node_modules\electron\dist\electron.exe"
set "LOG=%APP_DIR%启动日志.txt"
title DocMate 闪闪文档 v4.1.37

if not exist "%APP_DIR%dist\index.html" (
  echo [错误] 缺少 dist\index.html，请重新 release
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

echo 正在启动 DocMate v4.1.37 ...
start "" "%ELECTRON%" "%APP_DIR%"
exit /b 0
