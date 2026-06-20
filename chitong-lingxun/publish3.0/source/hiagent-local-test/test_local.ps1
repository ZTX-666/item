# 本机自测脚本（无需 HiAgent）
$base = "http://127.0.0.1:8787"

Write-Host "GET $base/health"
Invoke-RestMethod "$base/health" | ConvertTo-Json -Depth 5

Write-Host "`nGET $base/api/ping"
Invoke-RestMethod "$base/api/ping" | ConvertTo-Json -Depth 5

Write-Host "`nGET $base/api/messages/search?limit=3"
try {
    Invoke-RestMethod "$base/api/messages/search?limit=3" | ConvertTo-Json -Depth 6
} catch {
    Write-Host "  (若无 wacli.db 会 404，可先完成赤瞳 sync)"
}

Write-Host "`nPOST $base/api/upload"
$body = @{
    source = "powershell-test"
    query  = "test"
    items  = @(@{ msg_id = "demo-1"; text = "hello" })
    note   = "local self test"
} | ConvertTo-Json -Depth 5
Invoke-RestMethod "$base/api/upload" -Method Post -Body $body -ContentType "application/json" | ConvertTo-Json

Write-Host "`n上传日志: hiagent-local-test\logs\uploads.jsonl"
