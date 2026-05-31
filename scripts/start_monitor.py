#!/usr/bin/env python3
"""Start the agent monitor pipeline: bridge + relay in one process."""
import subprocess, sys, time, os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Kill existing
subprocess.run(['taskkill','/f','/im','python.exe'], capture_output=True)
time.sleep(1)

# Start pipeline
print("=== Agent Status LED Monitor ===")
bridge = subprocess.Popen(
    [sys.executable, 'scripts/agent_bridge.py', '--interval', '0.3'],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT
)
relay = subprocess.Popen(
    [sys.executable, 'scripts/agent_relay.py', '--port', 'COM9', '-v'],
    stdin=bridge.stdout, stderr=subprocess.STDOUT
)
bridge.stdout.close()

print("Pipeline started. Press Ctrl+C to stop.")
try:
    relay.wait()
except KeyboardInterrupt:
    bridge.terminate()
    relay.terminate()
