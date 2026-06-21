# publish23: 默认目录迁移已有账号库 + 多账号复用/切号 + 跨进程锁 + 默认数据库按钮
# Usage: powershell -ExecutionPolicy Bypass -File build-publish23.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Project = Join-Path $Root "WacliDesktop\WacliDesktop.csproj"
$Publish23 = Join-Path $Root "publish23"
$SourceOut = Join-Path $Publish23 "source"
$PortableOut = Join-Path $Publish23 "portable"
$RuntimeOut = Join-Path $Publish23 "runtime"
$SingleExe = Join-Path $Publish23 "ChitongLingxun-standalone.exe"
$MemorySrc = Join-Path $Root "publish23-memory.md"

function Stop-WacliDesktopApps {
    Get-Process WacliDesktop,ChitongLingxun -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 1
}

Stop-WacliDesktopApps

Write-Host "[1/10] Clean publish23 ..."
if (Test-Path $Publish23) { Remove-Item $Publish23 -Recurse -Force }
New-Item -ItemType Directory -Path $SourceOut, $PortableOut, $RuntimeOut -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $RuntimeOut "bin") -Force | Out-Null

$runtimeReadme = @"
赤瞳灵讯 · runtime 目录 (publish23)
====================================
WhatsApp 数据库默认在：%UserProfile%\ChitongLingxun
修改默认数据库根目录时，已登记账号库会尝试整体迁移
"@
Set-Content -Path (Join-Path $RuntimeOut "README.txt") -Encoding UTF8 -Value $runtimeReadme

$iconPng = Join-Path $Root "WacliDesktop\Assets\app-icon.png"
$iconIco = Join-Path $Root "WacliDesktop\Assets\app-icon.ico"
if (Test-Path $iconPng) {
    python -c "from PIL import Image; img=Image.open(r'$iconPng').convert('RGBA'); img.save(r'$iconIco', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])" 2>$null
}

Write-Host "[2/10] dotnet build Release ..."
dotnet build $Project -c Release
if ($LASTEXITCODE -ne 0) { throw "build failed" }

Write-Host "[3/10] Smoke test (Release) ..."
$debugExe = Join-Path $Root "WacliDesktop\bin\Release\net8.0-windows\WacliDesktop.exe"
if (-not (Test-Path $debugExe)) { throw "exe not found" }
$p = Start-Process -FilePath $debugExe -PassThru
Start-Sleep -Seconds 2
if ($p.HasExited) { throw "Smoke test failed" }
Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
Stop-WacliDesktopApps
Write-Host "      PASS"

Write-Host "[4/10] Publish portable ..."
dotnet publish $Project -c Release -r win-x64 `
    --self-contained true `
    -p:PublishSingleFile=false `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -o $PortableOut
if ($LASTEXITCODE -ne 0) { throw "portable publish failed" }

Write-Host "[5/10] Publish single-file exe ..."
$tempSingle = Join-Path $env:TEMP ("wacli-publish23-single-" + [guid]::NewGuid().ToString("n"))
dotnet publish $Project -c Release -r win-x64 `
    --self-contained true `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:IncludeAllContentForSelfExtract=true `
    -p:EnableCompressionInSingleFile=true `
    -o $tempSingle
if ($LASTEXITCODE -ne 0) { throw "single-file publish failed" }
Copy-Item (Join-Path $tempSingle "WacliDesktop.exe") $SingleExe -Force
Remove-Item $tempSingle -Recurse -Force -ErrorAction SilentlyContinue
Stop-WacliDesktopApps

Write-Host "[6/10] Smoke test portable + single ..."
foreach ($exe in @((Join-Path $PortableOut "WacliDesktop.exe"), $SingleExe)) {
    $px = Start-Process -FilePath $exe -PassThru
    Start-Sleep -Seconds 2
    if ($px.HasExited) { throw "Smoke test failed: $exe" }
    Stop-Process -Id $px.Id -Force -ErrorAction SilentlyContinue
}
Stop-WacliDesktopApps
Write-Host "      PASS"

Write-Host "[7/10] Pack source ..."
$exclude = @('bin', 'obj', 'publish', 'publish1', 'publish2', 'publish3', 'publish4', 'publish5', 'publish6', 'publish7', 'publish8', 'publish9', 'publish10', 'publish11', 'publish12', 'publish20', 'publish21', 'publish22', 'publish23', '.vs')
Get-ChildItem $Root -Force | Where-Object { $_.Name -notin $exclude } | ForEach-Object {
    Copy-Item $_.FullName -Destination (Join-Path $SourceOut $_.Name) -Recurse -Force
}
Get-ChildItem $SourceOut -Recurse -Directory -Filter bin -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem $SourceOut -Recurse -Directory -Filter obj -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

Write-Host "[8/10] memory.md ..."
if (Test-Path $MemorySrc) {
    Copy-Item $MemorySrc (Join-Path $Publish23 "memory.md") -Force
    Copy-Item $MemorySrc (Join-Path $SourceOut "publish23-memory.md") -Force
}

Set-Content -Path (Join-Path $PortableOut "start.bat") -Encoding ASCII -Value '@start "" "%~dp0WacliDesktop.exe"'
Set-Content -Path (Join-Path $Publish23 "start.bat") -Encoding ASCII -Value '@start "" "%~dp0portable\WacliDesktop.exe"'

Write-Host "[9/10] Launcher ..."
$LauncherProject = Join-Path $Root "WacliDesktopLauncher\WacliDesktopLauncher.csproj"
dotnet publish $LauncherProject -c Release -r win-x64 --self-contained false -o (Join-Path $env:TEMP "wacli-launcher-out23")
Copy-Item (Join-Path $env:TEMP "wacli-launcher-out23\wacli-desktop.exe") (Join-Path $Publish23 "wacli-desktop.exe") -Force -ErrorAction SilentlyContinue

Write-Host "[10/10] Done"
Write-Host ""
Write-Host "publish23 ready:"
Write-Host "  $Publish23"
