# Start Agent Status Monitor Pipeline
# Usage: .\scripts\start_monitor.ps1
# Auto-detects ESP32 serial port, then starts bridge+relay pipeline

$ErrorActionPreference = "Stop"

Write-Host "=== Agent Status LED Monitor ===" -ForegroundColor Green
Write-Host ""

# Kill any existing Python processes
$existing = Get-Process python* -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Stopping existing monitor processes..." -ForegroundColor Yellow
    $existing | Stop-Process -Force
    Start-Sleep -Seconds 1
}

# ── Auto-detect ESP32 port (via Python) ────────────────────────────
Write-Host "Detecting ESP32..." -ForegroundColor Cyan

$detectScript = @"
import sys; sys.path.insert(0, 'scripts')
from agent_relay import SerialManager
candidates = SerialManager.auto_detect_all_esp32()
if not candidates:
    print('NONE')
else:
    for c in candidates:
        print(c)
"@

$espPorts = & python -c $detectScript 2>$null
if (-not $espPorts -or $espPorts[0] -eq "NONE") {
    Write-Host "ERROR: No ESP32 device detected." -ForegroundColor Red
    # Show available ports
    $allPorts = & python -c "from agent_relay import SerialManager; print(', '.join(SerialManager.list_ports()))" 2>$null
    if ($allPorts) {
        Write-Host "  Available serial ports: $allPorts" -ForegroundColor Yellow
    } else {
        Write-Host "  No serial ports found at all." -ForegroundColor Yellow
    }
    Write-Host "  Connect ESP32 via USB and retry." -ForegroundColor Yellow
    exit 1
}

$espPort = $null
if ($espPorts.Count -eq 1) {
    $espPort = $espPorts[0].Trim()
    Write-Host "  ESP32 detected on $espPort" -ForegroundColor Green
} else {
    # Multiple candidates
    Write-Host "Multiple ESP32 devices detected:" -ForegroundColor Yellow
    for ($i = 0; $i -lt $espPorts.Count; $i++) {
        Write-Host "  [$($i+1)] $($espPorts[$i].Trim())" -ForegroundColor Gray
    }
    while ($true) {
        $choice = Read-Host "Select device [1-$($espPorts.Count)]"
        try {
            $idx = [int]$choice
            if ($idx -ge 1 -and $idx -le $espPorts.Count) {
                $espPort = $espPorts[$idx-1].Trim()
                Write-Host "  Using $espPort" -ForegroundColor Green
                break
            }
        } catch {}
        Write-Host "  Invalid choice: $choice" -ForegroundColor Red
    }
}

# ── Initialize state file ───────────────────────────────────────────
$stateFile = ".omo\agent_state"
if (-not (Test-Path $stateFile)) {
    "IDLE" | Out-File -FilePath $stateFile -Encoding utf8 -NoNewline
}

# ── Start pipeline ───────────────────────────────────────────────────
Write-Host ""
Write-Host "Starting pipeline: agent_bridge | agent_relay" -ForegroundColor Cyan
Write-Host "  Bridge: watches .omo/agent_state" -ForegroundColor Gray
Write-Host "  Relay:  $espPort @ 115200 baud" -ForegroundColor Gray
Write-Host "  Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

python scripts/agent_bridge.py | python scripts/agent_relay.py --port $espPort -v
