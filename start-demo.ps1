param(
    [int]$Port = 8010
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$TempRoot = Join-Path $ProjectRoot "tmp"
$PidFile = Join-Path $TempRoot "demo-server.pid"
$StdoutLog = Join-Path $TempRoot "demo-server.stdout.log"
$StderrLog = Join-Path $TempRoot "demo-server.stderr.log"
$HealthUrl = "http://127.0.0.1:$Port/api/health"
$AppUrl = "http://127.0.0.1:$Port"

function Get-DemoHealth {
    try {
        return Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2
    } catch {
        return $null
    }
}

try {
    New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null

    $ExistingHealth = Get-DemoHealth
    if ($ExistingHealth) {
        if ($ExistingHealth.profile -ne "demo") {
            throw "Port $Port is already used by another SoilLens mode."
        }
        $ExistingOwner = Get-NetTCPConnection `
            -LocalPort $Port `
            -State Listen `
            -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($ExistingOwner) {
            Set-Content `
                -LiteralPath $PidFile `
                -Value $ExistingOwner.OwningProcess `
                -Encoding ASCII
        }
        Write-Host "SoilLens public demo is already running."
        Write-Host "Opening $AppUrl"
        Start-Process $AppUrl
        exit 0
    }

    $PortOwner = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($PortOwner) {
        throw "Port $Port is already occupied by process $($PortOwner.OwningProcess)."
    }

    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $StdoutLog -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $StderrLog -Force -ErrorAction SilentlyContinue

    Write-Host "Starting SoilLens public demo..."
    Write-Host "The first start can take about one minute."

    $PowerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
    $RunScript = Join-Path $ProjectRoot "run-demo.ps1"
    $Arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $RunScript,
        "-Port", [string]$Port
    )
    $ServerProcess = Start-Process `
        -FilePath $PowerShell `
        -ArgumentList $Arguments `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $StdoutLog `
        -RedirectStandardError $StderrLog `
        -PassThru
    Set-Content -LiteralPath $PidFile -Value $ServerProcess.Id -Encoding ASCII

    $Health = $null
    for ($Attempt = 1; $Attempt -le 120; $Attempt++) {
        Start-Sleep -Milliseconds 500
        $Health = Get-DemoHealth
        if ($Health) {
            break
        }
        if ($ServerProcess.HasExited) {
            break
        }
        if ($Attempt % 10 -eq 0) {
            Write-Host "Still starting... $([math]::Round($Attempt / 2)) seconds"
        }
    }

    if (-not $Health) {
        if (-not $ServerProcess.HasExited) {
            Stop-Process -Id $ServerProcess.Id -Force -ErrorAction SilentlyContinue
        }
        $ErrorTail = ""
        if (Test-Path -LiteralPath $StderrLog) {
            $ErrorTail = (
                Get-Content -LiteralPath $StderrLog -Tail 30 -Encoding UTF8
            ) -join [Environment]::NewLine
        }
        throw "SoilLens did not start. Error log:`n$ErrorTail"
    }
    if ($Health.profile -ne "demo" -or $Health.status -ne "ok") {
        throw "Health check returned an unexpected mode or status."
    }
    $ListeningProcess = Get-NetTCPConnection `
        -LocalPort $Port `
        -State Listen `
        -ErrorAction Stop |
        Select-Object -First 1
    Set-Content `
        -LiteralPath $PidFile `
        -Value $ListeningProcess.OwningProcess `
        -Encoding ASCII

    Write-Host ""
    Write-Host "SoilLens public demo is ready."
    Write-Host "Opening $AppUrl"
    Write-Host "To stop it later, double-click Stop public demo."
    Start-Process $AppUrl
    exit 0
} catch {
    Write-Host ""
    Write-Host "START FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Log file: $StderrLog"
    exit 1
}
