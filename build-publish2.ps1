# publish2: single-file self-contained exe (one file only)
# Usage: powershell -ExecutionPolicy Bypass -File build-publish2.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Project = Join-Path $Root "WacliDesktop\WacliDesktop.csproj"
$Publish2 = Join-Path $Root "publish2"
$OutExe = Join-Path $Publish2 "WhatsApp本地同步中台.exe"

Write-Host "[1/4] Clean publish2 ..."
if (Test-Path $Publish2) { Remove-Item $Publish2 -Recurse -Force }
New-Item -ItemType Directory -Path $Publish2 -Force | Out-Null

$iconPng = Join-Path $Root "WacliDesktop\Assets\app-icon.png"
$iconIco = Join-Path $Root "WacliDesktop\Assets\app-icon.ico"
if (Test-Path $iconPng) {
    python -c "from PIL import Image; img=Image.open(r'$iconPng').convert('RGBA'); img.save(r'$iconIco', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])" 2>$null
}

Write-Host "[2/4] Publish single-file (self-contained win-x64) ..."
$tempOut = Join-Path $env:TEMP "wacli-publish2-temp"
if (Test-Path $tempOut) { Remove-Item $tempOut -Recurse -Force }

dotnet publish $Project -c Release -r win-x64 `
    --self-contained true `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:IncludeAllContentForSelfExtract=true `
    -p:EnableCompressionInSingleFile=true `
    -o $tempOut
if ($LASTEXITCODE -ne 0) { throw "publish failed" }

$built = Join-Path $tempOut "WacliDesktop.exe"
if (-not (Test-Path $built)) { throw "WacliDesktop.exe not found in publish output" }

Move-Item -Path $built -Destination $OutExe -Force
Remove-Item $tempOut -Recurse -Force -ErrorAction SilentlyContinue

# Ensure publish2 contains only the one exe
Get-ChildItem $Publish2 | Where-Object { $_.Name -ne (Split-Path $OutExe -Leaf) } | Remove-Item -Recurse -Force

Write-Host "[3/4] Smoke test ..."
$p = Start-Process -FilePath $OutExe -PassThru
Start-Sleep -Seconds 3
if ($p.HasExited) { throw "Smoke test failed: exit $($p.ExitCode)" }
Stop-Process -Id $p.Id -Force
Write-Host "      PASS"

$sizeMb = [math]::Round((Get-Item $OutExe).Length / 1MB, 1)
Write-Host "[4/4] Done."
Write-Host ""
Write-Host "  Output:  $OutExe"
Write-Host "  Size:    ${sizeMb} MB"
Write-Host ""
Write-Host "  Distribute this single file. First run: Configure Environment -> Login."
