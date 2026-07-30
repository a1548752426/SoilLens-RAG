param(
    [int]$Port = 8010
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $env:SOILLENS_DISABLE_SEMANTIC) {
    $env:SOILLENS_DISABLE_SEMANTIC = "1"
}

& (Join-Path $ProjectRoot "run.ps1") -Port $Port -Profile demo
