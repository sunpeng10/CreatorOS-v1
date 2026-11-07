param([int]$WebPort = 3000, [int]$ApiPort = 8000, [switch]$Dev)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$statePath = Join-Path $projectRoot 'data\processes.json'
if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $running = @($state.processes | Where-Object { $process = Get-Process -Id $_.id -ErrorAction SilentlyContinue; $process -and $process.StartTime.ToUniversalTime().Ticks -eq $_.started_ticks })
    if ($running.Count -gt 0) {
        Write-Host "已有项目进程运行。Web: $($state.web_url) API: $($state.api_url)/docs"
        Write-Host '需要重启时先运行 .\scripts\stop.ps1。'
        exit 0
    }
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw '请先执行 .\scripts\setup.ps1' }
if (Test-Path -LiteralPath '.env') {
    foreach ($line in (Get-Content -LiteralPath '.env')) {
        if (-not $PSBoundParameters.ContainsKey('ApiPort') -and $line -match '^API_PORT=(\d{1,5})\s*$') { $ApiPort = [int]$Matches[1] }
        if (-not $PSBoundParameters.ContainsKey('WebPort') -and $line -match '^WEB_PORT=(\d{1,5})\s*$') { $WebPort = [int]$Matches[1] }
    }
}
function Select-FreePort([int]$candidate) {
    for ($offset = 0; $offset -lt 20; $offset++) {
        $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, ($candidate + $offset))
        try { $listener.Start(); $listener.Stop(); return ($candidate + $offset) } catch { $listener.Stop() }
    }
    throw "无法在 $candidate 附近找到空闲端口"
}
$ApiPort = Select-FreePort $ApiPort
$WebPort = Select-FreePort $(if ($WebPort -eq $ApiPort) { $WebPort + 1 } else { $WebPort })
$env:PYTHONUTF8 = '1'
$env:WEB_ORIGIN = "http://127.0.0.1:$WebPort"
$env:API_URL = "http://127.0.0.1:$ApiPort"
$env:NEXT_TELEMETRY_DISABLED = '1'
$env:PYTHONPATH = Join-Path $projectRoot 'services\api'
New-Item -ItemType Directory -Force -Path 'data\logs' | Out-Null
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$nextExe = Join-Path $projectRoot 'apps\web\node_modules\next\dist\bin\next'
$nodeExe = (Get-Command node.exe).Source
if (-not (Test-Path -LiteralPath $nextExe)) { throw '缺少前端依赖，请运行 setup.ps1' }
$apiProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$ApiPort") -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'data\logs\api.stdout.log' -RedirectStandardError 'data\logs\api.stderr.log'
$mode = if ($Dev -or -not (Test-Path -LiteralPath 'apps\web\.next\BUILD_ID')) { 'dev' } else { 'start' }
$webArgs = @(('"' + $nextExe + '"'), $mode, '--hostname', '127.0.0.1', '--port', "$WebPort")
if ($mode -eq 'dev') { $webArgs += '--webpack' }
$webProcess = Start-Process -FilePath $nodeExe -ArgumentList $webArgs -WorkingDirectory (Join-Path $projectRoot 'apps\web') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot 'data\logs\web.stdout.log') -RedirectStandardError (Join-Path $projectRoot 'data\logs\web.stderr.log')
$processes = @(@{id=$apiProcess.Id; started_ticks=$apiProcess.StartTime.ToUniversalTime().Ticks; kind='api'}, @{id=$webProcess.Id; started_ticks=$webProcess.StartTime.ToUniversalTime().Ticks; kind='web'})
$state = @{processes=$processes; web_url="http://127.0.0.1:$WebPort"; api_url="http://127.0.0.1:$ApiPort"; mode=$mode}
$state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $statePath -Encoding utf8
function Wait-Healthy([string]$url) {
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try { $response = Invoke-WebRequest -Uri $url -TimeoutSec 2 -UseBasicParsing; if ($response.StatusCode -eq 200) { return } } catch { }
        Start-Sleep -Milliseconds 500
    }
    throw "服务未就绪: $url。请查看 data\logs 日志。"
}
Wait-Healthy "$($state.api_url)/api/health"
Wait-Healthy $state.web_url
Wait-Healthy "$($state.web_url)/api/health"
Write-Host "CreatorOS 已启动（$mode）。"
Write-Host "Web: $($state.web_url)"
Write-Host "API: $($state.api_url)/docs"
Write-Host '停止命令: .\scripts\stop.ps1'
