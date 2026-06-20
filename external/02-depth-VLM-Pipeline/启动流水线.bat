@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=%~dp0.venv\Scripts\python.exe
if not exist "%PY%" ( echo 请先运行一键安装.bat & pause & exit /b 1 )
"%PY%" pipeline_vlm.py --source input
pause
