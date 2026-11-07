param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not $SkipBuild) {
    & .\.venv\Scripts\python.exe scripts/generate_desktop_icon.py
    if ($LASTEXITCODE -ne 0) { throw '生成桌面图标失败' }
    Push-Location -LiteralPath 'apps\desktop'
    $priorHttpsProxy = $env:HTTPS_PROXY
    $priorNodeProxy = $env:NODE_USE_ENV_PROXY
    try {
        if (-not $env:HTTPS_PROXY) {
            $proxySettings = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -Name ProxyEnable,ProxyServer -ErrorAction SilentlyContinue
            if ($proxySettings.ProxyEnable -and $proxySettings.ProxyServer -match '127\.0\.0\.1:(\d+)') {
                $env:HTTPS_PROXY = 'http://127.0.0.1:' + $Matches[1]
                $env:NODE_USE_ENV_PROXY = '1'
            }
        }
        if (-not (Test-Path -LiteralPath 'node_modules\electron\package.json')) {
            & npm.cmd ci --registry https://registry.npmjs.org
            if ($LASTEXITCODE -ne 0) { throw '桌面依赖安装失败' }
        }
        & (Join-Path $PSScriptRoot 'install-electron-runtime.ps1')
        & npm.cmd run package
        if ($LASTEXITCODE -ne 0) { throw '桌面打包失败，请关闭桌面应用后重试' }
    } finally {
        $env:HTTPS_PROXY = $priorHttpsProxy
        $env:NODE_USE_ENV_PROXY = $priorNodeProxy
        Pop-Location
    }
}
$exe = (Get-Content -LiteralPath (Join-Path $projectRoot 'data\desktop\current.json') -Raw | ConvertFrom-Json).executable
if (-not (Test-Path -LiteralPath $exe)) { throw '缺少桌面运行包' }
$shell = New-Object -ComObject WScript.Shell
$destinations = @([Environment]::GetFolderPath('Desktop'), (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'))
foreach ($folder in $destinations) {
    $shortcut = $shell.CreateShortcut((Join-Path $folder 'CreatorOS 爆款实验室.lnk'))
    $shortcut.TargetPath = $exe
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.IconLocation = (Join-Path $projectRoot 'apps\desktop\assets\creatoros.ico')
    $shortcut.Description = 'CreatorOS · 爆款实验室'
    $shortcut.Save()
}
Write-Host '桌面与开始菜单入口已创建，双击 CreatorOS 爆款实验室即可打开。'
