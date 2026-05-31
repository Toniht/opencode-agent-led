@echo off
REM Agent Status LED Monitor
cd /d %~dp0..
echo === Agent Status LED Monitor ===
REM Initialize state to IDLE (prevents stale EXECUTING from previous session)
echo IDLE> .omo\agent_state
echo Starting pipeline: bridge ^| relay
echo Press Ctrl+C to stop
echo.
python scripts\agent_bridge.py --interval 0.3 | python scripts\agent_relay.py --port COM9 -v
