#!/usr/bin/env python3
"""
Agent Status Relay — PC-side monitor for OpenCode agent state.

Reads OpenCode agent session events (via stdin or auto-detection), maps them to
LED states, and drives an ESP32 LED controller over USB serial per the
contracts/serial-protocol.md protocol.

Usage:
    python scripts/agent_relay.py --dry-run
    python scripts/agent_relay.py --port COM3
    python scripts/agent_relay.py --port COM3 --baud 115200 --heartbeat-interval 1.5

Stdin commands (one per line):
    IDLE         - agent is idle / ready for input
    EXECUTING    - agent is executing a task
    QUESTION     - agent is asking the user a question
    ERROR        - agent encountered an error
    RESET        - clear error counter, return to idle
"""

import argparse
import enum
import logging
import os
import re
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Optional

# ── Serial support (graceful degredation for --dry-run) ──────────────
try:
    import serial
    import serial.tools.list_ports

    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

# ── Logging ──────────────────────────────────────────────────────────
LOG = logging.getLogger("agent_relay")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"


# ═══════════════════════════════════════════════════════════════════════
# AgentState — ordered by priority (lower value = higher priority)
# ═══════════════════════════════════════════════════════════════════════

class AgentState(enum.Enum):
    """Agent operational state with priority for conflict resolution.

    Priority values are integers: lower = higher priority.
    Priority order: ERROR(0) > QUESTIONING(1) > EXECUTING(2) > IDLE(3).
    DISCONNECTED(10) is special — triggered by heartbeat timeout, not by explicit command.
    """

    ERROR = 0
    QUESTIONING = 1
    EXECUTING = 2
    IDLE = 3
    DISCONNECTED = 10  # lowest priority, auto-triggered by timeout

    @property
    def priority(self) -> int:
        return self.value

    @property
    def serial_command(self) -> str:
        """Returns the serial command token for this state."""
        _map = {
            AgentState.IDLE: "IDLE",
            AgentState.EXECUTING: "EXEC",
            AgentState.QUESTIONING: "QUESTION",
            AgentState.ERROR: "ERROR",
            AgentState.DISCONNECTED: None,  # DISCONNECTED is derived — no serial cmd
        }
        return _map[self]

    @property
    def description(self) -> str:
        _map = {
            AgentState.IDLE: "Idle / ready for input",
            AgentState.EXECUTING: "Executing task",
            AgentState.QUESTIONING: "Questioning — waiting for user answer",
            AgentState.ERROR: "Error encountered",
            AgentState.DISCONNECTED: "Serial disconnected (heartbeat timeout)",
        }
        return _map[self]


# ═══════════════════════════════════════════════════════════════════════
# State Priority Resolver
# ═══════════════════════════════════════════════════════════════════════

def resolve_priority(a: AgentState, b: AgentState) -> AgentState:
    """Return the higher-priority state (lower value wins). DISCONNECTED always loses."""
    if a == AgentState.DISCONNECTED:
        return b
    if b == AgentState.DISCONNECTED:
        return a
    return a if a.priority < b.priority else b


# ═══════════════════════════════════════════════════════════════════════
# OpenCode Session Event Detector
# ═══════════════════════════════════════════════════════════════════════

# Patterns for auto-detecting agent state from OpenCode output
_AUTO_PATTERNS = {
    AgentState.EXECUTING: re.compile(
        r"(?:tool_call|executing|running task|Thinking|⏳|🔄|agent.*execut)", re.IGNORECASE
    ),
    AgentState.QUESTIONING: re.compile(
        r"(?:\?\?|ask|question|confirm|prompt|> |input required|waiting for input)", re.IGNORECASE
    ),
    AgentState.ERROR: re.compile(
        r"(?:error|exception|traceback|fail|fatal|ERR|CRITICAL)", re.IGNORECASE
    ),
}


class AgentMonitor:
    """Watches OpenCode agent events and resolves current state.

    Accepts events from:
    1. Stdin lines with explicit commands: "IDLE", "EXECUTING", "QUESTION", "ERROR", "RESET"
    2. Auto-detection mode: parses raw text for execution/error/question patterns.

    The error counter tracks consecutive ERROR events. 3 consecutive errors → errorLocked.
    Only RESET clears the lock.
    """

    # State → valid stdin command tokens (case-insensitive matching)
    _COMMAND_TOKENS: dict[str, AgentState] = {
        "IDLE": AgentState.IDLE,
        "EXECUTING": AgentState.EXECUTING,
        "EXEC": AgentState.EXECUTING,
        "QUESTION": AgentState.QUESTIONING,
        "QUESTIONING": AgentState.QUESTIONING,
        "ERROR": AgentState.ERROR,
        "RESET": None,  # special — handled separately
    }

    def __init__(self, auto_detect: bool = False):
        self._state: AgentState = AgentState.IDLE
        self._error_count: int = 0
        self._error_locked: bool = False
        self._lock = threading.Lock()
        self._callbacks: list = []
        self._auto_detect = auto_detect
        self._last_state: Optional[AgentState] = None

    # ── properties ────────────────────────────────────────────────

    @property
    def state(self) -> AgentState:
        with self._lock:
            return self._state

    @property
    def error_count(self) -> int:
        with self._lock:
            return self._error_count

    @property
    def error_locked(self) -> bool:
        with self._lock:
            return self._error_locked

    # ── callback registration ─────────────────────────────────────

    def on_state_change(self, callback):
        """Register a callback: callback(old_state, new_state, timestamp)."""
        self._callbacks.append(callback)

    # ── event ingestion ───────────────────────────────────────────

    def process_line(self, line: str) -> Optional[AgentState]:
        """Process a single line from OpenCode output/stdin.

        Returns the new state if changed, else None.
        """
        stripped = line.strip()
        if not stripped:
            return None

        # 1) Explicit command path
        upper = stripped.upper()
        if upper in self._COMMAND_TOKENS:
            cmd_state = self._COMMAND_TOKENS[upper]
            if cmd_state is None:  # RESET
                return self._handle_reset()
            return self._set_state(cmd_state)

        # 2) Auto-detection path (optional)
        if self._auto_detect:
            for state, pattern in _AUTO_PATTERNS.items():
                if pattern.search(stripped):
                    return self._set_state(state)

        return None

    def process_command(self, command: str) -> Optional[AgentState]:
        """Process a single explicit state command.

        Valid commands: IDLE, EXECUTING, QUESTION, ERROR, RESET.
        Returns the new state if changed, else None.
        """
        return self.process_line(command)

    # ── internal state machine ────────────────────────────────────

    def _handle_reset(self) -> Optional[AgentState]:
        with self._lock:
            was_locked = self._error_locked
            self._error_count = 0
            self._error_locked = False
            old = self._state
            self._state = AgentState.IDLE
            if was_locked or old != AgentState.IDLE:
                self._notify(old, AgentState.IDLE)
                return AgentState.IDLE
            return None

    def _set_state(self, new_state: AgentState) -> Optional[AgentState]:
        ts = datetime.now(timezone.utc)
        with self._lock:
            old = self._state

            # Error counter logic
            if new_state == AgentState.ERROR:
                self._error_count += 1
                if self._error_count >= 3:
                    self._error_locked = True
                    LOG.warning("[error-lock] %d consecutive errors — LOCKED", self._error_count)
                else:
                    LOG.info("[error-counter] %d/%d", self._error_count, 3)
            elif new_state != AgentState.ERROR and self._error_count > 0:
                # non-ERROR command does NOT reset counter — errors are "sticky"
                # but RESET is handled separately above
                pass

            # Error-locked: reject all non-RESET state changes for ERROR
            if self._error_locked and new_state != AgentState.ERROR:
                LOG.warning("[error-locked] rejecting %s — must RESET first", new_state.name)
                return None

            # Priority resolution — IDLE always accepted (natural resting state)
            if new_state != AgentState.IDLE:
                resolved = resolve_priority(old, new_state)
                if resolved == old and old != AgentState.DISCONNECTED:
                    # lower-priority state attempted — log but don't change
                    if new_state != old:
                        LOG.debug(
                            "[priority] %s (prio=%d) ignored — current %s (prio=%d) is higher",
                            new_state.name, new_state.priority,
                            old.name, old.priority,
                        )
                    return None
            else:
                resolved = new_state

            self._state = resolved
            self._notify(old, resolved)
            return resolved

    def _notify(self, old: AgentState, new: AgentState):
        ts = datetime.now(timezone.utc)
        LOG.info(
            "[state-change] %s → %s  (error_count=%d, locked=%s)",
            old.name, new.name, self._error_count, self._error_locked,
        )
        for cb in self._callbacks:
            try:
                cb(old, new, ts)
            except Exception:
                LOG.exception("callback error")

    # ── stdin event loop ──────────────────────────────────────────

    def run_stdin_loop(self, stop_event: threading.Event):
        """Blocking loop: read lines from stdin, process as state commands."""
        LOG.info("[monitor] reading events from stdin...")
        try:
            for line in sys.stdin:
                if stop_event.is_set():
                    break
                self.process_line(line)
        except (EOFError, KeyboardInterrupt):
            pass
        except Exception:
            LOG.exception("[monitor] stdin read error")
        LOG.info("[monitor] stdin loop stopped")


# ═══════════════════════════════════════════════════════════════════════
# Serial Port Manager
# ═══════════════════════════════════════════════════════════════════════

class SerialManager:
    """Manages the USB serial connection to the ESP32 LED controller."""

    def __init__(self, port: str, baud: int = 115200, dry_run: bool = False):
        self._port = port
        self._baud = baud
        self._dry_run = dry_run
        self._ser: Optional["serial.Serial"] = None
        self._lock = threading.Lock()
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected and not self._dry_run

    def open(self) -> bool:
        """Open the serial port. Returns True on success."""
        if self._dry_run:
            LOG.info("[serial] dry-run mode — no serial port opened")
            self._connected = True
            return True

        if not HAS_SERIAL:
            LOG.error("[serial] pyserial not installed. Run: pip install pyserial")
            return False

        try:
            self._ser = serial.Serial(
                port=self._port,
                baudrate=self._baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.5,
                write_timeout=1.0,
            )
            self._connected = True
            LOG.info("[serial] opened %s @ %d baud", self._port, self._baud)
            # Quick check for ESP32 — don't block stdin processing
            self._wait_ready(timeout=0.5)
            return True
        except serial.SerialException as exc:
            LOG.error("[serial] failed to open %s: %s", self._port, exc)
            return False
        except Exception as exc:
            LOG.error("[serial] unexpected error: %s", exc)
            return False

    def close(self):
        """Close the serial port."""
        with self._lock:
            if self._ser and self._ser.is_open:
                try:
                    self._ser.close()
                    LOG.info("[serial] port closed")
                except Exception:
                    pass
            self._connected = False

    def send_command(self, command: str) -> Optional[str]:
        """Send a newline-delimited command and read the response line.

        Returns the response string (without trailing newline) or None on failure.
        In dry-run mode, prints the command to stdout.
        """
        line = command.strip() + "\n"

        if self._dry_run:
            LOG.info("[dry-run] → %s", command.strip())
            return "OK"  # simulate success

        with self._lock:
            if not self._ser or not self._ser.is_open:
                LOG.warning("[serial] not connected — cannot send '%s'", command)
                self._connected = False
                return None

            try:
                self._ser.reset_input_buffer()
                self._ser.write(line.encode("ascii"))
                # Read response line (ESP32 responds with "OK\n" or "ERR ...\n")
                response = self._ser.readline().decode("ascii", errors="replace").strip()
                LOG.debug("[serial] → %s  ← %s", command.strip(), response)
                return response
            except serial.SerialTimeoutException:
                LOG.warning("[serial] write timeout for '%s'", command)
                self._connected = False
                return None
            except serial.SerialException as exc:
                LOG.warning("[serial] error: %s", exc)
                self._connected = False
                return None

    def _wait_ready(self, timeout: float = 3.0):
        """Wait for the ESP32 to send its READY banner after connection."""
        if not self._ser or not self._ser.is_open:
            return
        deadline = time.time() + timeout
        LOG.info("[serial] waiting for ESP32 READY...")
        while time.time() < deadline:
            if self._ser.in_waiting:
                line = self._ser.readline().decode("ascii", errors="replace").strip()
                if line:
                    LOG.info("[serial] boot: %s", line)
                    if "READY" in line.upper():
                        LOG.info("[serial] ESP32 is READY")
                        return
            time.sleep(0.1)
        LOG.warning("[serial] no READY signal within %.1fs", timeout)

    def is_open(self) -> bool:
        if self._dry_run:
            return True
        with self._lock:
            return self._ser is not None and self._ser.is_open

    @staticmethod
    def list_ports() -> list[str]:
        """List available serial ports. Returns list of device names."""
        if not HAS_SERIAL:
            return []
        return [p.device for p in serial.tools.list_ports.comports()]

    @staticmethod
    def auto_detect_esp32() -> Optional[str]:
        """Try to auto-detect an ESP32 serial port by VID/PID or description."""
        if not HAS_SERIAL:
            return None
        for port in serial.tools.list_ports.comports():
            # ESP32-S3 common VID:PID pairs
            if port.vid and port.pid:
                # Expressif VID = 0x303A, common PIDs: 0x1001 (USB-Serial-JTAG)
                if port.vid == 0x303A or port.vid == 0x10C4:  # 10C4 = Silicon Labs CP210x
                    LOG.info("[detect] found ESP32 candidate: %s (VID:PID=%04X:%04X, desc=%s)",
                             port.device, port.vid, port.pid, port.description)
                    return port.device
            desc = (port.description or "").lower()
            if "esp32" in desc or "ch340" in desc or "cp210" in desc or "usb serial" in desc:
                LOG.info("[detect] found candidate by description: %s (%s)",
                         port.device, port.description)
                return port.device
        return None


# ═══════════════════════════════════════════════════════════════════════
# Heartbeat Loop (background thread)
# ═══════════════════════════════════════════════════════════════════════

class HeartbeatLoop:
    """Sends PING commands on a background thread at the configured interval."""

    def __init__(self, serial_mgr: SerialManager, interval: float = 1.5):
        self._serial = serial_mgr
        self._interval = max(0.5, min(interval, 5.0))  # clamp to sane range
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._failures = 0
        self._max_failures = 3  # consecutive before logging DISCONNECTED

    def start(self):
        """Start the heartbeat background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="heartbeat")
        self._thread.start()
        LOG.info("[heartbeat] started (interval=%.1fs)", self._interval)

    def stop(self):
        """Stop the heartbeat thread."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        LOG.info("[heartbeat] stopped")

    def _run(self):
        """Heartbeat loop — sends PING at interval."""
        while not self._stop.wait(timeout=self._interval):
            if not self._serial.connected:
                self._failures += 1
                if self._failures == 1:
                    LOG.warning("[heartbeat] serial disconnected")
                elif self._failures % 10 == 0:
                    LOG.warning("[heartbeat] still disconnected (%d missed PINGs)", self._failures)
                continue

            self._failures = 0
            resp = self._serial.send_command("PING")
            if resp is None:
                self._failures += 1
                LOG.warning("[heartbeat] PING failed (%d/%d)", self._failures, self._max_failures)
                if self._failures >= self._max_failures:
                    LOG.error("[heartbeat] PING failures ≥ %d — connection lost", self._max_failures)
            elif resp and "ERR" in resp.upper():
                LOG.warning("[heartbeat] PING rejected: %s", resp)


# ═══════════════════════════════════════════════════════════════════════
# Command-Line Interface
# ═══════════════════════════════════════════════════════════════════════

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Agent Status Relay — monitor OpenCode agent state and drive ESP32 LED controller.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/agent_relay.py --dry-run                          # test mode (no serial)
  python scripts/agent_relay.py --port COM3                        # connect to ESP32 on COM3
  python scripts/agent_relay.py --port COM3 --heartbeat-interval 2 # 2s heartbeat
  python scripts/agent_relay.py --list-ports                       # show available serial ports
  echo "EXECUTING" | python scripts/agent_relay.py --dry-run       # pipe state commands
        """,
    )

    p.add_argument(
        "--port", "-p",
        default=None,
        help="Serial port for ESP32 (e.g., COM3, /dev/ttyUSB0). Auto-detect if omitted.",
    )
    p.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Dry-run mode: log what would be sent, no serial connection.",
    )
    p.add_argument(
        "--baud", "-b",
        type=int,
        default=115200,
        help="Serial baud rate (default: 115200).",
    )
    p.add_argument(
        "--heartbeat-interval",
        type=float,
        default=1.5,
        help="Heartbeat PING interval in seconds (default: 1.5, range: 0.5-5.0).",
    )
    p.add_argument(
        "--auto-detect",
        action="store_true",
        help="Enable auto-detection of agent state from raw OpenCode output text.",
    )
    p.add_argument(
        "--list-ports",
        action="store_true",
        help="List available serial ports and exit.",
    )
    p.add_argument(
        "--verbose", "-v",
        action="count",
        default=0,
        help="Increase log verbosity (-v for DEBUG, -vv for full detail).",
    )
    return p


def _setup_logging(verbosity: int):
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity == 2:
        level = logging.DEBUG
    elif verbosity >= 3:
        level = logging.DEBUG
        # also show pyserial debug
        logging.getLogger("serial").setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    LOG.setLevel(level)
    LOG.addHandler(handler)


def _state_change_handler(
    serial_mgr: SerialManager,
    is_dry_run: bool,
    old: AgentState,
    new: AgentState,
    ts: datetime,
):
    """Callback: send serial command when state changes."""
    cmd = new.serial_command
    if cmd is None:
        LOG.debug("[state→serial] %s has no serial command (derived state)", new.name)
        return

    LOG.info("[state->serial] sending '%s' for state %s", cmd, new.name)
    resp = serial_mgr.send_command(cmd)
    if resp is None:
        LOG.error("[state->serial] command '%s' FAILED (no response)", cmd)
    elif "ERR" in resp.upper():
        LOG.error("[state->serial] command '%s' rejected: %s", cmd, resp)
    else:
        LOG.info("[state->serial] command '%s' -> %s", cmd, resp)


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    args = _build_argparser().parse_args()
    _setup_logging(args.verbose)

    # ── list-ports shortcut ───────────────────────────────────────
    if args.list_ports:
        ports = SerialManager.list_ports()
        if ports:
            print("Available serial ports:")
            for p in ports:
                print(f"  {p}")
        else:
            print("No serial ports found.")
        return

    # ── resolve port ──────────────────────────────────────────────
    port = args.port
    if not args.dry_run and not port:
        port = SerialManager.auto_detect_esp32()
        if port:
            LOG.info("[auto-detect] using ESP32 port: %s", port)
        else:
            LOG.error(
                "[auto-detect] no ESP32 port found. Specify --port or check USB connection."
            )
            LOG.info("[auto-detect] available ports: %s", SerialManager.list_ports())
            sys.exit(1)

    if not args.dry_run and not port:
        LOG.error("--port is required (or use --dry-run for testing)")
        sys.exit(1)

    # ── serial manager ────────────────────────────────────────────
    serial_mgr = SerialManager(port=port or "dry-run", baud=args.baud, dry_run=args.dry_run)
    if not serial_mgr.open():
        if not args.dry_run:
            LOG.error("Failed to open serial port. Exiting.")
            sys.exit(1)

    # ── agent monitor ─────────────────────────────────────────────
    monitor = AgentMonitor(auto_detect=args.auto_detect)

    # Wire state changes → serial commands
    monitor.on_state_change(
        lambda old, new, ts: _state_change_handler(serial_mgr, args.dry_run, old, new, ts)
    )

    # ── heartbeat loop ────────────────────────────────────────────
    heartbeat = HeartbeatLoop(serial_mgr, interval=args.heartbeat_interval)
    heartbeat.start()

    # ── graceful shutdown ─────────────────────────────────────────
    stop_event = threading.Event()

    def _shutdown(sig, frame):
        LOG.info("[shutdown] signal %s received", sig)
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # ── header ────────────────────────────────────────────────────
    LOG.info("=" *  60)
    LOG.info("Agent Status Relay — OpenCode → ESP32 LED Controller")
    LOG.info("  Port:          %s", port or "(dry-run)")
    LOG.info("  Baud:          %d", args.baud)
    LOG.info("  Heartbeat:     %.1fs", args.heartbeat_interval)
    LOG.info("  Auto-detect:   %s", "ON" if args.auto_detect else "OFF")
    LOG.info("  Dry-run:       %s", "YES" if args.dry_run else "NO")
    LOG.info("  Initial state: %s (priority=%d)", monitor.state.name, monitor.state.priority)
    LOG.info("=" *  60)
    LOG.info("Send state commands via stdin: IDLE | EXECUTING | QUESTION | ERROR | RESET")
    LOG.info("")

    # ── stdin event loop (blocking) ───────────────────────────────
    try:
        monitor.run_stdin_loop(stop_event)
    except KeyboardInterrupt:
        pass
    finally:
        LOG.info("[shutdown] cleaning up...")
        heartbeat.stop()
        serial_mgr.close()
        LOG.info("[shutdown] done.")


if __name__ == "__main__":
    main()
