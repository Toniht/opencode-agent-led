# Data Model: Agent Status LED Indicator

**Feature**: 001-agent-status-led | **Phase**: 1 | **Date**: 2026-05-31

## Entity Overview

The firmware is a stateless command processor. There is no persistent storage — all data is transient in RAM. The following entities define the data structures used in firmware logic.

---

## Entity: AgentState (Enum)

The current operational state of the monitored OpenCode agent.

| Value | Priority | Meaning | LED Pattern |
|-------|----------|---------|-------------|
| `ERROR` | 0 (highest) | Agent encountered an error | Red steady on |
| `QUESTION` | 1 | Agent is asking user a question | Green + Yellow 1Hz sync blink |
| `EXECUTING` | 2 | Agent is executing a task | Yellow steady on |
| `IDLE` | 3 | Agent is idle, ready for input | Green steady on |
| `DISCONNECTED` | 4 (lowest) | USB serial heartbeat lost | Red 2Hz fast blink |
| `SILENT` | Special | LED override — all off | All LEDs off |

**State Transition Rules**:
- `DISCONNECTED` is a **derived state** — triggered automatically by heartbeat timeout, not by serial command. It resolves to the previous state when serial activity resumes.
- `ERROR` with counter ≥ 3 → `ERROR_LOCKED` (red persists until explicit `RESET`).
- Priority resolution: When multiple state signals arrive simultaneously, the highest priority wins. `DISCONNECTED` is the exception — it only activates when no other valid state has been received within the 5s window.
- `SILENT` is a transient override — it does not change the underlying state. When `RESET` is received, the underlying state is restored.

### C++ Representation

```cpp
enum class AgentState : uint8_t {
    ERROR = 0,
    QUESTION = 1,
    EXECUTING = 2,
    IDLE = 3,
    DISCONNECTED = 4,
    SILENT = 5
};

// Priority array: lower index = higher priority
// SILENT excluded — it's an overlay, not a priority level
```

---

## Entity: LEDSignal

Physical output configuration for the three LEDs.

| Field | Type | Description |
|-------|------|-------------|
| `greenMode` | `LedMode` | Green LED output mode |
| `yellowMode` | `LedMode` | Yellow LED output mode |
| `redMode` | `LedMode` | Red LED output mode |

### LedMode (Enum)

| Value | Meaning | Implementation |
|-------|---------|----------------|
| `OFF` | LED is off | `digitalWrite(pin, LOW)` (active-high) |
| `ON` | LED is steady on | `digitalWrite(pin, HIGH)` |
| `SLOW_BLINK` | 1Hz blink (500ms on, 500ms off) | `millis()` toggle at 500ms interval |
| `FAST_BLINK` | 2Hz blink (250ms on, 250ms off) | `millis()` toggle at 250ms interval |

### C++ Representation

```cpp
enum class LedMode : uint8_t {
    OFF = 0,
    ON = 1,
    SLOW_BLINK = 2,   // 1Hz (500ms interval)
    FAST_BLINK = 3    // 2Hz (250ms interval)
};

struct LedSignal {
    LedMode green;
    LedMode yellow;
    LedMode red;
};

// Mapping: AgentState → LedSignal
// ERROR        → {OFF, OFF, ON}
// QUESTION     → {SLOW_BLINK, SLOW_BLINK, OFF}
// EXECUTING    → {OFF, ON, OFF}
// IDLE         → {ON, OFF, OFF}
// DISCONNECTED → {OFF, OFF, FAST_BLINK}
// SILENT       → {OFF, OFF, OFF}
```

### Blink State Tracking (Runtime)

```cpp
struct LedBlink {
    bool state;                    // Current output: HIGH or LOW
    unsigned long previousMillis;  // Last toggle timestamp
    unsigned long interval;        // 0 = steady, >0 = blink interval in ms
};

// Runtime array: blinkState[0]=green, [1]=yellow, [2]=red
LedBlink blinkState[3];
```

---

## Entity: StatusCommand

A parsed serial command from the PC.

| Field | Type | Description |
|-------|------|-------------|
| `type` | `CommandType` | Command keyword |
| `raw` | `const char*` | Raw line for error reporting |

### CommandType (Enum)

| Value | Serial Token | Description |
|-------|-------------|-------------|
| `CMD_IDLE` | `"IDLE"` | Set state to Idle |
| `CMD_EXEC` | `"EXEC"` | Set state to Executing |
| `CMD_QUESTION` | `"QUESTION"` | Set state to Questioning |
| `CMD_ERROR` | `"ERROR"` | Set state to Error (increment counter) |
| `CMD_RESET` | `"RESET"` | Reset error counter, restore to Idle |
| `CMD_PING` | `"PING"` | Heartbeat — resets timeout |
| `CMD_SILENT` | `"SILENT"` | Enable silent mode (all LEDs off) |
| `CMD_STATUS` | `"STATUS"` | Query current state (respond with state name) |
| `CMD_UNKNOWN` | — | Unrecognized command |

### C++ Representation

```cpp
enum class CommandType : uint8_t {
    CMD_IDLE,
    CMD_EXEC,
    CMD_QUESTION,
    CMD_ERROR,
    CMD_RESET,
    CMD_PING,
    CMD_SILENT,
    CMD_STATUS,
    CMD_UNKNOWN
};

struct StatusCommand {
    CommandType type;
    // No payload needed for current command set
};
```

---

## Entity: SystemRuntime

Global system state tracked at runtime.

| Field | Type | Initial Value | Description |
|-------|------|---------------|-------------|
| `currentState` | `AgentState` | `IDLE` | Active agent state (with priority resolution) |
| `underlyingState` | `AgentState` | `IDLE` | State beneath SILENT overlay |
| `errorCount` | `uint8_t` | `0` | Consecutive error counter (caps at 3) |
| `errorLocked` | `bool` | `false` | True when errorCount ≥ 3 |
| `lastActivity` | `unsigned long` | `millis()` on boot | Timestamp of last valid serial input |
| `invalidFrames` | `uint8_t` | `0` | Consecutive invalid frame counter (caps at 10) |
| `silentMode` | `bool` | `false` | SILENT override active |
| `heartbeatTimeout` | `unsigned long` | `5000` | Configurable timeout in ms |

### C++ Representation

```cpp
struct SystemRuntime {
    AgentState currentState = AgentState::IDLE;
    AgentState underlyingState = AgentState::IDLE;
    uint8_t errorCount = 0;
    bool errorLocked = false;
    unsigned long lastActivity = 0;
    uint8_t invalidFrames = 0;
    bool silentMode = false;
    const unsigned long heartbeatTimeout = 5000;
};

// Singleton instance
SystemRuntime sys;
```

---

## State-to-Signal Mapping

```
┌──────────────┬──────────┬──────────┬──────────┐
│ AgentState   │ Green    │ Yellow   │ Red      │
├──────────────┼──────────┼──────────┼──────────┤
│ IDLE         │ ON       │ OFF      │ OFF      │
│ EXECUTING    │ OFF      │ ON       │ OFF      │
│ QUESTION     │ SLOW_BLK │ SLOW_BLK │ OFF      │
│ ERROR        │ OFF      │ OFF      │ ON       │
│ DISCONNECTED │ OFF      │ OFF      │ FAST_BLK │
│ SILENT       │ OFF      │ OFF      │ OFF      │
└──────────────┴──────────┴──────────┴──────────┘
```

---

## Validation Rules

| Rule | Enforcement |
|------|-------------|
| `errorCount` never exceeds 3 | Clamped in `processCommand()` |
| `errorLocked` → only `RESET` clears it | Guard in state transition |
| `invalidFrames` ≥ 10 → `DISCONNECTED` | Checked after each invalid parse |
| `lastActivity` timeout → `DISCONNECTED` | Checked in `loop()` every iteration |
| `SILENT` does not change `underlyingState` | `setState()` skips underlying update when silent |
| Priority ordering always enforced | `setState()` uses priority comparison |
