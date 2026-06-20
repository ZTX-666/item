$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { Write-Host "请先运行 一键安装.bat"; exit 1 }
& $Py detect.py --source input --save-img --export-json @args
