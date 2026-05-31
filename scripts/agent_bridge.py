#!/usr/bin/env python3
"""
Agent Bridge v2 - watches .omo/agent_state file, pipes to relay.

The OpenCode agent writes its state (EXECUTING/IDLE/ERROR/QUESTION) to .omo/agent_state.
This script watches that file and pipes changes to stdout for agent_relay.py.

Usage:
    python scripts/agent_bridge.py | python scripts/agent_relay.py --port COM9
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / ".omo" / "agent_state"
POLL_INTERVAL = 0.3

def read_state():
    try:
        if STATE_FILE.exists():
            content = STATE_FILE.read_text(encoding="utf-8").strip()
            if content:
                return content
    except:
        pass
    return "IDLE"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=POLL_INTERVAL)
    args = parser.parse_args()

    last_state = None

    print(f"[bridge] watching {STATE_FILE}", file=sys.stderr)
    print(f"[bridge] poll={args.interval}s", file=sys.stderr)

    try:
        while True:
            state = read_state()
            if state != last_state:
                ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print(f"[bridge] {ts} {last_state or 'NONE'} -> {state}", file=sys.stderr)
                print(state, flush=True)
                last_state = state
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("[bridge] stopped", file=sys.stderr)

if __name__ == "__main__":
    main()
