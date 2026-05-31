#!/usr/bin/env python3
"""Start the agent monitor pipeline: auto-detect ESP32, then bridge + relay in one process.

The script auto-detects the ESP32 serial port before launching the pipeline.
If multiple ESP32 devices are found, it prompts the user to choose one.
"""
import subprocess
import sys
import time
import os

# Ensure we're in the project root
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add scripts dir to path so we can import agent_relay
sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))
from agent_relay import SerialManager, HAS_SERIAL

# ── Auto-detect ESP32 port ──────────────────────────────────────────
def detect_port():
    """Detect ESP32 port. If multiple, prompt user. Returns port string or None."""
    if not HAS_SERIAL:
        print("ERROR: pyserial not installed. Run: pip install pyserial", file=sys.stderr)
        return None

    candidates = SerialManager.auto_detect_all_esp32()
    if not candidates:
        print("ERROR: No ESP32 device detected.", file=sys.stderr)
        all_ports = SerialManager.list_ports()
        if all_ports:
            print(f"  Available serial ports: {', '.join(all_ports)}", file=sys.stderr)
        else:
            print("  No serial ports found at all.", file=sys.stderr)
        print("  Connect ESP32 via USB and retry.", file=sys.stderr)
        return None

    if len(candidates) == 1:
        print(f"ESP32 detected on {candidates[0]}")
        return candidates[0]

    # Multiple candidates — prompt
    print(f"\nMultiple ESP32 devices detected ({len(candidates)}):")
    for i, dev in enumerate(candidates, 1):
        print(f"  [{i}] {dev}")
    while True:
        try:
            choice = input(f"Select device [1-{len(candidates)}]: ").strip()
            idx = int(choice)
            if 1 <= idx <= len(candidates):
                print(f"Using {candidates[idx - 1]}")
                return candidates[idx - 1]
            print(f"  Invalid choice: {choice}")
        except (ValueError, EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return None


# ── Main ─────────────────────────────────────────────────────────────
def main():
    print("=== Agent Status LED Monitor ===")

    # Kill existing Python processes
    subprocess.run(["taskkill", "/f", "/im", "python.exe"],
                   capture_output=True)
    time.sleep(1)

    # Detect port
    port = detect_port()
    if not port:
        sys.exit(1)

    # Start pipeline
    bridge = subprocess.Popen(
        [sys.executable, "scripts/agent_bridge.py", "--interval", "0.3"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    relay = subprocess.Popen(
        [sys.executable, "scripts/agent_relay.py", "--port", port, "-v"],
        stdin=bridge.stdout,
        stderr=subprocess.STDOUT,
    )
    bridge.stdout.close()

    print(f"Pipeline started on {port}. Press Ctrl+C to stop.")
    try:
        relay.wait()
    except KeyboardInterrupt:
        bridge.terminate()
        relay.terminate()


if __name__ == "__main__":
    main()
