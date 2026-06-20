# 若電腦尚未安裝 .NET 8 Desktop Runtime，無法啟動框架依賴版程式時，請先「右鍵 → 以系統管理員身分執行」本腳本。
# 完成後再執行 PaddlePdfOcrApp.exe；進入程式後可點「一鍵配置環境」下載 Python（或本腳本亦可一併完成 Python）。
param(
    [switch] $SkipDotNet,
    [switch] $SkipPython
)

$ErrorActionPreference = 'Stop'
$base = $PSScriptRoot
if (-not $base) { $base = (Get-Location).Path }

function Install-DotNetDesktop8 {
    Write-Host '正在安裝 .NET 8 Windows Desktop Runtime (x64)...' -ForegroundColor Cyan
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        & winget install --id Microsoft.DotNet.DesktopRuntime.8 -e --accept-source-agreements --accept-package-agreements --silent
        return
    }
    $url = 'https://aka.ms/dotnet/8.0/windowsdesktop-runtime-win-x64.exe'
    $exe = Join-Path $env:TEMP 'windowsdesktop-runtime-8-win-x64.exe'
    Write-Host "下載：$url" -ForegroundColor Cyan
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $url -OutFile $exe -UseBasicParsing
    Start-Process -FilePath $exe -ArgumentList '/install /quiet /norestart' -Verb RunAs -Wait
}

function Install-PythonPortable {
    $PythonVersion = '3.11.9'
    $EmbedZipName = "python-$PythonVersion-embed-amd64.zip"
    $EmbedUrl = "https://www.python.org/ftp/python/$PythonVersion/$EmbedZipName"
    $dest = Join-Path $base 'python_portable'

    Write-Host "Python 目標目錄：$dest" -ForegroundColor Cyan
    if (Test-Path $dest) {
        Remove-Item -LiteralPath $dest -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    $zip = Join-Path $env:TEMP $EmbedZipName
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
    Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile $getPip -UseBasicParsing
    & (Join-Path $dest 'python.exe') $getPip --no-warn-script-location
    & (Join-Path $dest 'python.exe') -m pip install --upgrade pip
    & (Join-Path $dest 'python.exe') -m pip install rapidocr-onnxruntime pillow
    Write-Host 'Python 可攜式環境完成。' -ForegroundColor Green
}

if (-not $SkipDotNet) {
    Install-DotNetDesktop8
}
if (-not $SkipPython) {
    Install-PythonPortable
}

Write-Host '全部步驟結束。請執行 PaddlePdfOcrApp.exe。' -ForegroundColor Green
