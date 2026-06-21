@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
set BASE=%~dp0

echo [赤瞳灵讯] 启动服务环境...

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python。请安装 Python 3.11+ 并添加到 PATH 后再运行。
    pause
    exit /b 1
)

REM AgentToolbox (赤瞳工具箱后端，端口 8899)
set AT_DIR=%BASE%agent-services\agent-toolbox
set AT_VENV=%AT_DIR%\.venv
set AT_PY=%AT_VENV%\Scripts\python.exe
if not exist "%AT_VENV%" (
    echo [AgentToolbox] 创建虚拟环境...
    python -m venv "%AT_VENV%"
    if errorlevel 1 (
        echo [错误] 无法创建 AgentToolbox 虚拟环境
        pause
        exit /b 1
    )
    echo [AgentToolbox] 安装依赖（首次启动需要）...
    "%AT_PY%" -m pip install -q -r "%AT_DIR%\requirements.txt"
    if errorlevel 1 (
        echo [错误] 无法安装 AgentToolbox 依赖
        pause
        exit /b 1
    )
)
echo [AgentToolbox] 启动 http://127.0.0.1:8899 ...
start "AgentToolbox" /min "%AT_PY%" "%AT_DIR%\run_server.py"

REM Chitung Center (编排中心，端口 8999)
set CC_DIR=%BASE%agent-services\chitung-center
set CC_VENV=%CC_DIR%\.venv
set CC_PY=%CC_VENV%\Scripts\python.exe
if not exist "%CC_VENV%" (
    echo [ChitungCenter] 创建虚拟环境...
    python -m venv "%CC_VENV%"
    if errorlevel 1 (
        echo [错误] 无法创建 ChitungCenter 虚拟环境
        pause
        exit /b 1
    )
    echo [ChitungCenter] 安装依赖（首次启动需要）...
    "%CC_PY%" -m pip install -q -r "%CC_DIR%\requirements.txt"
    if errorlevel 1 (
        echo [警告] 无法安装 ChitungCenter 依赖，将继续启动主程序
    )
)
if exist "%CC_PY%" (
    echo [ChitungCenter] 启动 http://127.0.0.1:8999 ...
    start "ChitungCenter" /min "%CC_PY%" "%CC_DIR%\run_server.py"
) else (
    echo [ChitungCenter] 跳过（未创建虚拟环境）
)

echo [赤瞳灵讯] 等待服务就绪...
timeout /t 4 /nobreak >nul

echo [赤瞳灵讯] 启动主程序...
start "" "%BASE%portable\WacliDesktop.exe"