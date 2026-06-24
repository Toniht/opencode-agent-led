# Agent Status LED — Safe Stop Monitor (PowerShell)
# Reads relay PID from .omo/monitor/relay.pid and stops only that process.
param(
    [switch]$Force = $false
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PidFile = Join-Path $ProjectDir ".omo\monitor\relay.pid"

if (-not (Test-Path $PidFile)) {
    Write-Host "[stop_monitor] No relay.pid found - monitor may not be running."
    Write-Host "[stop_monitor] Run 'scripts\start_monitor.ps1' first, or use plugin auto-start."
    exit 0
}

$Pid = (Get-Content $PidFile -Raw).Trim()

if ($Pid -notmatch '^\d+$') {
    Write-Host "[stop_monitor] Invalid PID in relay.pid: '$Pid'"
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    exit 1
}

$proc = Get-Process -Id $Pid -ErrorAction SilentlyContinue
if (-not $proc) {
    Write-Host "[stop_monitor] PID $Pid not found - already stopped."
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    exit 0
}

Write-Host "[stop_monitor] Stopping relay (PID $Pid, name=$($proc.ProcessName))..."
Stop-Process -Id $Pid -Force:$Force
Write-Host "[stop_monitor] Relay stopped."
exit 0
