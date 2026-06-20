param(
    [ValidateSet('Framework', 'SelfContained')]
    [string] $Mode = 'Framework'
)
# V44：預設框架依賴（體積小）；目標機需 .NET 8 Desktop Runtime，或先執行 install-environment.ps1。

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$dotnet = if (Test-Path "$env:LOCALAPPDATA\Microsoft\dotnet\dotnet.exe") {
    "$env:LOCALAPPDATA\Microsoft\dotnet\dotnet.exe"
} else {
    'dotnet'
}

$out = Join-Path $here 'publish\portable_v44'
$selfContained = if ($Mode -eq 'SelfContained') { 'true' } else { 'false' }

Write-Host "Mode: $Mode -> $out" -ForegroundColor Cyan

& $dotnet publish 'PaddlePdfOcrApp.csproj' `
    -c Release `
    -r win-x64 `
    --self-contained $selfContained `
    /p:PublishSingleFile=false `
    /p:DebugType=none `
    /p:DebugSymbols=false `
    -o $out

Write-Host 'Publish v44 finished.' -ForegroundColor Green
if ($Mode -eq 'Framework') {
    Write-Host 'Target PC: install .NET 8 Desktop Runtime (x64), or run install-environment.ps1 as Administrator first.' -ForegroundColor Yellow
}
