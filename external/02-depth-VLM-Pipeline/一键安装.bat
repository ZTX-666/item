@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [depth 包] 安装检测+深度环境与模型，首次约 5-20 分钟...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 ( echo 安装失败 & pause & exit /b 1 )
echo 安装成功。可运行：启动检测 / 启动深度 / 启动流水线
pause
