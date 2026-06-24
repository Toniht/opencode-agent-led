@echo off
REM === Agent Status LED — Safe Stop Monitor ===
REM Reads relay PID from .omo/monitor/relay.pid and kills only that process.
REM Unlike "taskkill /IM python.exe", this won't kill other Python processes.
setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0.."
set "PID_FILE=%PROJECT_DIR%\.omo\monitor\relay.pid"

if not exist "%PID_FILE%" (
    echo [stop_monitor] No relay.pid found — monitor may not be running.
    echo [stop_monitor] Run "scripts\start_monitor.bat" first, or use plugin auto-start.
    exit /b 0
)

set /p PID=<"%PID_FILE%"

REM Validate PID is numeric
set "valid=1"
for /f "delims=0123456789" %%a in ("!PID!") do set "valid="
if not defined valid (
    echo [stop_monitor] Invalid PID in relay.pid: '!PID!'
    del "%PID_FILE%" 2>nul
    exit /b 1
)

REM Check if process exists
tasklist /FI "PID eq !PID!" 2>nul | find "!PID!" >nul
if errorlevel 1 (
    echo [stop_monitor] PID !PID! not found — already stopped.
    del "%PID_FILE%" 2>nul
    exit /b 0
)

echo [stop_monitor] Stopping relay (PID !PID!)...
taskkill /PID !PID! >nul 2>&1
if errorlevel 1 (
    echo [stop_monitor] ERROR: Failed to stop PID !PID!
    exit /b 1
)

echo [stop_monitor] Relay stopped (PID !PID!).
REM PID file will be cleaned up by plugin on exit
exit /b 0
