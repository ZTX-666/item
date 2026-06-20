$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { Write-Host "请先 一键安装.bat"; exit 1 }
Set-Location $Root
& $Py pipeline_vlm.py --source input @args
