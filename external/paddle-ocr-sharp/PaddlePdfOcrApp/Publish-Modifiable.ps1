param(
    [ValidateSet('Framework', 'SelfContained')]
    [string] $Mode = 'Framework',
    [string] $OutputRelative = 'publish\modifiable_dev'
)
# Multi-file publish for iteration: edit .cs/.xaml then re-run.
# Framework = needs .NET 8 Desktop Runtime on target PC. SelfContained = larger, no runtime install.

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$dotnet = if (Test-Path "$env:LOCALAPPDATA\Microsoft\dotnet\dotnet.exe") {
    "$env:LOCALAPPDATA\Microsoft\dotnet\dotnet.exe"
} else {
    'dotnet'
}

$out = Join-Path $here $OutputRelative
$selfContained = if ($Mode -eq 'SelfContained') { 'true' } else { 'false' }

Write-Host "Mode: $Mode -> $out" -ForegroundColor Cyan

& $dotnet publish 'PaddlePdfOcrApp.csproj' `
    -c Release `
    -r win-x64 `
    --self-contained $selfContained `
    /p:PublishSingleFile=false `
    /p:DebugType=portable `
    /p:DebugSymbols=true `
    -o $out

Write-Host 'Publish finished. Edit source, then run this script again.' -ForegroundColor Green
if ($Mode -eq 'Framework') {
    Write-Host 'Target machines need: .NET 8 Desktop Runtime (win-x64).' -ForegroundColor Yellow
}
