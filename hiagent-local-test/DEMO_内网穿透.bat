@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ============================================================
echo   内网穿透 Demo（大白话版）
echo   目标：让云端 HiAgent 能通过公网网址访问你本机的 8787 服务
echo ============================================================
echo.
echo 第 0 步：安装 cloudflared（只需一次）
echo   winget install Cloudflare.cloudflared
echo.
echo 本脚本将自动：
echo   [1] 在本机启动测试 API（8787 端口）
echo   [2] 启动 Cloudflare 隧道，生成 https://xxxx.trycloudflare.com
echo.
echo 请把第 2 步窗口里出现的 https 地址复制到 HiAgent 里测试。
echo 示例：https://xxxx.trycloudflare.com/api/ping
echo.
pause

echo.
echo [1/2] 启动本机 API ...
start "本机API-8787" cmd /k "cd /d %~dp0 && python -m pip install -r requirements.txt -q && python local_test_server.py"

echo 等待 5 秒 ...
timeout /t 5 /nobreak >nul

echo.
echo [2/2] 启动隧道（会显示公网地址，不要关窗口）...
where cloudflared >nul 2>&1
if errorlevel 1 (
    echo.
    echo [错误] 未找到 cloudflared，请先运行：
    echo   winget install Cloudflare.cloudflared
    echo 然后重新双击本脚本。
    pause
    exit /b 1
)

cloudflared tunnel --url http://127.0.0.1:8787

pause
