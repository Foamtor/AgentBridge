# start API (+ web if node/pnpm available)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "Starting API on http://127.0.0.1:8000 ..."
$api = Start-Process -PassThru -NoNewWindow python -ArgumentList @(
  "-m", "uvicorn", "main:app", "--app-dir", "apps/api", "--reload", "--port", "8000"
)

$webDir = Join-Path $root "apps\web"
if (Test-Path (Join-Path $webDir "package.json")) {
  Push-Location $webDir
  if (Get-Command pnpm -ErrorAction SilentlyContinue) {
    Write-Host "Starting web on http://127.0.0.1:5173 ..."
    Start-Process -NoNewWindow pnpm -ArgumentList @("dev")
  } elseif (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Host "Starting web on http://127.0.0.1:5173 ..."
    Start-Process -NoNewWindow npm -ArgumentList @("run", "dev")
  } else {
    Write-Host "Skip web: pnpm/npm not found"
  }
  Pop-Location
}

Write-Host "API pid=$($api.Id). Press Ctrl+C in that window to stop, or run stop-dev.ps1"
