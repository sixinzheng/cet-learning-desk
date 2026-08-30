param(
    [string]$Python = "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)

$ErrorActionPreference = "Stop"
$androidRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $androidRoot
$sdkRoot = Join-Path $env:LOCALAPPDATA "Android\Sdk"
$toolsRoot = Join-Path $androidRoot ".tools"
$gradleVersion = "8.10.2"
$gradleRoot = Join-Path $toolsRoot "gradle-$gradleVersion"
$gradleBat = Join-Path $gradleRoot "bin\gradle.bat"
$gradleZip = Join-Path $toolsRoot "gradle-$gradleVersion-bin.zip"
$gradleUrl = "https://services.gradle.org/distributions/gradle-$gradleVersion-bin.zip"
$gradleSha256 = "31C55713E40233A8303827CEB42CA48A47267A0AD4BAB9177123121E71524C26"

if (-not (Test-Path -LiteralPath $sdkRoot)) {
    throw "Android SDK 不存在：$sdkRoot"
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "构建 Python 不存在：$Python"
}

& $Python (Join-Path $androidRoot "prepare_android.py")
if ($LASTEXITCODE -ne 0) { throw "Android 资源准备失败" }

if (-not (Test-Path -LiteralPath $gradleBat)) {
    New-Item -ItemType Directory -Path $toolsRoot -Force | Out-Null
    if (-not (Test-Path -LiteralPath $gradleZip)) {
        Invoke-WebRequest -Uri $gradleUrl -OutFile $gradleZip -UseBasicParsing
    }
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $gradleZip).Hash
    if ($actualHash -ne $gradleSha256) {
        throw "Gradle 下载校验失败。期望 $gradleSha256，实际 $actualHash"
    }
    Expand-Archive -LiteralPath $gradleZip -DestinationPath $toolsRoot -Force
}

$env:ANDROID_HOME = $sdkRoot
$env:ANDROID_SDK_ROOT = $sdkRoot
$env:PYTHONUTF8 = "1"

Push-Location $androidRoot
try {
    & $gradleBat --no-daemon :app:assembleRelease
    if ($LASTEXITCODE -ne 0) { throw "Android APK 构建失败" }
} finally {
    Pop-Location
}

$apk = Join-Path $androidRoot "app\build\outputs\apk\release\app-release-unsigned.apk"
if (-not (Test-Path -LiteralPath $apk)) {
    throw "未找到生成的 APK：$apk"
}
Write-Host "Unsigned APK: $apk"
