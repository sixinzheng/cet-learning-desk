$ErrorActionPreference = "Stop"
$androidRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sdkRoot = Join-Path $env:LOCALAPPDATA "Android\Sdk"
$buildTools = Join-Path $sdkRoot "build-tools\36.0.0"
$apksigner = Join-Path $buildTools "apksigner.bat"
$zipalign = Join-Path $buildTools "zipalign.exe"
$keytool = "C:\Program Files\Java\latest\jdk-21\bin\keytool.exe"
$unsignedApk = Join-Path $androidRoot "app\build\outputs\apk\release\app-release-unsigned.apk"
$signedApk = Join-Path $androidRoot "app\build\outputs\apk\release\四六级学习台-Android-arm64-v0.2.0.apk"
$signingRoot = Join-Path $env:LOCALAPPDATA "CETLearningDesk\signing"
$keyStore = Join-Path $signingRoot "android-release.jks"
$secretFile = Join-Path $signingRoot "android-signing-secret.clixml"
$alias = "cet-learning-desk"

foreach ($required in @($apksigner, $zipalign, $keytool, $unsignedApk)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "缺少 Android 签名依赖：$required"
    }
}

New-Item -ItemType Directory -Path $signingRoot -Force | Out-Null

if (-not (Test-Path -LiteralPath $keyStore)) {
    if (Test-Path -LiteralPath $secretFile) {
        throw "发现签名密码但缺少密钥库；为避免生成无法持续更新的第二套密钥，构建已停止。"
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
    if ($LASTEXITCODE -ne 0) { throw "生成 Android 发布密钥失败" }
} else {
    if (-not (Test-Path -LiteralPath $secretFile)) {
        throw "Android 发布密钥存在，但当前 Windows 用户的加密密码文件缺失。"
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
    if ($LASTEXITCODE -ne 0) { throw "APK zipalign 校验失败" }
    $signArguments = @(
        'sign', '--ks', $keyStore, '--ks-key-alias', $alias,
        '--ks-pass', 'env:CET_ANDROID_SIGNING_PASSWORD',
        '--key-pass', 'env:CET_ANDROID_SIGNING_PASSWORD',
        '--out', $signedApk, $unsignedApk
    )
    & $apksigner $signArguments
    if ($LASTEXITCODE -ne 0) { throw "APK 签名失败" }
    & $apksigner verify --verbose --print-certs $signedApk
    if ($LASTEXITCODE -ne 0) { throw "APK 签名验证失败" }
} finally {
    Remove-Item Env:CET_ANDROID_SIGNING_PASSWORD -ErrorAction SilentlyContinue
    $password = $null
}

Write-Host "Signed APK: $signedApk"
Write-Host "Signing key (do not distribute): $keyStore"
