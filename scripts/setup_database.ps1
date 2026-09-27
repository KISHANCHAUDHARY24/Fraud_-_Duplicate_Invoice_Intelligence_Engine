<#
.SYNOPSIS
    Creates the PostgreSQL user and database for the backend, using the
    values in backend\.env (DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD).

.DESCRIPTION
    psql will prompt for the password of the PostgreSQL superuser ("postgres")
    that you chose when installing PostgreSQL. That password is typed into psql
    directly and is never stored by this script.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\setup_database.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\setup_database.ps1 -PgBin "C:\Program Files\PostgreSQL\sql-17\bin"
#>
param(
    [string]$PgBin = "",
    [string]$SuperUser = "postgres"
)

$ErrorActionPreference = "Stop"

$envFile = Join-Path $PSScriptRoot "..\backend\.env"
if (-not (Test-Path $envFile)) {
    throw "backend\.env not found. Copy backend\.env.example to backend\.env first."
}

# Read KEY=VALUE pairs from backend\.env
$config = @{}
foreach ($line in Get-Content $envFile) {
    if ($line -match '^\s*([A-Z_]+)\s*=\s*(.*)\s*$') { $config[$Matches[1]] = $Matches[2] }
}
foreach ($key in "DATABASE_NAME", "DATABASE_USER", "DATABASE_PASSWORD") {
    if (-not $config[$key]) { throw "$key is empty in backend\.env" }
}

if (-not $PgBin) {
    # Use psql from PATH if available, otherwise search the default install folder
    # (folder names vary: "17", "sql-17", ...). Newest version first.
    $onPath = Get-Command psql.exe -ErrorAction SilentlyContinue
    $found = if ($onPath) { $onPath.Source } else {
        Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not $found) { throw "psql.exe not found. Pass -PgBin with your PostgreSQL bin folder." }
    $PgBin = Split-Path $found
}

$psql = Join-Path $PgBin "psql.exe"
if (-not (Test-Path $psql)) {
    throw "psql.exe not found at $psql. Pass -PgBin with your PostgreSQL bin folder."
}

$dbHost = if ($config["DATABASE_HOST"]) { $config["DATABASE_HOST"] } else { "127.0.0.1" }
$dbPort = if ($config["DATABASE_PORT"]) { $config["DATABASE_PORT"] } else { "5432" }

Write-Host "Creating role '$($config.DATABASE_USER)' and database '$($config.DATABASE_NAME)' on ${dbHost}:${dbPort}"
Write-Host "You will be asked for the password of PostgreSQL user '$SuperUser'."

& $psql -U $SuperUser -h $dbHost -p $dbPort -d postgres `
    -v ON_ERROR_STOP=1 `
    -v "db_name=$($config.DATABASE_NAME)" `
    -v "db_user=$($config.DATABASE_USER)" `
    -v "db_password=$($config.DATABASE_PASSWORD)" `
    -f (Join-Path $PSScriptRoot "setup_database.sql")

if ($LASTEXITCODE -ne 0) { throw "psql failed with exit code $LASTEXITCODE" }
