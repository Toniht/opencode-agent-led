#!/usr/bin/env python3
"""
Agent Bridge — watches .omo/agent_state file, pipes to agent_relay.

The OpenCode agent writes its state (EXECUTING/IDLE/ERROR/QUESTION) to .omo/agent_state.
This script watches that file and pipes changes to stdout for agent_relay.py.

Serial port auto-detection is handled by agent_relay.py on the receiving end of the pipe.
No port configuration is needed here.

Usage:
    python scripts/agent_bridge.py | python scripts/agent_relay.py       # auto-detect ESP32
    python scripts/agent_bridge.py | python scripts/agent_relay.py --port COM9
    python scripts/agent_bridge.py --interval 0.5
"""

import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / ".omo" / "agent_state"
STATS_FILE = Path(__file__).resolve().parent.parent / ".omo" / "task_stats.csv"
POLL_INTERVAL = 0.3
STATS_REPORT_INTERVAL = 10  # print summary every N transitions

def read_state():
    try:
        if STATE_FILE.exists():
            content = STATE_FILE.read_text(encoding="utf-8").strip()
            if content:
                return content
    except:
        pass
    return "IDLE"


def _today_transitions():
    """Count today's EXECUTING->IDLE transitions from CSV."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    count = 0
    try:
        if STATS_FILE.exists():
            with STATS_FILE.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ts = row.get("timestamp", "")
                    if ts.startswith(today_str) and row.get("state_to") == "IDLE":
                        count += 1
    except Exception:
        pass
    return count


def print_stats_summary(stats_file=None, label=""):
    """Read stats CSV and print summary to stderr."""
    sf = stats_file or STATS_FILE
    if not sf.exists():
        print(f"[stats] no stats file found", file=sys.stderr)
        return

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    durations = []
    total_tasks = 0
    last_duration = None

    try:
        with sf.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        for row in rows:
            ts = row.get("timestamp", "")
            dur = row.get("duration_seconds", "")
            if ts.startswith(today_str):
                total_tasks += 1
                try:
                    d = float(dur)
                    durations.append(d)
                    last_duration = d
                except (ValueError, TypeError):
                    pass
            else:
                try:
                    d = float(dur)
                    last_duration = d
                except (ValueError, TypeError):
                    pass

        avg = sum(durations) / len(durations) if durations else 0.0

        label_prefix = f"[stats] [{label}] " if label else "[stats] "
        print(f"{label_prefix}last task: {last_duration:.1f}s" if last_duration is not None else f"{label_prefix}last task: N/A", file=sys.stderr)
        print(f"{label_prefix}tasks today: {total_tasks}", file=sys.stderr)
        print(f"{label_prefix}avg duration: {avg:.1f}s (from {len(durations)} tasks)", file=sys.stderr)
    except Exception as e:
        print(f"[stats] error reading stats: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=POLL_INTERVAL)
    parser.add_argument("--stats", action="store_true",
                        help="Print stats summary on exit")
    parser.add_argument("--stats-interval", type=int, default=STATS_REPORT_INTERVAL,
                        help=f"Print stats summary every N transitions (default: {STATS_REPORT_INTERVAL})")
    args = parser.parse_args()

    last_state = None
    exec_start = None          # timestamp when state became EXECUTING
    transition_count = 0       # number of state transitions seen
    task_count = 0             # number of completed EXECUTING->IDLE transitions

    # Ensure .omo directory exists
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Ensure CSV header exists
    if not STATS_FILE.exists():
        STATS_FILE.write_text("timestamp,duration_seconds,state_from,state_to\n", encoding="utf-8")

    print(f"[bridge] watching {STATE_FILE}", file=sys.stderr)
    print(f"[bridge] poll={args.interval}s", file=sys.stderr)
    if args.stats:
        print(f"[bridge] --stats enabled: summary will print on exit", file=sys.stderr)

    try:
        while True:
            state = read_state()
            if state != last_state:
                now = datetime.now(timezone.utc)
                ts = now.strftime("%H:%M:%S")
                transition_count += 1

                # Track EXECUTING duration
                if state == "EXECUTING":
                    exec_start = now
                elif state == "IDLE" and last_state == "EXECUTING" and exec_start is not None:
                    duration = (now - exec_start).total_seconds()
                    task_count += 1

                    # Log to CSV
                    try:
                        with STATS_FILE.open("a", encoding="utf-8", newline="") as f:
                            writer = csv.writer(f)
                            writer.writerow([
                                now.isoformat(),
                                f"{duration:.3f}",
                                last_state,
                                state,
                            ])
                    except Exception as e:
                        print(f"[bridge] failed to write stats: {e}", file=sys.stderr)

                    # Print transition detail with duration
                    print(f"[bridge] {ts} {last_state} -> {state} ({duration:.1f}s)", file=sys.stderr)
                    print(state, flush=True)
                    last_state = state
                    exec_start = None

                    # Periodic summary every N completed tasks
                    if task_count > 0 and task_count % args.stats_interval == 0:
                        print_stats_summary(label=f"every-{args.stats_interval}")
                else:
                    # Non-duration state transitions
                    prev = last_state
                    print(f"[bridge] {ts} {prev or 'NONE'} -> {state}", file=sys.stderr)
                    print(state, flush=True)
                    last_state = state

                    # Clear exec_start if leaving EXECUTING for a non-IDLE state
                    if prev == "EXECUTING" and state != "EXECUTING":
                        exec_start = None

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("[bridge] stopped", file=sys.stderr)
    finally:
        if args.stats:
            print("[bridge] --- stats summary ---", file=sys.stderr)
            print_stats_summary(label="final")

if __name__ == "__main__":
    main()
