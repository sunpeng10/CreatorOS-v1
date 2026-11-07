param([switch]$Browser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:PYTHONUTF8 = '1'
$env:CREATOROS_TESTING = '1'
& .\.venv\Scripts\python.exe -m pytest services/api/tests -q
if ($LASTEXITCODE -ne 0) { throw 'pytest 失败' }
Push-Location -LiteralPath 'apps\web'
try {
    $checks = @('test', 'lint', 'typecheck')
    if (-not $Browser) { $checks += 'build' }
    foreach ($check in $checks) {
        & npm.cmd run $check
        if ($LASTEXITCODE -ne 0) { throw "前端 $check 失败" }
    }
} finally { Pop-Location; Remove-Item Env:CREATOROS_TESTING -ErrorAction SilentlyContinue }
if ($Browser) {
    & .\.venv\Scripts\python.exe scripts/generate_fixtures.py
    if ($LASTEXITCODE -ne 0) { throw '生成测试素材失败' }
    $previousBrowser = $env:CREATOROS_BROWSER
    if (-not $previousBrowser) { $env:CREATOROS_BROWSER = 'edge' }
    try {
        & node scripts/browser-e2e.cjs
        if ($LASTEXITCODE -ne 0) { throw '浏览器验收失败' }
    } finally {
        if (-not $previousBrowser) { Remove-Item Env:CREATOROS_BROWSER -ErrorAction SilentlyContinue }
    }
}
