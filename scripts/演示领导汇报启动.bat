@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

rem Leader demo: all toolbox tools ON, background automation OFF, history preserved.

set "ROOT=%~dp0.."
set "TOOLBOX=%ROOT%\agent-toolbox"
set "CENTER=%ROOT%\chitung-center"
set "FRONTEND=%ROOT%\chitung-frontend"
set "CCTV_GATEWAY=%ROOT%\cctv-gateway"
set "WHATSAPP_ARCHIVE=%ROOT%\whatsapp-archive\app-server"

echo.
echo ========================================
echo   Chitung leader demo startup
echo ========================================

echo [1/6] Stop old processes...
for %%P in (5173 8899 8999 3457 8787) do (
  for /f "tokens=5" %%Q in ('netstat -ano ^| findstr ":%%P" ^| findstr "LISTENING"') do taskkill /F /PID %%Q >nul 2>&1
)
taskkill /F /IM electron.exe >nul 2>&1
ping -n 2 127.0.0.1 >nul

echo [2/6] Repair SQLite + pause auto patrol...
"%CENTER%\.venv\Scripts\python.exe" "%ROOT%\scripts\repair_platform_dbs.py"
"%CENTER%\.venv\Scripts\python.exe" "%ROOT%\scripts\demo_lightweight_reset.py"

echo [3/6] Start agent-toolbox (:8899)...
start "agent-toolbox" /MIN /D "%TOOLBOX%" cmd /c ".venv\Scripts\python.exe run_server.py"
ping -n 2 127.0.0.1 >nul

echo [4/6] Start chitung-center (:8999, schedulers disabled)...
start "chitung-center" /MIN /D "%CENTER%" cmd /c "set DISABLE_BACKGROUND_SCHEDULERS=true&& .venv\Scripts\python.exe run_server.py"
ping -n 2 127.0.0.1 >nul

echo [5/6] Start CCTV (:3457) + WhatsApp Archive (:8787)...
start "cctv-gateway" /MIN /D "%CCTV_GATEWAY%" cmd /c "node --env-file-if-exists=.env src/server.cjs"
if exist "%WHATSAPP_ARCHIVE%\package.json" (
  start "whatsapp-archive" /MIN /D "%WHATSAPP_ARCHIVE%" cmd /c "set WHATSCLI_STORE_DIR=%ROOT%\agent-toolbox\workspace\wacli&& set WHATSCLI_DB_PATH=%ROOT%\agent-toolbox\workspace\wacli\wacli.db&& npm run start"
)

echo Waiting for backends...
set /a WAIT=0
:wait_backends
curl -sf http://127.0.0.1:8899/health >nul 2>&1
if errorlevel 1 goto :wait_retry
curl -sf http://127.0.0.1:8999/health >nul 2>&1
if errorlevel 1 goto :wait_retry
curl -sf http://127.0.0.1:3457/api/health >nul 2>&1
if errorlevel 1 goto :wait_retry
curl -sf http://127.0.0.1:8787/api/health >nul 2>&1
if errorlevel 1 goto :wait_retry
goto :backends_ok
:wait_retry
set /a WAIT+=1
if !WAIT! GEQ 60 goto :backends_ok
ping -n 2 127.0.0.1 >nul
goto :wait_backends

:backends_ok
echo [6/6] Start Vite + Electron...
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
echo Leader demo ready. Running preflight...
"%CENTER%\.venv\Scripts\python.exe" "%ROOT%\scripts\demo_preflight.py"
echo.
endlocal
