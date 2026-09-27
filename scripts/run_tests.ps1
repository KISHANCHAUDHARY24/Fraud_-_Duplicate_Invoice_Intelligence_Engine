<#
Run every automated test suite and print one summary (docs/testing.md).

    powershell -ExecutionPolicy Bypass -File scripts\run_tests.ps1
    powershell -ExecutionPolicy Bypass -File scripts\run_tests.ps1 -Live     # also the 5 live end-to-end tests

-Live needs the ML service running on port 8001 with a trained model.
#>
param([switch]$Live)

$root = Split-Path -Parent $PSScriptRoot
$results = @()

function Run-Suite($name, $folder, $command) {
    Write-Host "`n=== $name ===" -ForegroundColor Cyan
    Push-Location -LiteralPath $folder
    try {
        & powershell -NoProfile -Command $command
        $script:results += [pscustomobject]@{ Suite = $name; Result = if ($LASTEXITCODE -eq 0) { "PASSED" } else { "FAILED" } }
    } finally { Pop-Location }
}

$liveLine = if ($Live) { "`$env:ML_LIVE_TESTS = '1'; " } else { "" }
Run-Suite "Django" "$root\backend" "$liveLine.\venv\Scripts\python.exe manage.py test --noinput"
Run-Suite "ML service" "$root\ml-service" ".\venv\Scripts\python.exe -m pytest"
Run-Suite "Frontend tests" "$root\frontend" "node node_modules/vitest/vitest.mjs run"
Run-Suite "Frontend lint" "$root\frontend" "node node_modules/oxlint/bin/oxlint src"

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
$results | Format-Table -AutoSize
if ($results.Result -contains "FAILED") { exit 1 }
