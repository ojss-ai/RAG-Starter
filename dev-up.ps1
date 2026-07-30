# Brings up the full RagStarter dev stack: docker backing services, DB migrations,
# backend API (uvicorn --reload), and frontend (next dev).
# Run from the repo root: .\dev-up.ps1
# Stop everything with .\dev-down.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "==> Loading $root\.env into the process environment..." -ForegroundColor Cyan
# app/config.py resolves its env_file relative to cwd, which is backend/ when we
# invoke alembic/uvicorn from there — so it never sees the root .env on its own.
# Real environment variables always win over env_file in pydantic-settings, so
# exporting them here (inherited by the child processes below) fixes that without
# touching application code.
Get-Content "$root\.env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $k, $v = $line -split "=", 2
        [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), "Process")
    }
}

Write-Host "==> Starting docker services (postgres, etcd, minio, milvus, attu)..." -ForegroundColor Cyan
docker compose -f "$root\docker-compose.yml" up -d postgres etcd minio milvus attu
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

Write-Host "==> Waiting for postgres to be healthy..." -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds(60)
do {
    $status = docker inspect -f "{{.State.Health.Status}}" ragstarter-postgres-1 2>$null
    if ($status -eq "healthy") { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)
if ($status -ne "healthy") { throw "postgres did not become healthy in time" }

Write-Host "==> Running Alembic migrations..." -ForegroundColor Cyan
Push-Location "$root\backend"
& ".venv\Scripts\python.exe" -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "alembic upgrade failed" }
Pop-Location

Write-Host "==> Starting backend (http://localhost:8000)..." -ForegroundColor Cyan
$backend = Start-Process -PassThru -WindowStyle Normal -FilePath ".venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000" `
    -WorkingDirectory "$root\backend"

Write-Host "==> Starting frontend (http://localhost:3000)..." -ForegroundColor Cyan
$frontend = Start-Process -PassThru -WindowStyle Normal -FilePath "npm.cmd" `
    -ArgumentList "run", "dev" `
    -WorkingDirectory "$root\frontend"

"$($backend.Id),$($frontend.Id)" | Set-Content "$root\.dev-pids"

Write-Host ""
Write-Host "All up:" -ForegroundColor Green
Write-Host "  Frontend:      http://localhost:3000"
Write-Host "  Backend:       http://localhost:8000"
Write-Host "  MinIO console: http://localhost:9001"
Write-Host "  Attu (Milvus): http://localhost:3001"
Write-Host "  Postgres:      localhost:5433"
Write-Host ""
Write-Host "Backend/frontend are running in separate windows (PIDs saved to .dev-pids)."
Write-Host "Run .\dev-down.ps1 to stop everything."
