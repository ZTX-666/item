@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/2] Starting local API on port 8787 ...
start "Chitong-Local-API" cmd /k "cd /d %~dp0 && python -m pip install -r requirements.txt -q && python local_test_server.py"

timeout /t 4 /nobreak >nul

echo [2/2] Starting Cloudflare quick tunnel (public HTTPS URL) ...
echo.
echo If cloudflared is not installed, run:
echo   winget install Cloudflare.cloudflared
echo.
echo Copy the https://*.trycloudflare.com URL into HiAgent HTTP tool base URL.
echo Example: https://xxxx.trycloudflare.com/health
echo.

where cloudflared >nul 2>&1
if errorlevel 1 (
    echo ERROR: cloudflared not found. Install with winget or download from cloudflare.com.
    pause
    exit /b 1
)

cloudflared tunnel --url http://127.0.0.1:8787
pause
