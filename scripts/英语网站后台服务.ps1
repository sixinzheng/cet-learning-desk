param(
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [string]$PythonPrefix = '',
    [Parameter(Mandatory = $true)][string]$ProjectRoot,
    [Parameter(Mandatory = $true)][string]$LogPath
)

$ErrorActionPreference = 'Continue'
Set-Location -LiteralPath $ProjectRoot
"[$(Get-Date -Format o)] starting Flask service with $PythonPath $PythonPrefix" | Add-Content -LiteralPath $LogPath -Encoding utf8
if ($PythonPrefix) {
    & $PythonPath $PythonPrefix run_server.py 2>&1 | Out-File -LiteralPath $LogPath -Append -Encoding utf8
} else {
    & $PythonPath run_server.py 2>&1 | Out-File -LiteralPath $LogPath -Append -Encoding utf8
}
"[$(Get-Date -Format o)] service process exited with code $LASTEXITCODE" | Add-Content -LiteralPath $LogPath -Encoding utf8
