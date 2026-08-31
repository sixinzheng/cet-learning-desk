param(
    [string]$UnsignedApkPath = "",
    [string]$SignedApkPath = ""
)

$ErrorActionPreference = "Stop"
$androidRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sdkRoot = Join-Path $env:LOCALAPPDATA "Android\Sdk"
$buildTools = Join-Path $sdkRoot "build-tools\36.0.0"
$apksigner = Join-Path $buildTools "apksigner.bat"
$zipalign = Join-Path $buildTools "zipalign.exe"
$keytool = "C:\Program Files\Java\latest\jdk-21\bin\keytool.exe"
$unsignedApk = if ($UnsignedApkPath) {
    [IO.Path]::GetFullPath($UnsignedApkPath)
} else {
    Join-Path $androidRoot "app\build\outputs\apk\release\app-release-unsigned.apk"
}
$versionSource = Get-Content -LiteralPath (Join-Path (Split-Path -Parent $androidRoot) "app_version.py") -Raw -Encoding UTF8
if ($versionSource -notmatch 'APP_VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"') {
    throw "Unable to read APP_VERSION from app_version.py"
}
$appVersion = $Matches[1]
$signedApk = if ($SignedApkPath) {
    [IO.Path]::GetFullPath($SignedApkPath)
} else {
    Join-Path $androidRoot "app\build\outputs\apk\release\CET-Learning-Desk-Android-arm64-v$appVersion.apk"
}
$signingRoot = Join-Path $env:LOCALAPPDATA "CETLearningDesk\signing"
$keyStore = Join-Path $signingRoot "android-release.jks"
$secretFile = Join-Path $signingRoot "android-signing-secret.clixml"
$alias = "cet-learning-desk"

foreach ($required in @($apksigner, $zipalign, $keytool, $unsignedApk)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Missing Android signing dependency: $required"
    }
}

New-Item -ItemType Directory -Path $signingRoot -Force | Out-Null

if (-not (Test-Path -LiteralPath $keyStore)) {
    if (Test-Path -LiteralPath $secretFile) {
        throw "Signing password exists but the keystore is missing. Refusing to create a second key."
    }
    $bytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    } finally {
        $generator.Dispose()
    }
    $password = [Convert]::ToBase64String($bytes).Replace('+', 'A').Replace('/', 'B').TrimEnd('=')
    ConvertTo-SecureString $password -AsPlainText -Force | Export-Clixml -LiteralPath $secretFile
    $keyArguments = @(
        '-genkeypair', '-v', '-keystore', $keyStore, '-storetype', 'PKCS12',
        '-storepass', $password, '-keypass', $password, '-alias', $alias,
        '-keyalg', 'RSA', '-keysize', '4096', '-validity', '10000',
        '-dname', 'CN=CET Learning Desk, OU=Learning, O=CET Learning Desk, L=Beijing, ST=Beijing, C=CN'
    )
    & $keytool $keyArguments
    if ($LASTEXITCODE -ne 0) { throw "Failed to generate the Android release key." }
} else {
    if (-not (Test-Path -LiteralPath $secretFile)) {
        throw "The Android release key exists but its encrypted password file is missing."
    }
    $secure = Import-Clixml -LiteralPath $secretFile
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

try {
    $env:CET_ANDROID_SIGNING_PASSWORD = $password
    & $zipalign -c -P 16 -v 4 $unsignedApk
    if ($LASTEXITCODE -ne 0) { throw "APK zipalign verification failed." }
    $signArguments = @(
        'sign', '--ks', $keyStore, '--ks-key-alias', $alias,
        '--ks-pass', 'env:CET_ANDROID_SIGNING_PASSWORD',
        '--key-pass', 'env:CET_ANDROID_SIGNING_PASSWORD',
        '--out', $signedApk, $unsignedApk
    )
    & $apksigner $signArguments
    if ($LASTEXITCODE -ne 0) { throw "APK signing failed." }
    & $apksigner verify --verbose --print-certs $signedApk
    if ($LASTEXITCODE -ne 0) { throw "APK signature verification failed." }
} finally {
    Remove-Item Env:CET_ANDROID_SIGNING_PASSWORD -ErrorAction SilentlyContinue
    $password = $null
}

Write-Host "Signed APK: $signedApk"
Write-Host "Signing key (do not distribute): $keyStore"
