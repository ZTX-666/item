# Test whether company HiAgent can reach local DB, and whether you can reach company MySQL.
# Usage: powershell -ExecutionPolicy Bypass -File test-db-reachability.ps1

$ErrorActionPreference = "Continue"
$here = $PSScriptRoot
$root = Split-Path (Split-Path $here -Parent) -Parent

function Write-Section($title) {
    Write-Host ""
    Write-Host "=== $title ===" -ForegroundColor Cyan
}

function Find-WacliDb {
    $candidates = @(
        (Join-Path $root "source\publish12\runtime\data\wacli.db"),
        (Join-Path $root "source\publish11\runtime\data\wacli.db"),
        (Join-Path $root "source\publish10\runtime\data\wacli.db"),
        (Join-Path $env:USERPROFILE ".wacli\wacli.db")
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return (Resolve-Path $p).Path }
    }
    return $null
}

Write-Section "0. DB type"
Write-Host "Chitong uses SQLite (wacli.db). HiAgent form needs MySQL host:port, not a SQLite file path."

Write-Section "1. Local SQLite (wacli.db)"
$db = Find-WacliDb
if (-not $db) {
    Write-Host "wacli.db not found. Run Chitong and sync WhatsApp first." -ForegroundColor Yellow
} else {
    Write-Host "OK: $db" -ForegroundColor Green
    $len = (Get-Item $db).Length
    Write-Host "Size MB: $([math]::Round($len / 1MB, 2))"
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) {
        $countPy = Join-Path $here "_count_messages.py"
        @"
import sqlite3
c = sqlite3.connect(r'''$($db.Replace("'", "''"))''')
n = c.execute('select count(*) from messages where revoked=0 and deleted_for_me=0').fetchone()[0]
print('active messages:', n)
"@ | Set-Content $countPy -Encoding UTF8
        python $countPy 2>$null
        Remove-Item $countPy -Force -ErrorAction SilentlyContinue
    }
}

Write-Section "2. Local MySQL listening on 3306"
$mysqlListen = Get-NetTCPConnection -LocalPort 3306 -State Listen -ErrorAction SilentlyContinue
if ($mysqlListen) {
    Write-Host "OK: port 3306 is listening (PID $($mysqlListen[0].OwningProcess))" -ForegroundColor Green
} else {
    Write-Host "Port 3306 not listening. Company cannot reach MySQL on this PC unless you start MySQL." -ForegroundColor Yellow
}

Write-Section "3. Public internet -> your PC"
try {
    $pubIp = (Invoke-RestMethod -Uri "https://api.ipify.org" -TimeoutSec 8).Trim()
    Write-Host "Your public IP (reference): $pubIp"
} catch {
    Write-Host "Could not get public IP: $($_.Exception.Message)" -ForegroundColor Yellow
    $pubIp = "unknown"
}

Write-Host "HiAgent may ask for a public host. Even with IP $pubIp, port 3306 is usually blocked by NAT/firewall."
Write-Host "Connection test from cloud to your home/office PC often FAILS - this is normal."

Write-Section "4. Your PC -> company MySQL"
$testPy = Join-Path $here "test_company_mysql.py"
if (-not (Test-Path $testPy)) {
    Write-Host "Missing test_company_mysql.py"
} elseif (-not $env:MYSQL_TEST_HOST) {
    Write-Host "Skipped. Set env vars then run python test_company_mysql.py" -ForegroundColor Yellow
    Write-Host '  $env:MYSQL_TEST_HOST="company-host"'
    Write-Host '  $env:MYSQL_TEST_PORT="3306"'
    Write-Host '  $env:MYSQL_TEST_USER="user"'
    Write-Host '  $env:MYSQL_TEST_PASS="password"'
    Write-Host '  $env:MYSQL_TEST_DB="dbname"'
} else {
    python $testPy
}

Write-Section "5. Local HTTP API port 8787"
$api8787 = Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue
if ($api8787) {
    Write-Host "OK: 8787 listening - use verify_local.ps1 for /health" -ForegroundColor Green
    Write-Host "This is HTTP API, not MySQL database form."
} else {
    Write-Host "8787 not listening. Start Chitong HiAgent bridge or local_test_server.py"
}

Write-Section "6. HiAgent console (final)"
Write-Host "Create database -> MySQL -> fill IT host (not 127.0.0.1) -> Connection test"
Write-Host "Recommended: test company MySQL (step 4), sync wacli data there, not expose local PC."

Write-Section "Lab only - tunnel (may violate company policy)"
Write-Host "cloudflared tunnel --url tcp://localhost:3306  (personal lab only, no real business data)"

Write-Host ""
Write-Host "See TEST_DB_REACHABILITY.md" -ForegroundColor Gray
