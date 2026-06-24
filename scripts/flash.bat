@echo off
REM === Agent Status LED — Safe Flash (with PID-aware stop) ===
REM Stops only the relay process (not all Python), then flashes firmware.
setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0.."
set "PID_FILE=%PROJECT_DIR%\.omo\monitor\relay.pid"

echo.
echo ╔══════════════════════════════════════╗
echo ║  Agent Status LED — Safe Flash      ║
echo ╚══════════════════════════════════════╝
echo.

REM ── Step 1: Stop relay safely ──────────────────
if exist "%PID_FILE%" (
    set /p PID=<"%PID_FILE%"
    echo [flash] relay PID: !PID!
    tasklist /FI "PID eq !PID!" 2>nul | find "!PID!" >nul
    if not errorlevel 1 (
        echo [flash] stopping relay (PID !PID!)...
        taskkill /PID !PID! >nul 2>&1
        if errorlevel 1 (
            echo [flash] WARNING: Could not stop PID !PID! — port may be busy.
        ) else (
            echo [flash] relay stopped.
        )
    ) else (
        echo [flash] PID !PID! already gone.
    )
) else (
    echo [flash] No relay.pid — checking for any python holding COM port...
    REM Fallback: try to detect PID from python holding COM port
    for /f "tokens=2" %%a in ('python -c "import subprocess,re;o=subprocess.check_output(['netstat','-ano'],text=True);m=re.findall(r'COM4\s.*?(\d+)',o);print(m[0] if m else '')" 2^>nul') do (
        if not "%%a"=="" (
            echo [flash] Found PID %%a holding COM4, stopping...
            taskkill /PID %%a >nul 2>&1
        )
    )
)

REM ── Step 2: Wait for port release ──────────────
echo [flash] waiting for COM4 release...
timeout /t 2 /nobreak >nul

REM ── Step 3: Flash ──────────────────────────────
echo [flash] flashing firmware to COM4...
pio run -t upload --upload-port COM4

if errorlevel 1 (
    echo.
    echo [flash] FLASH FAILED. If COM4 is still busy, try:
    echo   1. Close OpenCode
    echo   2. Run scripts\flash.bat again
    pause
) else (
    echo.
    echo [flash] SUCCESS! Firmware updated on COM4.
    echo [flash] Restart OpenCode to reload the plugin.
)
