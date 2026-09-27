<#
Start the three services in their own PowerShell windows, wait until each answers, then open the app.

    powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1
    powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1 -Database expense_intelligence_demo -NoBrowser

  -Database   use another PostgreSQL database for this run (overrides DATABASE_NAME from backend\.env)
  -NoBrowser  do not open http://localhost:5173 at the end

Close a service by closing its window (or Ctrl+C in it). Assumes the setup in docs/installation.md is done.
#>
param(
    [string]$Database = "",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Start-Service-Window($title, $folder, $command) {
    $script = "`$Host.UI.RawUI.WindowTitle = '$title'; Set-Location -LiteralPath '$folder'; $command"
    # -NoProfile: a personal PowerShell profile (e.g. a conda hook) must not change which Python runs.
    $process = Start-Process powershell -ArgumentList "-NoProfile", "-NoExit", "-Command", $script -PassThru
    Write-Host ("Started {0,-22} (window PID {1})" -f $title, $process.Id)
}

function Wait-Until($name, $url, $seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 | Out-Null
            Write-Host "  $name is up ($url)" -ForegroundColor Green
            return $true
        } catch { Start-Sleep -Seconds 2 }
    }
    Write-Host "  $name did not answer within $seconds s: check its window." -ForegroundColor Yellow
    return $false
}

$databaseLine = ""
if ($Database) { $databaseLine = "`$env:DATABASE_NAME = '$Database'; " }

Start-Service-Window "ML service :8001" "$root\ml-service" ".\venv\Scripts\python.exe -m uvicorn main:app --port 8001"
Start-Service-Window "Django API :8000" "$root\backend" "$databaseLine.\venv\Scripts\python.exe manage.py runserver 8000"
# node is called directly: npm's .cmd launchers break on the '&' in the project folder name (troubleshooting.md).
Start-Service-Window "React :5173" "$root\frontend" "node node_modules/vite/bin/vite.js"

Write-Host "Waiting for the services (the first start after installing can take a few minutes: Windows Defender)..."
$ok = (Wait-Until "ML service" "http://127.0.0.1:8001/health" 300) -and
      (Wait-Until "Django API" "http://127.0.0.1:8000/api/health/" 180) -and
      (Wait-Until "React app" "http://localhost:5173/" 120)

if ($ok -and -not $NoBrowser) { Start-Process "http://localhost:5173/" }
if ($ok) { Write-Host "All services are running." -ForegroundColor Green }
