@echo off
REM Agent Status LED Monitor
cd /d %~dp0..
echo === Agent Status LED Monitor ===
REM Initialize state to IDLE (prevents stale EXECUTING from previous session)
echo IDLE> .omo\monitor\agent_state
echo Starting pipeline: bridge ^| relay (auto-detect ESP32)
echo Press Ctrl+C to stop
echo.
python scripts\agent_bridge.py --interval 0.3 --stats | python scripts\agent_relay.py -v
