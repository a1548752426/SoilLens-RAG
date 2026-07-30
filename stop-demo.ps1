param(
    [int]$Port = 8010
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $ProjectRoot "tmp\demo-server.pid"
$HealthUrl = "http://127.0.0.1:$Port/api/health"

try {
    $Health = $null
    try {
        $Health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2
    } catch {
        $Health = $null
    }

    if (-not (Test-Path -LiteralPath $PidFile)) {
        if ($Health) {
            throw "The demo is running, but its process record is missing. Send this message to Codex."
        }
        Write-Host "SoilLens public demo is not running."
        exit 0
    }

    $ProcessId = [int](Get-Content -LiteralPath $PidFile -Raw -Encoding ASCII)
    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($Process) {
        Stop-Process -Id $ProcessId -Force
        $Process | Wait-Process -Timeout 10 -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Write-Host "SoilLens public demo has stopped."
    exit 0
} catch {
    Write-Host "STOP FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

