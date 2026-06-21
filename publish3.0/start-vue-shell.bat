@echo off
chcp 65001 >nul
setlocal

set BASE=%~dp0
echo [publish3.0] 启动 Vue 对接示例（需先运行 start-api.bat）
echo [publish3.0] 地址: http://127.0.0.1:5173
echo.

cd /d "%BASE%source\vue-shell"
if not exist node_modules (
  echo 首次运行，正在 npm install...
  call npm install
)
call npm run dev
