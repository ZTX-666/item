@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0.."
set "CENTER=%ROOT%\chitung-center"

echo.
echo ========================================
echo   赤瞳 · 演示前自检
echo ========================================
echo.

if not exist "%CENTER%\.venv\Scripts\python.exe" (
  echo [错误] 未找到 chitung-center 虚拟环境
  echo 请先运行 scripts\启动赤瞳平台.bat 完成首次安装
  pause
  exit /b 1
)

"%CENTER%\.venv\Scripts\python.exe" "%ROOT%\scripts\demo_preflight.py"
set "CODE=%ERRORLEVEL%"

echo.
if "%CODE%"=="0" (
  echo [OK] 自检通过，可以开始彩排。
) else (
  echo [注意] 存在失败项，请按上方提示修复后再演示。
)
echo.
pause
exit /b %CODE%
