@echo off
REM === Agent Status LED — One-Command Install ===
REM Install deps, detect ESP32, flash firmware, register plugin.
REM Usage:   scripts\install.bat                 (full install)
REM          scripts\install.bat --plugin-only   (skip firmware flash)
setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0.."
set "PLUGINS_DIR=%USERPROFILE%\.config\opencode\plugins"
set "CONFIG_FILE=%USERPROFILE%\.config\opencode\opencode.jsonc"
set "SCRIPT_DIR=%~dp0"
set SKIP_FLASH=0

if "%1"=="--plugin-only" set SKIP_FLASH=1
if "%1"=="--skip-flash"  set SKIP_FLASH=1

cd /d "%PROJECT_DIR%"

echo.
echo ╔══════════════════════════════════════════════╗
echo ║   Agent Status LED — Installer v2           ║
echo ╚══════════════════════════════════════════════╝
echo.

REM ═══════════════════════════════════════════════
REM  Step 1 — Python dependencies
REM ═══════════════════════════════════════════════
echo [1/4] Python dependencies...
where python >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] Python 3 required — https://python.org
    pause & exit /b 1
)
python -c "import serial" >nul 2>&1
if errorlevel 1 (
    echo   Installing pyserial...
    python -m pip install pyserial -q
)
echo   [OK]   Python + pyserial

REM ═══════════════════════════════════════════════
REM  Step 2 — Detect ESP32 + Flash
REM ═══════════════════════════════════════════════
if %SKIP_FLASH%==1 (
    echo [2/4] Skip firmware (--plugin-only)
    goto :skip_flash
)

echo [2/4] ESP32 detection...
for /f "delims=" %%a in ('python -c "import serial.tools.list_ports; ports=list(serial.tools.list_ports.comports()); esp=[p.device for p in ports if p.vid in (0x303A,0x10C4,0x1A86) or 'CH34' in (p.description or '') or 'ESP' in (p.description or '')]; print(esp[0] if esp else '')" 2^>nul') do set "ESP_PORT=%%a"

if "%ESP_PORT%"=="" (
    echo   [SKIP] No ESP32 found. Connect USB and re-run, or:
    echo          scripts\flash.bat
    goto :skip_flash
)
echo   [OK]   Found: %ESP_PORT%

REM ── PlatformIO ──────────────────────
where pio >nul 2>&1
if errorlevel 1 (
    echo   Installing PlatformIO...
    python -m pip install platformio -q 2>nul
)
echo   Flashing %ESP_PORT%...
pio run -t upload --upload-port %ESP_PORT% 2>&1 | findstr /C:"SUCCESS" /C:"FAILED" >nul
if errorlevel 1 (
    echo   [FAIL] Flash failed — retry: scripts\flash.bat
) else (
    echo   [OK]   Firmware flashed
)

:skip_flash

REM ═══════════════════════════════════════════════
REM  Step 3 — User-level plugin
REM ═══════════════════════════════════════════════
echo [3/4] Plugin install...
if not exist "%PLUGINS_DIR%" mkdir "%PLUGINS_DIR%"
copy /Y "%SCRIPT_DIR%agent-led-plugin.mjs" "%PLUGINS_DIR%\agent-led-plugin.mjs" >nul
copy /Y "%SCRIPT_DIR%agent_relay.py" "%PLUGINS_DIR%\agent_relay.py" >nul
echo   [OK]   Copied to %PLUGINS_DIR%

if not exist "%CONFIG_FILE%" (
    echo { "plugin": ["./plugins/agent-led-plugin.mjs"] } > "%CONFIG_FILE%"
) else (
    findstr /C:"agent-led-plugin" "%CONFIG_FILE%" >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -Command ^
            "$c = Get-Content '%CONFIG_FILE%' -Raw -Encoding UTF8 | ConvertFrom-Json; $c.plugin = @($c.plugin) + './plugins/agent-led-plugin.mjs'; $c | ConvertTo-Json -Depth 10 | Set-Content '%CONFIG_FILE%' -Encoding UTF8 -NoNewline" 2>nul
    )
)
echo   [OK]   Registered in opencode.jsonc

REM ═══════════════════════════════════════════════
REM  Step 4 — Verify
REM ═══════════════════════════════════════════════
echo [4/4] Verify...
set ERR=0
if not exist "%PLUGINS_DIR%\agent-led-plugin.mjs" (echo   [MISS] plugin & set /a ERR+=1)
if not exist "%PLUGINS_DIR%\agent_relay.py"      (echo   [MISS] relay  & set /a ERR+=1)
findstr /C:"agent-led-plugin" "%CONFIG_FILE%" >nul 2>&1 || (echo   [MISS] config & set /a ERR+=1)
if %ERR%==0 (echo   [OK]   All checks passed) else (echo   [!ERR! issue(s)])

echo.
echo ╔══════════════════════════════════════════════╗
echo ║  Done! Restart OpenCode to activate.        ║
echo ║  Test: node scripts\test-publisher.mjs      ║
echo ║  Stop: scripts\stop_monitor.bat             ║
echo ╚══════════════════════════════════════════════╝
endlocal
