param(
    [switch]$NoBrowser
)

# 四六级智能单词助手 · 本地网站一键启动
# 用法：双击桌面「网站快捷启动」里的快捷方式，或直接运行本脚本。
# 可选 -NoBrowser：只启动服务，不自动打开浏览器。

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = "C:\Users\Lenovo\AppData\Local\Programs\Python\Python314\python.exe"
$configPath = Join-Path $projectRoot "data\config.json"
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
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "未找到 Python 3.14，请检查安装路径：`n$pythonPath",
        "英语学习网站启动失败"
    ) | Out-Null
    exit 1
}

if (-not (Test-EnglishSite)) {
    # 服务未在运行：隐藏窗口启动单进程服务（不启用 Flask 调试重载器）
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $pythonPath
    $startInfo.Arguments = "run_server.py"
    $startInfo.WorkingDirectory = $projectRoot
    $startInfo.UseShellExecute = $true
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    [void][System.Diagnostics.Process]::Start($startInfo)

    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 250
        if (Test-EnglishSite) {
            $ready = $true
            break
        }
    }

    if (-not $ready) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show(
            "英语学习网站服务未能启动，请重试或查看日志。",
            "英语学习网站启动失败"
        ) | Out-Null
        exit 1
    }
}

if (-not $NoBrowser) {
    Start-Process -FilePath 'C:\Program Files\Mozilla Firefox\firefox.exe' -ArgumentList $siteUrl
}
