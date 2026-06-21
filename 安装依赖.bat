@echo off
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
