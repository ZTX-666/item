# 一键安装：检测 + 深度（虚拟环境、PyTorch、权重）
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Find-Python {
    foreach ($c in @("py -3.10", "py -3", "python")) {
        try {
            $v = Invoke-Expression "$c -c `"import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')`"" 2>$null
            if ($v -match "^3\.(10|11|12)$") { return $c }
        } catch {}
    }
    throw "未找到 Python 3.10+"
}

$PyCmd = Find-Python
$Venv = Join-Path $Root ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"

if (-not (Test-Path $Py)) {
    Write-Host "创建 .venv ..."
    Invoke-Expression "$PyCmd -m venv `"$Venv`""
}

Write-Host "安装 PyTorch (CPU) ..."
& $Py -m pip install --upgrade pip wheel
& $Py -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
& $Py -m pip install -r requirements.txt

Write-Host "下载权重（已存在则跳过）..."
& $Py scripts\download_all_weights.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "验证环境..."
& $Py verify_env.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "======== 安装完成 ========"
Write-Host "检测: 启动检测.bat  |  API: 启动检测API.bat  (端口 8080)"
Write-Host "深度: 启动深度.bat  |  API: 启动深度API.bat  (端口 8090)"
Write-Host "说明: USE.txt"
