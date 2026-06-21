# publish10: portable runtime folder + git-build wacli on env setup (赤瞳灵讯)
# Usage: powershell -ExecutionPolicy Bypass -File build-publish10.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Project = Join-Path $Root "WacliDesktop\WacliDesktop.csproj"
$Publish10 = Join-Path $Root "publish10"
$SourceOut = Join-Path $Publish10 "source"
$PortableOut = Join-Path $Publish10 "portable"
$RuntimeOut = Join-Path $Publish10 "runtime"
$SingleExe = Join-Path $Publish10 "ChitongLingxun-standalone.exe"

function Stop-WacliDesktopApps {
    Get-Process WacliDesktop -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 1
}

Stop-WacliDesktopApps

Write-Host "[1/9] Clean publish10 ..."
if (Test-Path $Publish10) { Remove-Item $Publish10 -Recurse -Force }
New-Item -ItemType Directory -Path $SourceOut, $PortableOut, $RuntimeOut -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $RuntimeOut "bin"), (Join-Path $RuntimeOut "data") -Force | Out-Null

$runtimeReadme = @"
赤瞳灵讯 · runtime 目录
========================
首次使用请点击软件内「配置环境」，将自动：
  1. git clone wacli 到 runtime\src\wacli\
  2. 编译 wacli.exe 到 runtime\bin\
  3. 消息与附件写入 runtime\data\

整包拷贝 publish10 文件夹即可迁移；新电脑仍需配置环境编译 wacli。
"@
Set-Content -Path (Join-Path $RuntimeOut "README.txt") -Encoding UTF8 -Value $runtimeReadme

$iconPng = Join-Path $Root "WacliDesktop\Assets\app-icon.png"
$iconIco = Join-Path $Root "WacliDesktop\Assets\app-icon.ico"
if (Test-Path $iconPng) {
    python -c "from PIL import Image; img=Image.open(r'$iconPng').convert('RGBA'); img.save(r'$iconIco', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])" 2>$null
}

Write-Host "[2/9] dotnet build Release ..."
dotnet build $Project -c Release
if ($LASTEXITCODE -ne 0) { throw "build failed" }

Write-Host "[3/9] Smoke test (Release) ..."
$debugExe = Join-Path $Root "WacliDesktop\bin\Release\net8.0-windows\WacliDesktop.exe"
if (-not (Test-Path $debugExe)) { throw "exe not found" }
$p = Start-Process -FilePath $debugExe -PassThru
Start-Sleep -Seconds 2
if ($p.HasExited) { throw "Smoke test failed" }
Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
Stop-WacliDesktopApps
Write-Host "      PASS"

Write-Host "[4/9] Publish portable folder ..."
dotnet publish $Project -c Release -r win-x64 `
    --self-contained true `
    -p:PublishSingleFile=false `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -o $PortableOut
if ($LASTEXITCODE -ne 0) { throw "portable publish failed" }

Write-Host "[5/9] Publish single-file exe ..."
Stop-WacliDesktopApps
$tempSingle = Join-Path $env:TEMP ("wacli-publish10-single-" + [guid]::NewGuid().ToString("n"))
if (Test-Path $tempSingle) { Remove-Item $tempSingle -Recurse -Force }
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

Write-Host "[6/9] Smoke test (portable + single) ..."
foreach ($exe in @((Join-Path $PortableOut "WacliDesktop.exe"), $SingleExe)) {
    $px = Start-Process -FilePath $exe -PassThru
    Start-Sleep -Seconds 2
    if ($px.HasExited) { throw "Smoke test failed: $exe" }
    Stop-Process -Id $px.Id -Force -ErrorAction SilentlyContinue
}
Stop-WacliDesktopApps
Write-Host "      PASS"

Write-Host "[7/9] Pack source ..."
$exclude = @('bin', 'obj', 'publish', 'publish1', 'publish2', 'publish3', 'publish4', 'publish5', 'publish6', 'publish7', 'publish8', 'publish9', 'publish10', '.vs')
Get-ChildItem $Root -Force | Where-Object { $_.Name -notin $exclude } | ForEach-Object {
    Copy-Item $_.FullName -Destination (Join-Path $SourceOut $_.Name) -Recurse -Force
}
Get-ChildItem $SourceOut -Recurse -Directory -Filter bin -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem $SourceOut -Recurse -Directory -Filter obj -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

Set-Content -Path (Join-Path $PortableOut "start.bat") -Encoding ASCII -Value '@start "" "%~dp0WacliDesktop.exe"'
Set-Content -Path (Join-Path $Publish10 "start.bat") -Encoding ASCII -Value '@start "" "%~dp0portable\WacliDesktop.exe"'

Write-Host "[8/9] Build wacli-desktop launcher ..."
$LauncherProject = Join-Path $Root "WacliDesktopLauncher\WacliDesktopLauncher.csproj"
dotnet publish $LauncherProject -c Release -r win-x64 --self-contained false -o (Join-Path $env:TEMP "wacli-launcher-out")
if ($LASTEXITCODE -ne 0) { throw "launcher build failed" }
Copy-Item (Join-Path $env:TEMP "wacli-launcher-out\wacli-desktop.exe") (Join-Path $Publish10 "wacli-desktop.exe") -Force

Write-Host "[9/9] Done"
Write-Host ""
Write-Host "Done - publish10 (赤瞳灵讯 · portable runtime)"
Write-Host "  Source:   $SourceOut"
Write-Host "  Portable: $PortableOut"
Write-Host "  Runtime:  $RuntimeOut  (配置环境后填充 bin/ 与 data/)"
Write-Host "  Single:   $SingleExe"
