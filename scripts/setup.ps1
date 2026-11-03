param([string]$Python)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$uv = (Get-Command uv -ErrorAction Stop).Source
Push-Location $projectRoot
try {
    $taskTemp = Join-Path $projectRoot 'artifacts/tmp'
    New-Item -ItemType Directory -Force -Path $taskTemp | Out-Null
    $env:TEMP = $taskTemp
    $env:TMP = $taskTemp
    $env:UV_CACHE_DIR = Join-Path $projectRoot 'artifacts/uv-cache'
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        if (-not $Python) {
            $localRuntime = Get-ChildItem -Path '.python/cpython-3.10*-windows-x86_64-none/python.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
            $Python = if ($localRuntime) { $localRuntime.FullName } else { '3.10' }
        }
        & $uv venv --python $Python .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
    }
    & $uv pip install --link-mode copy --python .venv/Scripts/python.exe -r companion/requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'Locked dependency installation failed.' }
    & $uv pip install --link-mode copy --python .venv/Scripts/python.exe --no-deps -e companion
    if ($LASTEXITCODE -ne 0) { throw 'Companion installation failed.' }
    & .venv/Scripts/python.exe -c 'import sys; from companion.core.config import Config; print(sys.executable); print(sys.version); print(Config().settings.runtime.mode)'
} finally {
    Pop-Location
}
