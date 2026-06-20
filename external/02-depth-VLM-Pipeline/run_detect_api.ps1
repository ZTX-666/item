$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { Write-Host "请先运行 一键安装.bat"; exit 1 }
$port = if ($env:PORT) { $env:PORT } else { "8080" }
Write-Host "检测 API http://127.0.0.1:$port/docs"
& $Py -m uvicorn hiagent_api:app --host 0.0.0.0 --port $port
