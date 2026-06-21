# publish1: source + portable self-contained build with smoke test
# Usage: powershell -ExecutionPolicy Bypass -File build-publish1.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Project = Join-Path $Root "WacliDesktop\WacliDesktop.csproj"
$Publish1 = Join-Path $Root "publish1"
$SourceOut = Join-Path $Publish1 "source"
$PortableOut = Join-Path $Publish1 "portable"

Write-Host "[1/6] Clean publish1 ..."
if (Test-Path $Publish1) { Remove-Item $Publish1 -Recurse -Force }
New-Item -ItemType Directory -Path $SourceOut, $PortableOut -Force | Out-Null

Write-Host "[2/6] dotnet build Release ..."

# Regenerate multi-size ICO from PNG (Windows exe icon)
$iconPng = Join-Path $Root "WacliDesktop\Assets\app-icon.png"
$iconIco = Join-Path $Root "WacliDesktop\Assets\app-icon.ico"
if (Test-Path $iconPng) {
    python -c "from PIL import Image; img=Image.open(r'$iconPng').convert('RGBA'); img.save(r'$iconIco', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])" 2>$null
}

dotnet build $Project -c Release
if ($LASTEXITCODE -ne 0) { throw "build failed" }

Write-Host "[3/6] Smoke test (Release build) ..."
$debugExe = Join-Path $Root "WacliDesktop\bin\Release\net8.0-windows\WacliDesktop.exe"
if (-not (Test-Path $debugExe)) {
    $debugExe = Join-Path $Root "WacliDesktop\bin\Release\net8.0-windows\win-x64\WacliDesktop.exe"
}
if (-not (Test-Path $debugExe)) { throw "WacliDesktop.exe not found after build" }
$p = Start-Process -FilePath $debugExe -PassThru
Start-Sleep -Seconds 2
if ($p.HasExited) { throw "Smoke test failed: process exited with code $($p.ExitCode)" }
Stop-Process -Id $p.Id -Force
Write-Host "      PASS"

Write-Host "[4/6] Publish portable (self-contained win-x64) ..."
dotnet publish $Project -c Release -r win-x64 `
    --self-contained true `
    -p:PublishSingleFile=false `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -o $PortableOut
if ($LASTEXITCODE -ne 0) { throw "publish failed" }

Write-Host "[5/6] Smoke test (portable) ..."
$portableExe = Join-Path $PortableOut "WacliDesktop.exe"
$p2 = Start-Process -FilePath $portableExe -PassThru
Start-Sleep -Seconds 2
if ($p2.HasExited) { throw "Portable smoke test failed" }
Stop-Process -Id $p2.Id -Force
Write-Host "      PASS"

Write-Host "[6/6] Pack source tree ..."
$exclude = @('bin', 'obj', 'publish', 'publish1', '.vs')
Get-ChildItem $Root -Force | Where-Object { $_.Name -notin $exclude } | ForEach-Object {
    Copy-Item $_.FullName -Destination (Join-Path $SourceOut $_.Name) -Recurse -Force
}
Get-ChildItem $SourceOut -Recurse -Directory -Filter bin -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem $SourceOut -Recurse -Directory -Filter obj -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

Set-Content -Path (Join-Path $SourceOut "start-dev.bat") -Encoding ASCII -Value @"
@echo off
cd /d "%~dp0WacliDesktop"
dotnet run -c Release
"@

Set-Content -Path (Join-Path $PortableOut "start.bat") -Encoding ASCII -Value @"
@echo off
start "" "%~dp0WacliDesktop.exe"
"@

$readme = @"
WhatsApp Local Sync Console (Portable)
======================================
Run WacliDesktop.exe - no .NET install required.

First time: click "Configure Environment" on home screen, then Login.
Data folder: %USERPROFILE%\.wacli\

Developer: Sean Xu
"@
Set-Content -Path (Join-Path $PortableOut "README.txt") -Encoding UTF8 -Value $readme

Write-Host ""
Write-Host "Done."
Write-Host "  Source:   $SourceOut"
Write-Host "  Portable: $PortableOut"
Write-Host "  Run:      $portableExe"
