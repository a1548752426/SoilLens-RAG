param(
    [int]$Port = 8000,
    [ValidateSet("private", "demo")]
    [string]$Profile = "private"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

Set-Location $ProjectRoot
$env:SOILLENS_PROFILE = $Profile

if (-not (Test-Path -LiteralPath $VenvPython)) {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCommand) {
        $PythonCommand = Get-Command py -ErrorAction SilentlyContinue
    }
    if (-not $PythonCommand) {
        throw "Python 3 was not found. Install Python 3.10 or newer."
    }

    Write-Host "First run: creating the local Python environment..."
    if ($PythonCommand.Name -eq "py.exe") {
        & $PythonCommand.Source -3 -m venv $VenvDir
    } else {
        & $PythonCommand.Source -m venv $VenvDir
    }
    & $VenvPython -m pip install --upgrade pip
}

& $VenvPython -m pip install --disable-pip-version-check --quiet -r (Join-Path $ProjectRoot "requirements.txt")

Write-Host ""
Write-Host "SoilLens is starting at http://127.0.0.1:$Port"
if ($Profile -eq "demo") {
    Write-Host "Mode: public-safe demo data (synthetic samples and original demo documents)."
} else {
    Write-Host "Mode: local private data (real samples remain local-only)."
}
Write-Host "Press Ctrl+C to stop the server."
Write-Host ""

& $VenvPython -m uvicorn app.main:app --host 127.0.0.1 --port $Port
