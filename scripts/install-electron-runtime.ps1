$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$modulePath = Join-Path $projectRoot 'apps\desktop\node_modules\electron'
if (Test-Path -LiteralPath (Join-Path $modulePath 'dist\electron.exe')) { return }
$version = (Get-Content -LiteralPath (Join-Path $modulePath 'package.json') -Raw | ConvertFrom-Json).version
$archiveName = "electron-v$version-win32-x64.zip"
$cacheFolder = Join-Path $projectRoot 'data\desktop'
New-Item -ItemType Directory -Force -Path $cacheFolder | Out-Null
$archivePath = Join-Path $cacheFolder 'electron-runtime.zip'
$checksums = Get-Content -LiteralPath (Join-Path $modulePath 'checksums.json') -Raw | ConvertFrom-Json
$expected = $checksums.PSObject.Properties[$archiveName].Value
if (-not $expected) { throw '缺少官方运行时 SHA256，已停止安装' }
$valid = (Test-Path -LiteralPath $archivePath) -and ((Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash -eq $expected)
if (-not $valid) {
    $downloadArgs = @('-L','--fail','--silent','--show-error','--max-time','240','--output',$archivePath,"https://github.com/electron/electron/releases/download/v$version/$archiveName")
    if ($env:HTTPS_PROXY) { $downloadArgs = @('--proxy',$env:HTTPS_PROXY) + $downloadArgs }
    & curl.exe @downloadArgs
    if ($LASTEXITCODE -ne 0) { throw '官方运行时下载失败，请检查网络或 HTTPS_PROXY 后重试' }
}
if ((Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash -ne $expected) { throw '运行时 SHA256 校验失败，已停止安装' }
Expand-Archive -LiteralPath $archivePath -DestinationPath (Join-Path $modulePath 'dist') -Force
[IO.File]::WriteAllText((Join-Path $modulePath 'path.txt'), 'electron.exe', [Text.UTF8Encoding]::new($false))
Write-Host 'Electron 官方运行时 SHA256 校验并安装完成。'
