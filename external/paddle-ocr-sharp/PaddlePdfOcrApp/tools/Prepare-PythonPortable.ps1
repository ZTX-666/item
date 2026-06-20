# One-time: download Windows embeddable Python + pip + rapidocr worker deps into ..\python_portable
# Run from repo:  powershell -ExecutionPolicy Bypass -File tools\Prepare-PythonPortable.ps1
# Result folder (~200MB+): place next to PaddlePdfOcrApp.exe when distributing.

$ErrorActionPreference = 'Stop'
$PythonVersion = '3.11.9'
$EmbedZipName = "python-$PythonVersion-embed-amd64.zip"
$EmbedUrl = "https://www.python.org/ftp/python/$PythonVersion/$EmbedZipName"

$here = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $here 'python_portable'

Write-Host "Target: $dest" -ForegroundColor Cyan
if (Test-Path $dest) {
    Write-Host 'Removing existing python_portable ...' -ForegroundColor Yellow
    Remove-Item -LiteralPath $dest -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $dest | Out-Null
$zip = Join-Path $env:TEMP $EmbedZipName
Write-Host "Downloading $EmbedUrl ..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $EmbedUrl -OutFile $zip -UseBasicParsing
Expand-Archive -Path $zip -DestinationPath $dest -Force

$pthFile = Get-ChildItem -Path $dest -Filter 'python*._pth' | Select-Object -First 1
if (-not $pthFile) { throw 'Embeddable package missing python*._pth' }
$pthText = Get-Content -LiteralPath $pthFile.FullName -Raw
if ($pthText -notmatch '(?m)^import site\s*$') {
    Add-Content -LiteralPath $pthFile.FullName -Value "`r`nimport site`r`n"
}

$getPip = Join-Path $env:TEMP 'get-pip.py'
Write-Host 'Downloading get-pip.py ...'
Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile $getPip -UseBasicParsing

Write-Host 'Installing pip (may take a minute) ...'
& (Join-Path $dest 'python.exe') $getPip --no-warn-script-location

Write-Host 'Installing rapidocr_onnxruntime + pillow (large download) ...'
& (Join-Path $dest 'python.exe') -m pip install --upgrade pip
& (Join-Path $dest 'python.exe') -m pip install rapidocr-onnxruntime pillow

Write-Host 'Done. Copy the entire python_portable folder next to PaddlePdfOcrApp.exe in your publish output.' -ForegroundColor Green
