@echo off
REM === Agent Status LED — Setup for new machine ===
echo Installing dependencies...

REM Python
where python >nul 2>&1 || (echo ERROR: Python 3 not found & exit /b 1)
python -m pip install pyserial -q

REM PlatformIO
where pio >nul 2>&1 || (echo ERROR: PlatformIO CLI not found - run: pip install platformio & exit /b 1)

REM ESP32 platform
pio platform install espressif32

echo.
echo Setup complete. Next steps:
echo   1. Connect ESP32-S3 via USB
echo   2. Check COM port: pio device list
echo   3. Update COM port in scripts\start_monitor.bat if needed
echo   4. Flash firmware: pio run -t upload --upload-port COMx
echo   5. Start monitor: scripts\start_monitor.bat
