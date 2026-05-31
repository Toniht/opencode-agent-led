# Start Agent Status Monitor Pipeline
# Usage: .\scripts\start_monitor.ps1
# Stops any existing monitor, starts bridge+relay pipeline

$ErrorActionPreference = "Stop"

Write-Host "=== Agent Status LED Monitor ===" -ForegroundColor Green
Write-Host ""

# Kill any existing Python processes holding COM9
$existing = Get-Process python* -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Stopping existing monitor processes..." -ForegroundColor Yellow
    $existing | Stop-Process -Force
    Start-Sleep -Seconds 1
}

# Verify ESP32 is connected
Write-Host "Detecting ESP32..." -ForegroundColor Cyan
$ports = [System.IO.Ports.SerialPort]::GetPortNames()
$espPort = $ports | Where-Object { $_ -eq "COM9" }
if (-not $espPort) {
    Write-Host "WARNING: COM9 not found. Available ports: $($ports -join ', ')" -ForegroundColor Yellow
    Write-Host "Connect ESP32 and retry." -ForegroundColor Yellow
    exit 1
}
Write-Host "  ESP32 on COM9" -ForegroundColor Green

# Initialize state file
$stateFile = ".omo\agent_state"
if (-not (Test-Path $stateFile)) {
    "IDLE" | Out-File -FilePath $stateFile -Encoding utf8 -NoNewline
}

# Start pipeline
Write-Host ""
Write-Host "Starting pipeline: agent_bridge | agent_relay" -ForegroundColor Cyan
Write-Host "  Bridge: watches .omo/agent_state" -ForegroundColor Gray
Write-Host "  Relay: COM9 @ 115200 baud" -ForegroundColor Gray
Write-Host "  Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

python scripts/agent_bridge.py | python scripts/agent_relay.py --port COM9 -v
