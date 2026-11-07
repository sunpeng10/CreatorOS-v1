$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $projectRoot 'data\processes.json'
if (-not (Test-Path -LiteralPath $statePath)) { Write-Host '没有本项目启动记录。'; exit 0 }
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
function Stop-OwnedTree([int]$processId) {
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$processId" -ErrorAction SilentlyContinue
    foreach ($child in $children) { Stop-OwnedTree $child.ProcessId }
    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
}
foreach ($entry in $state.processes) {
    $process = Get-Process -Id $entry.id -ErrorAction SilentlyContinue
    if ($process -and $process.StartTime.ToUniversalTime().Ticks -eq $entry.started_ticks) {
        if ($PSVersionTable.PSVersion.Major -ge 7) { $process.Kill($true); $process.WaitForExit(5000) | Out-Null }
        else { Stop-OwnedTree $entry.id }
        Write-Host "已停止本项目 $($entry.kind) 进程。"
    }
}
Remove-Item -LiteralPath $statePath
