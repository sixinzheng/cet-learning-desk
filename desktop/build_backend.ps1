param(
    [string]$Python = "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)

$ErrorActionPreference = "Stop"
$desktopRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $desktopRoot
$buildDeps = Join-Path $desktopRoot ".python-build-deps"
$binaryDir = Join-Path $desktopRoot "src-tauri\binaries"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python runtime not found: $Python"
}

New-Item -ItemType Directory -Force -Path $buildDeps,$binaryDir | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $buildDeps "PyInstaller")) -or
    -not (Test-Path -LiteralPath (Join-Path $buildDeps "waitress"))) {
    & $Python -m pip install --disable-pip-version-check --target $buildDeps "pyinstaller>=6.11,<7" "waitress>=3.0,<4"
    if ($LASTEXITCODE -ne 0) { throw "Failed to install desktop build dependencies" }
}

$env:PYTHONPATH = "$projectRoot;$buildDeps;$(Join-Path $projectRoot '.runtime_deps');$(Join-Path $projectRoot '.deps')"
$privateSource = Join-Path $projectRoot "data\vocab.db"
$distributionSource = Join-Path $projectRoot "resources\distribution\vocab.seed.db"
$seedSource = if (Test-Path -LiteralPath $privateSource) { $privateSource } else { $distributionSource }
if (-not (Test-Path -LiteralPath $seedSource)) {
    throw "No database source is available for the distribution seed"
}
& $Python (Join-Path $projectRoot "scripts\build_distribution_seed.py") --source $seedSource --output $distributionSource
if ($LASTEXITCODE -ne 0) { throw "Failed to build distribution seed database" }

$distDir = Join-Path $desktopRoot "pyinstaller-dist"
$workDir = Join-Path $desktopRoot "pyinstaller-build"
& $Python -m PyInstaller --noconfirm --clean --distpath $distDir --workpath $workDir (Join-Path $desktopRoot "cet_backend.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

$source = Join-Path $distDir "cet-backend-x86_64-pc-windows-msvc.exe"
$target = Join-Path $binaryDir "cet-backend-x86_64-pc-windows-msvc.exe"
Copy-Item -LiteralPath $source -Destination $target -Force
Write-Host "Desktop backend created: $target"
