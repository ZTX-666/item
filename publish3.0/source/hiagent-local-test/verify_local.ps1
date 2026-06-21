# 本机验证（不依赖 HiAgent / 不依赖公网）
$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:8787"

Write-Host "=== 1. 检查端口 8787 是否在监听 ===" -ForegroundColor Cyan
$listen = Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue
if ($listen) {
    Write-Host "OK: port 8787 is listening" -ForegroundColor Green
} else {
    Write-Host "FAIL: nothing listening on 8787. Run start.bat first." -ForegroundColor Red
    exit 1
}

Write-Host "`n=== 2. 调用 /health ===" -ForegroundColor Cyan
$h = Invoke-RestMethod "$base/health"
$h | ConvertTo-Json

Write-Host "`n=== 3. 调用 /api/messages/search?limit=3 ===" -ForegroundColor Cyan
try {
    $m = Invoke-RestMethod "$base/api/messages/search?limit=3"
    Write-Host "OK: got $($m.count) messages"
} catch {
    Write-Host "WARN: $($_.Exception.Message)"
    Write-Host "      (若尚无 wacli.db，可先完成赤瞳 sync)"
}

Write-Host "`n=== 4. 离线导出（给 HiAgent 上传文件用）===" -ForegroundColor Cyan
Set-Location $PSScriptRoot
python export_sample_json.py --limit 5
if (Test-Path "sample_messages.json") {
    Write-Host "OK: sample_messages.json ready to upload into HiAgent chat"
}

Write-Host "`n=== 若要让云端 HiAgent 访问本机 ===" -ForegroundColor Yellow
Write-Host "运行 start-with-cloudflared.bat，把生成的 https://*.trycloudflare.com 配到 HiAgent"
Write-Host "不要用 127.0.0.1 — 云端永远访问不了本机回环地址"
