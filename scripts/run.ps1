param(
    [ValidateSet('fake', 'live', 'dashboard', 'test', 'audio')]
    [string]$Mode = 'fake',
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Run scripts/setup.ps1 first.'
}
Push-Location $projectRoot
try {
    switch ($Mode) {
        'fake' { & $pythonPath -m companion.adapters.cli --fake @ExtraArgs }
        'live' { & $pythonPath -m companion.adapters.cli --env-file .env @ExtraArgs }
        'dashboard' { & $pythonPath -m companion.dashboard.launch @ExtraArgs }
        'test' { & $pythonPath scripts/check.py @ExtraArgs }
        'audio' { & $pythonPath -m companion.tools.prepare_audio --env-file .env @ExtraArgs }
    }
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}
