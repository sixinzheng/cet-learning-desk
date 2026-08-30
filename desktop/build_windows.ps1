param(
    [string]$Python = "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)

$ErrorActionPreference = "Stop"
$desktopRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$cargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
$env:PATH = "$cargoBin;$env:PATH"

if (-not $env:TAURI_SIGNING_PRIVATE_KEY_PATH) {
    $localUpdaterKey = Join-Path $env:LOCALAPPDATA "CETLearningDesk\signing\tauri-updater.key"
    if (Test-Path -LiteralPath $localUpdaterKey) {
        $env:TAURI_SIGNING_PRIVATE_KEY_PATH = $localUpdaterKey
    }
}

& (Join-Path $desktopRoot "build_backend.ps1") -Python $Python
if ($LASTEXITCODE -ne 0) { throw "Desktop backend build failed" }
& $Python (Join-Path $desktopRoot "create_icon.py")
if ($LASTEXITCODE -ne 0) { throw "Desktop icon build failed" }

Push-Location $desktopRoot
try {
    npm install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "Failed to install Tauri dependencies" }
    node (Join-Path $desktopRoot "run_tauri_build.mjs")
    if ($LASTEXITCODE -ne 0) { throw "Windows installer build failed" }
} finally {
    Pop-Location
}

Write-Host "Installer output: $(Join-Path $desktopRoot 'src-tauri\target\release\bundle\nsis')"
