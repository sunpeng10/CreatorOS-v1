param([string]$PythonPath = '', [switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = '1'
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw '需要 Node.js 20.9+，请从 nodejs.org 安装 LTS 后重试。' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    $candidates = @($PythonPath, (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'), 'python')
    $selectedPython = $null
    foreach ($candidate in $candidates) {
        if (-not $candidate) { continue }
        try {
            & $candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { $selectedPython = $candidate; break }
        } catch { }
    }
    if (-not $selectedPython) { throw '需要 Python 3.11+。可用 -PythonPath 指定已安装解释器；不会修改系统配置。' }
    & $selectedPython -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '创建虚拟环境失败' }
}
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not $SkipInstall) {
    $requirementsPath = if (Test-Path -LiteralPath 'services\api\requirements.lock') { 'services\api\requirements.lock' } else { 'services\api\requirements.txt' }
    & $pythonExe -m pip install -r $requirementsPath --index-url https://pypi.org/simple
    if ($LASTEXITCODE -ne 0) { throw 'Python 依赖安装失败，请检查网络/代理后重跑 setup.ps1。' }
    Push-Location -LiteralPath 'apps\web'
    try {
        if (Test-Path -LiteralPath 'package-lock.json') { & npm.cmd ci } else { & npm.cmd install }
        if ($LASTEXITCODE -ne 0) { throw '前端依赖安装失败' }
    } finally { Pop-Location }
}
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
New-Item -ItemType Directory -Force -Path 'data' | Out-Null
& $pythonExe -m alembic -c services/api/alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) { throw '数据库迁移失败' }
$env:PYTHONPATH = Join-Path $projectRoot 'services\api'
& $pythonExe -m app.cli init-admin --generate
if ($LASTEXITCODE -ne 0) { throw '管理员初始化失败' }
Write-Host '初始化完成。运行 .\scripts\start.ps1 启动；管理员随机凭证见 data\admin-credentials.txt。'
