# Starts Tiro locally: API and web in their own windows, then opens the browser.
#   ./start.ps1          free local models through Ollama (.env + .env.ollama)
#   ./start.ps1 -OpenAI  hosted model from .env only
#   ./start.ps1 -ApiPort 8100 -WebPort 3100   preferred ports; busy ones move to the next free port
# Close the two windows (or Ctrl+C in them) to stop.
param([switch]$OpenAI, [int]$ApiPort = 8000, [int]$WebPort = 3000)

$root = $PSScriptRoot
$envFiles = "--env-file ../../.env"
if (-not $OpenAI) { $envFiles += " --env-file ../../.env.ollama" }

# Another local project may hold the default port; take the next free one.
function Get-FreePort($port) {
    while (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { $port++ }
    return $port
}
$ApiPort = Get-FreePort $ApiPort
$WebPort = Get-FreePort $WebPort

# Ingest skips unchanged spec chunks, so repeating it on every start is cheap.
Start-Process powershell -WorkingDirectory "$root\apps\api" -ArgumentList "-NoExit", "-Command", (
    "uv sync --locked; " +
    "uv run $envFiles python -m app.rag.ingest ../../data/demo/harbor-desk/spec.md; " +
    "uv run $envFiles uvicorn app.main:app --reload --port $ApiPort"
)
Start-Process powershell -WorkingDirectory "$root\apps\web" -ArgumentList "-NoExit", "-Command", (
    "if (-not (Test-Path node_modules)) { npm ci }; " +
    "`$env:API_URL = 'http://127.0.0.1:$ApiPort'; npm run dev -- -p $WebPort"
)

function Wait-Url($url) {
    for ($i = 0; $i -lt 120; $i++) {
        try { Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 2 | Out-Null; return $true }
        catch { Start-Sleep -Seconds 2 }
    }
    return $false
}

Write-Host "Starting Tiro: API on :$ApiPort, web on :$WebPort ..."
if ((Wait-Url "http://127.0.0.1:$ApiPort/ready") -and (Wait-Url "http://localhost:$WebPort")) {
    Write-Host "Ready."
    Start-Process "http://localhost:$WebPort"
} else {
    Write-Host "Not ready after 4 minutes; check the API and web windows for errors."
}
