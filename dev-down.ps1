# Stops the backend/frontend dev processes started by dev-up.ps1 and brings down docker services.
# Run from the repo root: .\dev-down.ps1

$root = $PSScriptRoot
$pidFile = "$root\.dev-pids"

if (Test-Path $pidFile) {
    $ids = (Get-Content $pidFile) -split ","
    foreach ($procId in $ids) {
        # taskkill /T kills the whole process tree — Stop-Process only kills the
        # parent, leaving uvicorn --reload / next dev's child watchers alive and
        # still holding the port.
        taskkill /F /T /PID $procId 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Stopped process tree $procId"
        } else {
            Write-Host "Process $procId already gone"
        }
    }
    Remove-Item $pidFile
} else {
    Write-Host "No .dev-pids file found — backend/frontend may not be running via dev-up.ps1"
}

Write-Host "==> Stopping docker services..." -ForegroundColor Cyan
docker compose -f "$root\docker-compose.yml" down
