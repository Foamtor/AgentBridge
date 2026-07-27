# stop processes started by start-dev.ps1 (best-effort)
Get-Process -Name "uvicorn","node" -ErrorAction SilentlyContinue |
  Where-Object { $_.Path -like "*AgentBridge*" -or $_.CommandLine -like "*apps/api*" } |
  Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "stop-dev: attempted to stop local API/web processes"
