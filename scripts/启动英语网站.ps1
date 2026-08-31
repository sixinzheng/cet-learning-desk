param(
    [switch]$NoBrowser,
    [switch]$NoDialogs
)

# 四六级智能单词助手 · 本地网站一键启动
# 用法：双击桌面「网站快捷启动」里的快捷方式，或直接运行本脚本。
# 可选 -NoBrowser：只启动服务，不自动打开浏览器。

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $projectRoot "data\config.json"
$serviceScript = Join-Path $PSScriptRoot "英语网站后台服务.ps1"
$localAppData = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $env:USERPROFILE 'AppData\Local' }
$logDirectory = Join-Path $localAppData 'CETLearningDesk\logs'
$logPath = Join-Path $logDirectory 'source-launch.log'
[void](New-Item -ItemType Directory -Path $logDirectory -Force)
# 后台服务运行时会持续持有主日志。二次双击应直接打开页面，
# 不能因为一次非关键的“启动器被调用”日志写入失败而中断。
try {
    "[$(Get-Date -Format o)] source launcher invoked" | Add-Content -LiteralPath $logPath -Encoding utf8 -ErrorAction Stop
} catch { }
$port = 5400
if (Test-Path -LiteralPath $configPath) {
    try {
        $port = (Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json).port
    } catch {
        $port = 5400
    }
}
$siteUrl = "http://127.0.0.1:$port/"

function Test-EnglishSite {
    try {
        $response = Invoke-WebRequest -UseBasicParsing $siteUrl -TimeoutSec 2
        return $response.StatusCode -eq 200 -and $response.Content -match '四六级学习台'
    }
    catch {
        return $false
    }
}

function Show-LaunchError([string]$message) {
    "[$(Get-Date -Format o)] launcher error: $message" | Add-Content -LiteralPath $logPath -Encoding utf8
    if ($NoDialogs) { throw $message }
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "$message`n`n启动日志：`n$logPath",
        "英语学习网站启动失败"
    ) | Out-Null
}

function Test-PythonCandidate($candidate) {
    try {
        $pythonCode = "import flask, requests; print('CET_RUNTIME_OK')"
        $prefix = if ($candidate.Prefix) { "$($candidate.Prefix) " } else { '' }
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $candidate.Path
        $startInfo.Arguments = "$prefix-c `"$pythonCode`""
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $startInfo
        [void]$process.Start()
        if (-not $process.WaitForExit(10000)) {
            $process.Kill()
            return $false
        }
        $output = $process.StandardOutput.ReadToEnd()
        $errorOutput = $process.StandardError.ReadToEnd()
        if ($process.ExitCode -ne 0) {
            "[$(Get-Date -Format o)] runtime probe failed: $errorOutput" | Add-Content -LiteralPath $logPath -Encoding utf8
        }
        return $process.ExitCode -eq 0 -and $output -match 'CET_RUNTIME_OK'
    } catch {
        "[$(Get-Date -Format o)] runtime probe exception: $($_.Exception.Message)" | Add-Content -LiteralPath $logPath -Encoding utf8
        return $false
    }
}

function Find-PythonRuntime {
    $candidates = @(
        [pscustomobject]@{Path=(Join-Path $projectRoot '.venv\Scripts\python.exe'); Prefix=''},
        [pscustomobject]@{Path=(Join-Path $projectRoot '.test-venv\Scripts\python.exe'); Prefix=''}
    )
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) { $candidates += [pscustomobject]@{Path=$py.Source; Prefix='-3'} }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) { $candidates += [pscustomobject]@{Path=$python.Source; Prefix=''} }
    $knownInstallRoot = Join-Path $localAppData 'Programs\Python'
    if (Test-Path -LiteralPath $knownInstallRoot) {
        Get-ChildItem -LiteralPath $knownInstallRoot -Directory -Filter 'Python3*' -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object {
                $candidates += [pscustomobject]@{Path=(Join-Path $_.FullName 'python.exe'); Prefix=''}
            }
    }
    foreach ($candidate in $candidates) {
        $exists = Test-Path -LiteralPath $candidate.Path
        $valid = $false
        if ($exists) { $valid = [bool](Test-PythonCandidate $candidate) }
        "[$(Get-Date -Format o)] runtime candidate path=$($candidate.Path) prefix=$($candidate.Prefix) exists=$exists valid=$valid" |
            Add-Content -LiteralPath $logPath -Encoding utf8
        if ($exists -and $valid) {
            return $candidate
        }
    }
    return $null
}

function Get-PortOwner {
    try {
        return Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop | Select-Object -First 1
    } catch { return $null }
}

if (-not (Test-EnglishSite)) {
    $owner = Get-PortOwner
    if ($owner) {
        $processName = try { (Get-Process -Id $owner.OwningProcess -ErrorAction Stop).ProcessName } catch { '未知进程' }
        Show-LaunchError "端口 $port 已被其他程序占用（PID $($owner.OwningProcess)，$processName），但它不是当前学习网站。请关闭该程序后重试。"
        exit 1
    }
    $runtime = Find-PythonRuntime
    if (-not $runtime) {
        Show-LaunchError '没有找到可用的 Python 运行环境，或环境缺少 Flask/requests。请重新安装学习台，或在项目虚拟环境中安装 requirements.txt。'
        exit 1
    }
    "[$(Get-Date -Format o)] launcher selected $($runtime.Path) $($runtime.Prefix)" | Add-Content -LiteralPath $logPath -Encoding utf8
    $backgroundArgs = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $serviceScript,
        '-PythonPath', $runtime.Path, '-ProjectRoot', $projectRoot, '-LogPath', $logPath
    )
    if ($runtime.Prefix) { $backgroundArgs += @('-PythonPrefix', $runtime.Prefix) }
    Start-Process -FilePath 'powershell.exe' -ArgumentList $backgroundArgs -WorkingDirectory $projectRoot -WindowStyle Hidden

    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 250
        if (Test-EnglishSite) {
            $ready = $true
            break
        }
    }

    if (-not $ready) {
        $tail = if (Test-Path -LiteralPath $logPath) { (Get-Content -LiteralPath $logPath -Tail 12) -join "`n" } else { '没有生成日志。' }
        Show-LaunchError "英语学习网站服务未能在 15 秒内启动。`n`n最近日志：`n$tail"
        exit 1
    }
}

if (-not $NoBrowser) {
    Start-Process $siteUrl
}
