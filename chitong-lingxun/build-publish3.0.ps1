# publish3.0: 主子页面 UI 统一 + 断链状态提示 + 数据库能力继承
# Usage: powershell -ExecutionPolicy Bypass -File build-publish3.0.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Project = Join-Path $Root "WacliDesktop\WacliDesktop.csproj"
$Publish = Join-Path $Root "publish3.0"
$SourceOut = Join-Path $Publish "source"
$PortableOut = Join-Path $Publish "portable"
$RuntimeOut = Join-Path $Publish "runtime"
$SingleExe = Join-Path $Publish "ChitongLingxun-standalone.exe"
$MemorySrc = Join-Path $Root "publish3.0-memory.md"
$FinalAgentSuite = Join-Path $Root "..\..\FinalAgentSuite"

function Stop-WacliDesktopApps {
    Get-Process WacliDesktop,ChitongLingxun -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 1
}

function Stop-AgentServices {
    Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -match "agent_toolbox|chitung_center" -or
        $_.CommandLine -match "run_server.py"
    } | Stop-Process -Force
}

function Write-Utf8NoBom {
    param($Path, $Value)
    [System.IO.File]::WriteAllText($Path, $Value, [System.Text.UTF8Encoding]::new($false))
}

function Update-DotEnv {
    param($Path, $Updates)
    $lines = if (Test-Path $Path) { Get-Content $Path } else { @() }
    $map = @{}
    foreach ($line in $lines) { $map[$line] = $line }
    $result = [System.Collections.Generic.List[string]]::new()
    $seen = @{}
    foreach ($line in $lines) {
        if ($line -match '^\s*([A-Za-z0-9_]+)\s*=') {
            $key = $matches[1]
            $seen[$key] = $true
            if ($Updates.ContainsKey($key)) {
                $result.Add("$key=$($Updates[$key])")
                continue
            }
        }
        $result.Add($line)
    }
    foreach ($kv in $Updates.GetEnumerator()) {
        if (-not $seen[$kv.Key]) {
            $result.Add("$($kv.Key)=$($kv.Value)")
        }
    }
    Write-Utf8NoBom -Path $Path -Value ($result -join "`r`n")
}

Stop-WacliDesktopApps
Stop-AgentServices

Write-Host "[1/11] Clean publish3.0 ..."
if (Test-Path $Publish) { Remove-Item $Publish -Recurse -Force }
New-Item -ItemType Directory -Path $SourceOut, $PortableOut, $RuntimeOut -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $RuntimeOut "bin") -Force | Out-Null

$runtimeReadme = @"
赤瞳灵讯 · runtime 目录 (publish3.0)
====================================
主页面固定尺寸，子页面可拖动调整
状态条支持「链接断开」红灯提示
新增「赤瞳工具箱」模块：WhatsApp 搜索、隐患案例、表格模板
"@
Set-Content -Path (Join-Path $RuntimeOut "README.txt") -Encoding UTF8 -Value $runtimeReadme

$iconPng = Join-Path $Root "WacliDesktop\Assets\app-icon.png"
$iconIco = Join-Path $Root "WacliDesktop\Assets\app-icon.ico"
if (Test-Path $iconPng) {
    python -c "from PIL import Image; img=Image.open(r'$iconPng').convert('RGBA'); img.save(r'$iconIco', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])" 2>$null
}

Write-Host "[2/11] dotnet build Release ..."
dotnet build $Project -c Release
if ($LASTEXITCODE -ne 0) { throw "build failed" }

Write-Host "[3/11] Smoke test (Release) ..."
$debugExe = Join-Path $Root "WacliDesktop\bin\Release\net8.0-windows\WacliDesktop.exe"
if (-not (Test-Path $debugExe)) { throw "exe not found" }
$p = Start-Process -FilePath $debugExe -PassThru
Start-Sleep -Seconds 2
if ($p.HasExited) { throw "Smoke test failed" }
Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
Stop-WacliDesktopApps
Write-Host "      PASS"

Write-Host "[4/11] Publish portable ..."
dotnet publish $Project -c Release -r win-x64 `
    --self-contained true `
    -p:PublishSingleFile=false `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -o $PortableOut
if ($LASTEXITCODE -ne 0) { throw "portable publish failed" }

Write-Host "[5/11] Publish single-file exe ..."
$tempSingle = Join-Path $env:TEMP ("wacli-publish3.0-single-" + [guid]::NewGuid().ToString("n"))
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

Write-Host "[6/11] Smoke test portable + single ..."
foreach ($exe in @((Join-Path $PortableOut "WacliDesktop.exe"), $SingleExe)) {
    $px = Start-Process -FilePath $exe -PassThru
    Start-Sleep -Seconds 2
    if ($px.HasExited) { throw "Smoke test failed: $exe" }
    Stop-Process -Id $px.Id -Force -ErrorAction SilentlyContinue
}
Stop-WacliDesktopApps
Write-Host "      PASS"

Write-Host "[7/11] Agent services (AgentToolbox + chitung-center) ..."
$AgentServicesOut = Join-Path $Publish "agent-services"
New-Item -ItemType Directory -Path $AgentServicesOut -Force | Out-Null

$AgentToolboxSrc = Join-Path $FinalAgentSuite "agent-toolbox"
$ChitungCenterSrc = Join-Path $FinalAgentSuite "chitung-center"

if (-not (Test-Path $AgentToolboxSrc)) { throw "agent-toolbox source not found: $AgentToolboxSrc" }
if (-not (Test-Path $ChitungCenterSrc)) { throw "chitung-center source not found: $ChitungCenterSrc" }

$AgentToolboxOut = Join-Path $AgentServicesOut "agent-toolbox"
$ChitungCenterOut = Join-Path $AgentServicesOut "chitung-center"

# Copy source while excluding heavy/relocatable directories using robocopy for speed
function Copy-AgentService($src, $dst) {
    New-Item -ItemType Directory -Path $dst -Force | Out-Null
    $xd = @('.venv', '__pycache__', '.git', 'node_modules')
    robocopy $src $dst /MIR /E /R:2 /W:1 /XD @xd /NP /NFL /NDL
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $src -> $dst (exit $LASTEXITCODE)" }
}

Copy-AgentService $AgentToolboxSrc $AgentToolboxOut
Copy-AgentService $ChitungCenterSrc $ChitungCenterOut

# Copy safety form templates so search_form_templates works on a relocated package
$TemplatesSrc = Join-Path $FinalAgentSuite "safety-policy-templates-20241025"
$TemplatesOut = Join-Path $AgentServicesOut "safety-policy-templates"
if (Test-Path $TemplatesSrc) {
    robocopy $TemplatesSrc $TemplatesOut /MIR /E /R:2 /W:1 /NP /NFL /NDL
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed for templates -> $TemplatesOut (exit $LASTEXITCODE)" }
}

# Patch bundled .env files to use relative package-local paths (cwd = package root when launched via start.bat)
$atEnv = Join-Path $AgentToolboxOut ".env"
Update-DotEnv $atEnv @{
    "AGENT_TOOLBOX_ROOT" = "agent-services\agent-toolbox"
    "AGENT_TOOLBOX_WORKSPACE" = "agent-services\agent-toolbox\workspace"
    "SAFETY_POLICY_TEMPLATES_DIR" = "agent-services\safety-policy-templates"
    "SAFETY_DATABASE_PATH" = "agent-services\agent-toolbox\workspace\safety_platform.db"
    "WHATSAPP_ARCHIVE_BASE_URL" = "http://127.0.0.1:8787"
}

$ccEnv = Join-Path $ChitungCenterOut ".env"
Update-DotEnv $ccEnv @{
    "CHITUNG_DATA_DIR" = "agent-services\chitung-center\data"
    "CHITUNG_SKILLS_DIR" = "agent-services\chitung-center\skills"
    "CHITUNG_AUDIT_LOG" = "agent-services\chitung-center\data\audit.jsonl"
    "AGENT_TOOLBOX_BASE_URL" = "http://127.0.0.1:8899"
}

Write-Host "[8/11] Pack source ..."
$exclude = @('bin', 'obj', 'publish', 'publish1', 'publish2', 'publish3', 'publish4', 'publish5', 'publish6', 'publish7', 'publish8', 'publish9', 'publish10', 'publish11', 'publish12', 'publish20', 'publish21', 'publish22', 'publish23', 'publish3.0', '.vs')
Get-ChildItem $Root -Force | Where-Object { $_.Name -notin $exclude } | ForEach-Object {
    Copy-Item $_.FullName -Destination (Join-Path $SourceOut $_.Name) -Recurse -Force
}
Get-ChildItem $SourceOut -Recurse -Directory -Filter bin -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem $SourceOut -Recurse -Directory -Filter obj -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

Write-Host "[9/11] memory.md ..."
if (Test-Path $MemorySrc) {
    Copy-Item $MemorySrc (Join-Path $Publish "memory.md") -Force
    Copy-Item $MemorySrc (Join-Path $SourceOut "publish3.0-memory.md") -Force
}

Write-Host "[10/11] Generate startup scripts ..."
$portableStartBat = @'
@echo off
start "" "%~dp0WacliDesktop.exe"
'@

$publishStartBat = @'
@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
set BASE=%~dp0

echo [赤瞳灵讯] 启动服务环境...

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python。请安装 Python 3.11+ 并添加到 PATH 后再运行。
    pause
    exit /b 1
)

REM AgentToolbox (赤瞳工具箱后端，端口 8899)
set AT_DIR=%BASE%agent-services\agent-toolbox
set AT_VENV=%AT_DIR%\.venv
set AT_PY=%AT_VENV%\Scripts\python.exe
if not exist "%AT_VENV%" (
    echo [AgentToolbox] 创建虚拟环境...
    python -m venv "%AT_VENV%"
    if errorlevel 1 (
        echo [错误] 无法创建 AgentToolbox 虚拟环境
        pause
        exit /b 1
    )
    echo [AgentToolbox] 安装依赖（首次启动需要）...
    "%AT_PY%" -m pip install -q -r "%AT_DIR%\requirements.txt"
    if errorlevel 1 (
        echo [错误] 无法安装 AgentToolbox 依赖
        pause
        exit /b 1
    )
)
echo [AgentToolbox] 启动 http://127.0.0.1:8899 ...
start "AgentToolbox" /min "%AT_PY%" "%AT_DIR%\run_server.py"

REM Chitung Center (编排中心，端口 8999)
set CC_DIR=%BASE%agent-services\chitung-center
set CC_VENV=%CC_DIR%\.venv
set CC_PY=%CC_VENV%\Scripts\python.exe
if not exist "%CC_VENV%" (
    echo [ChitungCenter] 创建虚拟环境...
    python -m venv "%CC_VENV%"
    if errorlevel 1 (
        echo [错误] 无法创建 ChitungCenter 虚拟环境
        pause
        exit /b 1
    )
    echo [ChitungCenter] 安装依赖（首次启动需要）...
    "%CC_PY%" -m pip install -q -r "%CC_DIR%\requirements.txt"
    if errorlevel 1 (
        echo [警告] 无法安装 ChitungCenter 依赖，将继续启动主程序
    )
)
if exist "%CC_PY%" (
    echo [ChitungCenter] 启动 http://127.0.0.1:8999 ...
    start "ChitungCenter" /min "%CC_PY%" "%CC_DIR%\run_server.py"
) else (
    echo [ChitungCenter] 跳过（未创建虚拟环境）
)

echo [赤瞳灵讯] 等待服务就绪...
timeout /t 4 /nobreak >nul

echo [赤瞳灵讯] 启动主程序...
start "" "%BASE%portable\WacliDesktop.exe"
'@

Write-Utf8NoBom -Path (Join-Path $PortableOut "start.bat") -Value $portableStartBat
Write-Utf8NoBom -Path (Join-Path $Publish "start.bat") -Value $publishStartBat

# Update the source-level start.bat to point to the current publish3.0
$sourceStartBat = @'
@echo off
start "" "%~dp0publish3.0\portable\WacliDesktop.exe"
'@
Write-Utf8NoBom -Path (Join-Path $Root "start.bat") -Value $sourceStartBat

Write-Host "[11/11] Launcher ..."
$LauncherProject = Join-Path $Root "WacliDesktopLauncher\WacliDesktopLauncher.csproj"
dotnet publish $LauncherProject -c Release -r win-x64 --self-contained false -o (Join-Path $env:TEMP "wacli-launcher-out3.0")
Copy-Item (Join-Path $env:TEMP "wacli-launcher-out3.0\wacli-desktop.exe") (Join-Path $Publish "wacli-desktop.exe") -Force -ErrorAction SilentlyContinue

Write-Host "[11/11] Done"
Write-Host ""
Write-Host "publish3.0 ready:"
Write-Host "  $Publish"
