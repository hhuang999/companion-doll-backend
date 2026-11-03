param([string]$Python = '')
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $ProjectRoot
try {
    if (-not $Python) { $Python = Join-Path $ProjectRoot '.venv/Scripts/python.exe' }
    $env:TEMP = Join-Path $ProjectRoot 'artifacts/tmp'
    $env:TMP = $env:TEMP
    $env:UV_CACHE_DIR = Join-Path $ProjectRoot 'artifacts/uv-cache'
    New-Item -ItemType Directory -Force $env:TEMP | Out-Null
    $Upstream = Join-Path $ProjectRoot 'vendor/xiaozhi-esp32-server'
    if (-not (Test-Path -LiteralPath $Upstream)) {
        git clone --filter=blob:none --no-checkout https://github.com/xinnan-tech/xiaozhi-esp32-server.git $Upstream
        if ($LASTEXITCODE) { throw 'Clone failed' }
        git -C $Upstream checkout -b codex/companion-integration 92337881a7b6553614b47e137a774d02bf40512f
        if ($LASTEXITCODE) { throw 'Checkout failed' }
    }
    & $Python xiaozhi_patch/apply.py $Upstream --apply
    if ($LASTEXITCODE) { throw 'Patch validation failed' }
    $ServerPython = Join-Path $ProjectRoot 'vendor/xiaozhi-venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $ServerPython)) {
        uv venv --python $Python vendor/xiaozhi-venv
        if ($LASTEXITCODE) { throw 'Environment creation failed' }
    }
    uv pip install --python $ServerPython --link-mode copy -r xiaozhi_patch/requirements.lock
    if ($LASTEXITCODE) { throw 'Dependency installation failed' }
    uv pip install --python $ServerPython --link-mode copy --no-deps -e './companion[test]'
    if ($LASTEXITCODE) { throw 'Companion installation failed' }
    & $ServerPython xiaozhi_patch/configure.py --download-model
    if ($LASTEXITCODE) { throw 'Configuration failed' }
    & $ServerPython -m companion.tools.upgrade_config data/xiaozhi-config
    if ($LASTEXITCODE) { throw 'Companion configuration upgrade failed' }
    & $ServerPython -m companion.tools.prepare_audio --env-file .env --config-dir data/xiaozhi-config --bind-config
    if ($LASTEXITCODE) { throw 'Fixed audio preparation failed' }
    & $ServerPython -m companion.tools.provision_device --device-id course-simulator --user-key synthetic-course-simulator --output data/device-client.json
    if ($LASTEXITCODE) { throw 'Local simulator credential preparation failed' }
    Write-Host 'Ready. Start with ./scripts/run_xiaozhi.ps1'
} finally { Pop-Location }
