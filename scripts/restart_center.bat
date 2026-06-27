@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "ROOT=%~dp0.."
set "CENTER=%ROOT%\chitung-center"

echo [赤瞳] 重启 chitung-center (:8999)...

for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8999" ^| findstr "LISTENING"') do taskkill /F /PID %%P >nul 2>&1

ping -n 3 127.0.0.1 >nul

start "chitung-center" /MIN /D "%CENTER%" cmd /c ".venv\Scripts\python.exe run_server.py"

set /a WAIT=0
:wait_loop
curl -sf http://127.0.0.1:8999/health >nul 2>&1
if not errorlevel 1 goto :ready
set /a WAIT+=1
if !WAIT! GEQ 30 goto :timeout
ping -n 2 127.0.0.1 >nul
goto :wait_loop

:ready
echo [OK] chitung-center 已就绪
exit /b 0

:timeout
echo [警告] 中台启动超时，请查看 chitung-center 窗口日志
exit /b 1
