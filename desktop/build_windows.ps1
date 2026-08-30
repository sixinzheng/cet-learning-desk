param(
    [string]$Python = "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)

$ErrorActionPreference = "Stop"
$desktopRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$cargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
$env:PATH = "$cargoBin;$env:PATH"

& (Join-Path $desktopRoot "build_backend.ps1") -Python $Python
if ($LASTEXITCODE -ne 0) { throw "Desktop backend build failed" }
& $Python (Join-Path $desktopRoot "create_icon.py")
if ($LASTEXITCODE -ne 0) { throw "Desktop icon build failed" }

Push-Location $desktopRoot
try {
    npm install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "Failed to install Tauri dependencies" }
    npm run desktop:build
    if ($LASTEXITCODE -ne 0) { throw "Windows installer build failed" }
} finally {
    Pop-Location
}

Write-Host "Installer output: $(Join-Path $desktopRoot 'src-tauri\target\release\bundle\nsis')"
