$ErrorActionPreference = "Stop"
$API = if ($env:API_BASE) { $env:API_BASE } else { "http://127.0.0.1:8000" }

Write-Host "== health =="
$h = Invoke-RestMethod -Uri "$API/health"
if ($h.status -ne "ok") { throw "health failed" }

$tid = "t-smoke-$(Get-Date -Format yyyyMMddHHmmss)"
Write-Host "== stream =="
$resp = Invoke-WebRequest -Uri "$API/chat/stream" -Method POST `
  -ContentType "application/json" `
  -Body (@{ query = "smoke"; thread_id = $tid; route = "echo" } | ConvertTo-Json)
if ($resp.StatusCode -ne 200) { throw "stream status $($resp.StatusCode)" }
if ($resp.Content -notmatch '"type":\s*"start"') { throw "missing start event" }

Write-Host "== cancel idle =="
try {
  Invoke-WebRequest -Uri "$API/chat/cancel" -Method POST `
    -ContentType "application/json" `
    -Body (@{ thread_id = "t-smoke-missing" } | ConvertTo-Json) | Out-Null
  throw "expected 404"
} catch {
  if ($_.Exception.Response.StatusCode.value__ -ne 404) { throw }
}

Write-Host "smoke_echo: ok (409 covered in pytest)"
