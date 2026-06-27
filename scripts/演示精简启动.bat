@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

rem 演示模式：关闭后台自动巡检，只保留 WPS + 赤瞳核心服务 + Electron

set "ROOT=%~dp0.."
set "TOOLBOX=%ROOT%\agent-toolbox"
set "CENTER=%ROOT%\chitung-center"
set "FRONTEND=%ROOT%\chitung-frontend"
set "CCTV_GATEWAY=%ROOT%\cctv-gateway"

echo.
echo ========================================
echo   赤瞳 · 演示精简启动（无后台自动巡检）
echo ========================================

echo [1/4] 停止旧进程...
for %%P in (5173 8899 8999 3457 8787) do (
  for /f "tokens=5" %%Q in ('netstat -ano ^| findstr ":%%P" ^| findstr "LISTENING"') do taskkill /F /PID %%Q >nul 2>&1
)
taskkill /F /IM electron.exe >nul 2>&1
ping -n 2 127.0.0.1 >nul

echo [2/4] 暂停自动吊运巡检与卡住的后台任务...
"%CENTER%\.venv\Scripts\python.exe" "%ROOT%\scripts\demo_lightweight_reset.py"

echo [3/4] 启动核心后端（禁用后台调度器）...
set DISABLE_BACKGROUND_SCHEDULERS=true
start "agent-toolbox" /MIN /D "%TOOLBOX%" cmd /c ".venv\Scripts\python.exe run_server.py"
ping -n 2 127.0.0.1 >nul
start "chitung-center" /MIN /D "%CENTER%" cmd /c "set DISABLE_BACKGROUND_SCHEDULERS=true&& .venv\Scripts\python.exe run_server.py"
ping -n 2 127.0.0.1 >nul
start "cctv-gateway" /MIN /D "%CCTV_GATEWAY%" cmd /c "node --env-file-if-exists=.env src/server.cjs"

echo 等待后端就绪...
set /a WAIT=0
:wait_backends
curl -sf http://127.0.0.1:8899/health >nul 2>&1
if errorlevel 1 goto :wait_retry
curl -sf http://127.0.0.1:8999/health >nul 2>&1
if errorlevel 1 goto :wait_retry
goto :backends_ok
:wait_retry
set /a WAIT+=1
if !WAIT! GEQ 40 goto :backends_ok
ping -n 2 127.0.0.1 >nul
goto :wait_backends

:backends_ok
echo [4/4] 启动前端与 Electron...
start "chitung-vite" /MIN /D "%FRONTEND%" cmd /c "npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"
set /a FW=0
:wait_fe
curl -sf http://127.0.0.1:5173 >nul 2>&1
if not errorlevel 1 goto :fe_ok
set /a FW+=1
if !FW! GEQ 30 goto :fe_ok
ping -n 2 127.0.0.1 >nul
goto :wait_fe
:fe_ok
start "chitung-desktop" /D "%FRONTEND%" cmd /c "set VITE_DEV_SERVER_URL=http://127.0.0.1:5173&& set CHITUNG_AUTOSTART_SERVICES=false&& node_modules\.bin\electron.cmd ."

echo.
echo 精简模式已启动
echo   核心: 中台 / 工具箱 / CCTV / Electron
echo   已关闭: WhatsApp Archive 8787、自动吊运巡检、外部监听调度
echo   WPS 未受影响
echo.
endlocal
