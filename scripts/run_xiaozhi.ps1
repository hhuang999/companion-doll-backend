$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot 'vendor/xiaozhi-venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    throw 'Run scripts/setup_xiaozhi.ps1 first.'
}
& $Python (Join-Path $PSScriptRoot 'run_xiaozhi.py') @args
exit $LASTEXITCODE
