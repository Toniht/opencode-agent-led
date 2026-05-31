# Serial Protocol Contract: Agent Status LED Indicator

**Feature**: 001-agent-status-led | **Phase**: 1 | **Date**: 2026-05-31

## Overview

This document defines the USB serial communication contract between the OpenCode PC host and the ESP32-S3 LED controller firmware. The protocol is designed for simplicity, debuggability, and reliability over 115200 baud serial.

---

## Physical Layer

| Parameter | Value |
|-----------|-------|
| Interface | USB Serial (CH343P UART-to-USB bridge or native USB CDC) |
| Baud Rate | 115200 |
| Data Bits | 8 |
| Parity | None |
| Stop Bits | 1 |
| Flow Control | None |
| Voltage | 3.3V TTL (internal to ESP32 dev board) |

---

## Framing

- **Delimiter**: Newline character `\n` (ASCII 0x0A)
- **Acceptable line endings**: `\n` (Unix), `\r\n` (Windows), or `\r` (legacy Mac) — firmware strips all trailing whitespace.
- **Maximum line length**: 32 characters (commands are short keywords). Lines exceeding 32 chars are truncated and counted as invalid.
- **Encoding**: ASCII (7-bit). No UTF-8, no binary payloads.
- **Case Sensitivity**: Commands are case-sensitive. `IDLE` is valid; `idle` or `Idle` is treated as unknown.

---

## Command Format (PC → ESP32)

```
<COMMAND>\n
```

Commands are single-word keywords with no arguments. Whitespace before/after is stripped.

### Command Reference

| Command | Priority | Effect | Response |
|---------|----------|--------|----------|
| `IDLE` | 3 | Set state to IDLE (green steady) | `OK` |
| `EXEC` | 2 | Set state to EXECUTING (yellow steady) | `OK` |
| `QUESTION` | 1 | Set state to QUESTIONING (green+yellow 1Hz blink) | `OK` |
| `ERROR` | 0 | Set state to ERROR (red steady), increment error counter | `OK` (or `ERR LOCKED` if already locked) |
| `RESET` | — | Reset error counter, clear lock, return to IDLE | `OK` |
| `PING` | — | Heartbeat — reset activity timeout | `OK` |
| `SILENT` | — | Turn off all LEDs (override until next command) | `OK` |
| `STATUS` | — | Query current operational state | State name (see below) |

### Priority Rules

When a command is received, the state machine applies priority resolution:
- `ERROR` (0) > `QUESTION` (1) > `EXECUTING` (2) > `IDLE` (3)
- Lower-priority commands are accepted but only take effect when no higher-priority state is active.
- `RESET`, `PING`, `SILENT`, `STATUS` are priority-independent — always processed immediately.

### Examples

```
→ IDLE
← OK
   [Green LED steady on]

→ EXEC
← OK
   [Yellow LED steady on]

→ QUESTION
← OK
   [Green + Yellow LEDs blink at 1Hz]

→ ERROR
← OK
   [Red LED steady on]

→ ERROR
← OK
   [Red LED steady on, errorCount=2]

→ ERROR
← ERR LOCKED
   [Red LED steady on, errorLocked=true]

→ RESET
← OK
   [Green LED steady on, errorCount=0]

→ PING
← OK
   [No LED change, heartbeat timer reset]

→ SILENT
← OK
   [All LEDs off, underlying state preserved]

→ EXEC
← OK
   [Yellow LED steady on — SILENT override released]

→ STATUS
← EXECUTING
   [Reports current state]

→ FOO
← ERR UNKNOWN
   [invalidFrames incremented]
```

---

## Response Format (ESP32 → PC)

```
OK\n
ERR <reason>\n
<STATE NAME>\n
```

- `OK`: Command accepted and executed.
- `ERR <reason>`: Command rejected or error condition. Possible reasons:
  - `UNKNOWN` — unrecognized command
  - `LOCKED` — ERROR state already locked (≥3 errors)
  - `TIMEOUT` — internal error
- `<STATE NAME>`: Response to `STATUS` query. One of: `IDLE`, `EXECUTING`, `QUESTIONING`, `ERROR`, `DISCONNECTED`, `SILENT`.

---

## Heartbeat Protocol

- **Interval**: PC should send `PING` at 1-2 second intervals (recommended: 1s).
- **Timeout**: Firmware triggers DISCONNECTED state if no valid serial data received for 5000ms.
- **Recovery**: DISCONNECTED auto-resolves on next valid command (no explicit reconnect needed).
- **Note**: Any valid command (not just `PING`) resets the heartbeat timer. `PING` is special only in that it has no LED state effect.

---

## Error Handling

### Invalid Frames

| Condition | Action |
|-----------|--------|
| Unknown command | Respond `ERR UNKNOWN`, increment `invalidFrames` |
| Line exceeds 32 chars | Truncate, respond `ERR UNKNOWN`, increment `invalidFrames` |
| Empty line (just `\n`) | Ignored silently, no counter increment |
| 10 consecutive invalid frames | Trigger DISCONNECTED state, respond `ERR TIMEOUT` |

### Error Counter

| Event | Action |
|-------|--------|
| `ERROR` command received | Increment counter |
| Counter reaches 3 | Set `errorLocked=true`, respond `ERR LOCKED` to further `ERROR` commands |
| `RESET` command received | Clear counter, clear lock, return to IDLE |
| Non-ERROR command received | Counter unchanged (errors are "sticky") |
| Power-on / reboot | Counter = 0 |

### Connection Loss

| Event | Action |
|-------|--------|
| No serial data for 5s | Enter DISCONNECTED (red fast blink 2Hz) |
| Serial data resumes | Exit DISCONNECTED, restore previous state |
| 10 invalid frames received (even with data flowing) | Enter DISCONNECTED |

---

## Timing Constraints

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Command-to-LED latency | < 500ms | `loop()` processes serial in < 1ms at 115200 baud |
| Heartbeat interval (PC side) | 1-2 seconds | Recommended to stay well under 5s timeout |
| Heartbeat timeout (ESP32 side) | 5000ms | Configurable via `heartbeatTimeout` constant |
| Blink period (1Hz) | 1000ms (500ms on/off) | 50% duty cycle, visually distinct |
| Blink period (2Hz) | 500ms (250ms on/off) | 50% duty cycle, noticeably faster |
| Error lock threshold | 3 consecutive ERROR commands | Per FR-006 |
| Invalid frame threshold | 10 consecutive | Per FR-011 |

---

## State Diagram

```
                    ┌──────────┐
          ┌────────>│   IDLE   │<────────┐
          │         │ Green ON  │         │
          │         └─────┬─────┘         │
          │               │               │
       RESET          EXEC│            RESET
          │               v               │
          │         ┌──────────┐         │
          │         │EXECUTING │         │
          │         │Yellow ON │         │
          │         └─────┬─────┘         │
          │               │               │
          │          QUESTION             │
          │               v               │
          │         ┌──────────┐         │
          │         │QUESTION  │         │
          │         │G+Y Blink │         │
          │         └─────┬─────┘         │
          │               │               │
          │           ERROR               │
          │               v               │
          │         ┌──────────┐         │
          └─────────│  ERROR   │─────────┘
                    │ Red ON   │
                    └──────────┘

    [Any state] ──(no serial 5s)──> DISCONNECTED (Red 2Hz blink)
    DISCONNECTED ──(serial resumes)──> [restore previous state]
```

---

## Implementation Notes

1. **Buffer size**: Serial RX buffer should be at least 64 bytes (ESP32 default: 256 bytes). At 115200 baud, 256 bytes fill in ~22ms — `loop()` iteration must be faster than this.

2. **Non-blocking**: `loop()` MUST NOT call `delay()`. All timing uses `millis()`. Serial reading uses `Serial.available()` in a `while` loop.

3. **Whitespace handling**: `trim()` the input line before matching. Accept `\r\n`, `\n`, or `\r` as line endings.

4. **String comparison**: Use `strcmp()` or `strncmp()` (not `String::equals()`) for RAM efficiency on ESP32. Command tokens are short C-string literals.

5. **Response format**: Always emit a response line. PC host can use this for acknowledgment and error detection.

6. **Boot behavior**: On power-up, enter IDLE state (green LED on). Send `READY\n` once (optional — signals firmware is alive before first PING).
