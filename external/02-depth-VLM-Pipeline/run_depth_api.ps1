$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { Write-Host "请先运行 一键安装.bat"; exit 1 }
$port = if ($env:DEPTH_PORT) { $env:DEPTH_PORT } else { "8090" }
Write-Host "深度 API http://127.0.0.1:$port/docs"
& $Py -m uvicorn depth_api:app --host 0.0.0.0 --port $port
