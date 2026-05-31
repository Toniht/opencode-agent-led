# Tasks: Agent Status LED Indicator

**Input**: Design documents from `/specs/001-agent-status-led/`

**Prerequisites**: plan.md (✅), spec.md (✅), research.md (✅), data-model.md (✅), contracts/serial-protocol.md (✅), quickstart.md (✅)

**Tests**: Not explicitly requested — integration verification via esp32-devops MCP tools instead.

**Organization**: Tasks ordered per user's explicit instruction: agent monitor → LED firmware → integration. Each task tagged with relevant user story where applicable.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task serves (US1=Executing, US2=Question, US3=Error, US4=Connection)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create PlatformIO project at repo root and configure build system

- [ ] T001 Create PlatformIO project at repo root — run `esp32_create_project(name="agent-status-led", projectPath=".", board="esp32-s3-devkitc-1", template="bare")`
- [ ] T002 [P] Write platformio.ini with ESP32-S3-R16N8 config: qio_opi memory type, 16MB flash, OPI PSRAM, USB CDC flags (`ARDUINO_USB_MODE=1`, `ARDUINO_USB_CDC_ON_BOOT=1`), monitor_filters=esp32_exception_decoder, upload_protocol=esp-builtin — reference light-test `D:\Code\opencode-light\light-test\esp32-traffic-light\platformio.ini`
- [ ] T003 [P] Install Python dependency for PC relay: `pip install pyserial` in scripts/requirements.txt
- [ ] T004 Validate project structure with `esp32_validate_project`

**Checkpoint**: PlatformIO project ready, builds without errors

---

## Phase 2: PC-side Agent Status Monitor (agent_relay.py)

**Purpose**: Python script that reads OpenCode agent session events, maps them to LED states, and manages the serial connection. This is the "source of truth" for agent state.

**Goal**: Agent relay script that can independently detect OpenCode agent states (Idle, Executing, Questioning, Error) from session events and log them — without ESP32 connected yet.

**Independent Test**: Run `scripts/agent_relay.py --dry-run`, trigger agent actions in OpenCode, verify correct state transitions are printed to stdout.

- [ ] T005 [P] [US1] [US2] [US3] Create `scripts/agent_relay.py` — define AgentState enum (IDLE, EXECUTING, QUESTIONING, ERROR, DISCONNECTED) with priority values matching data-model.md
- [ ] T006 [P] [US1] Implement OpenCode session event reader in `scripts/agent_relay.py` — detect agent executing/idle states via OpenCode session API or hooks, log state transitions with timestamps
- [ ] T007 [US2] Implement question detection logic in `scripts/agent_relay.py` — detect when agent prompts user for input (vs idle waiting), emit QUESTIONING state
- [ ] T008 [US3] Implement error detection logic in `scripts/agent_relay.py` — detect tool call failures, exceptions, or consecutive errors; emit ERROR state with counter
- [ ] T009 Implement state priority resolver in `scripts/agent_relay.py` — ensure ERROR > QUESTION > EXECUTING > IDLE priority ordering per FR-008
- [ ] T010 [P] [US4] Implement serial port manager in `scripts/agent_relay.py` — open/close COM port, send newline-delimited commands per contracts/serial-protocol.md, auto-detect ESP32 port
- [ ] T011 [US4] Implement heartbeat loop in `scripts/agent_relay.py` — send `PING\n` every 1-2 seconds on a background thread, log heartbeat failures
- [ ] T012 Add CLI arguments to `scripts/agent_relay.py` — `--port COM3`, `--dry-run` (no serial, print only), `--baud 115200`, `--heartbeat-interval 1`

**Checkpoint**: `python scripts/agent_relay.py --dry-run` correctly logs state transitions when OpenCode agent is active

---

## Phase 3: ESP32 Firmware — LED Controller & Serial Protocol

**Purpose**: ESP32 firmware that controls 3 LEDs (G=4, Y=5, R=6) with non-blocking state machine and serial command parser. Patterns reference light-test `D:\Code\opencode-light\light-test\esp32-traffic-light\src\main.cpp`.

**Goal**: Firmware that can independently drive all 5 LED states (Idle, Executing, Questioning, Error, Disconnected) and respond to all 8 serial commands.

**Independent Test**: Flash firmware, open serial monitor at 115200, send `IDLE`/`EXEC`/`QUESTION`/`ERROR`/`PING` commands, verify correct LED patterns per spec acceptance scenarios.

### Phase 3a: Pin & LED Primitives

- [ ] T013 [P] Create `src/pin_config.h` — define `PIN_GREEN 4`, `PIN_YELLOW 5`, `PIN_RED 6`, `LED_ON HIGH`, `LED_OFF LOW` (active-high pattern from light-test); add `gpio_hold_dis()` release calls matching light-test lines 18-21
- [ ] T014 [P] [US1] [US2] [US3] [US4] Create `src/led_controller.h` — declare `LedMode` enum (OFF, ON, SLOW_BLINK=1Hz, FAST_BLINK=2Hz), `LedBlink` struct (state, previousMillis, interval) per data-model.md, `AgentState` enum, `LedSignal` struct, and function signatures: `led_init()`, `led_setState(AgentState)`, `led_tick()`
- [ ] T015 [US1] [US2] [US3] [US4] Create `src/led_controller.cpp` — implement `led_init()`: `pinMode()` for 3 GPIOs + `digitalWrite(LOW)` all-off pattern from light-test lines 23-30. Implement `led_setState()`: switch on AgentState → set each LED's LedMode per state-to-signal mapping (IDLE→green ON, EXECUTING→yellow ON, QUESTION→green+yellow SLOW_BLINK, ERROR→red ON, DISCONNECTED→red FAST_BLINK, SILENT→all OFF)
- [ ] T016 [US2] [US4] Implement `led_tick()` in `src/led_controller.cpp` — non-blocking `millis()`-based per-LED blink update: for each LED with interval>0, toggle `state` when `(now - previousMillis) >= interval`. SLOW_BLINK=500ms, FAST_BLINK=250ms. Never use `delay()`.
- [ ] T017 Verify LED timing: SLOW_BLINK completes one full on-off cycle in exactly 1000ms, FAST_BLINK in 500ms — use `Serial.println(millis())` debug output to validate

### Phase 3b: Serial Protocol Parser

- [ ] T018 [P] Create `src/serial_protocol.h` — declare `CommandType` enum (CMD_IDLE, CMD_EXEC, CMD_QUESTION, CMD_ERROR, CMD_RESET, CMD_PING, CMD_SILENT, CMD_STATUS, CMD_UNKNOWN) and function signatures: `serial_init()`, `serial_process()`, `serial_respond_ok()`, `serial_respond_err()`
- [ ] T019 Create `src/serial_protocol.cpp` — implement `serial_init()`: `Serial.begin(115200)` with `delay(1500)` for USB CDC stability (pattern from light-test line 16). Implement `serial_process()`: read from `Serial.available()` into line buffer, match against command tokens via `strcmp()`, return `StatusCommand` struct per contracts/serial-protocol.md command reference
- [ ] T020 [P] Implement command matching in `src/serial_protocol.cpp` — map all 8 command keywords to CommandType: "IDLE"→CMD_IDLE, "EXEC"→CMD_EXEC, "QUESTION"→CMD_QUESTION, "ERROR"→CMD_ERROR, "RESET"→CMD_RESET, "PING"→CMD_PING, "SILENT"→CMD_SILENT, "STATUS"→CMD_STATUS. Unknown commands → CMD_UNKNOWN + "ERR UNKNOWN\n" response.
- [ ] T021 [FR-011] Implement frame validation in `src/serial_protocol.cpp` — reject lines >32 chars, count consecutive invalid frames (empty lines ignored per protocol). At 10 invalid → treat as DISCONNECTED trigger.
- [ ] T022 [P] Implement response helpers in `src/serial_protocol.cpp` — `serial_respond_ok()` prints "OK\n", `serial_respond_err(reason)` prints "ERR <reason>\n". Use `Serial.print()` not `String` class.

### Phase 3c: Main Integration

- [ ] T023 Create `src/main.cpp` — declare global `SystemRuntime sys` struct (currentState, underlyingState, errorCount, errorLocked, lastActivity, invalidFrames, silentMode, heartbeatTimeout=5000) per data-model.md lines 170-183
- [ ] T024 Implement `setup()` in `src/main.cpp` — call `serial_init()` and `led_init()`, set `lastActivity = millis()`, print startup banner with pin mapping (pattern from light-test lines 32-33), set initial state to IDLE (green LED on per FR-001)
- [ ] T025 [US1] [US2] [US3] Implement `loop()` command dispatch in `src/main.cpp` — call `serial_process()`, then switch on CommandType: IDLE/EXEC/QUESTION/ERROR → `setState()` with priority check; RESET → clear error counter + return to IDLE; PING → reset `lastActivity`; SILENT → toggle `silentMode`; STATUS → respond with current state name
- [ ] T026 [US3] Implement error counter logic in `src/main.cpp` — on CMD_ERROR: increment `sys.errorCount`, if ≥3 set `sys.errorLocked=true` and respond "ERR LOCKED". RESET clears counter and lock per FR-006.
- [ ] T027 [US4] Implement heartbeat watchdog in `src/main.cpp` — in `loop()`, check `millis() - sys.lastActivity > sys.heartbeatTimeout` → enter DISCONNECTED state (red 2Hz blink). On any valid serial input → restore previous state per FR-007, SC-005.
- [ ] T028 [FR-008] Implement priority state machine in `src/main.cpp` — function `setState(AgentState newState)`: if newState priority < currentState priority, accept; otherwise reject. Priority: ERROR(0) > QUESTION(1) > EXECUTING(2) > IDLE(3). DISCONNECTED auto-triggered. SILENT overlay preserves underlying state.
- [ ] T029 Call `led_tick()` once per `loop()` iteration in `src/main.cpp` — ensures non-blocking blink updates at every cycle. Verify `loop()` execution time < 1ms (no delay calls, only serial poll + millis() check + digitalWrite).

**Checkpoint**: Firmware flashed and verified — all 8 serial commands produce correct LED patterns. Send `IDLE`→green ON, `EXEC`→yellow ON, `QUESTION`→G+Y 1Hz blink, `ERROR`→red ON, wait 6s→red 2Hz blink (disconnected), `PING`→recovery.

---

## Phase 4: Integration — Agent State Controls LEDs

**Purpose**: Connect the PC-side agent_relay.py to the ESP32 firmware via USB serial. Agent state changes in OpenCode automatically drive LED patterns on the ESP32.

**Goal**: End-to-end system where OpenCode agent actions cause correct LED indications in real-time.

**Independent Test**: Start `agent_relay.py` with ESP32 connected, trigger agent execution in OpenCode, observe yellow LED within 500ms.

- [ ] T030 Connect `scripts/agent_relay.py` to ESP32 — configure `--port` argument, open serial connection at 115200, verify `READY\n` response from firmware on connection
- [ ] T031 [US1] Wire EXECUTING/IDLE transitions in `scripts/agent_relay.py` — on agent start executing → send `EXEC\n`, on agent return to idle → send `IDLE\n`. Verify yellow→green LED transitions per US1 acceptance scenarios.
- [ ] T032 [US2] Wire QUESTIONING transitions in `scripts/agent_relay.py` — on agent prompt user → send `QUESTION\n`, on user answer → send previous state command. Verify G+Y 1Hz sync blink per US2 acceptance scenarios.
- [ ] T033 [US3] Wire ERROR transitions in `scripts/agent_relay.py` — on agent tool failure/exception → send `ERROR\n`, track consecutive errors, on 3rd error verify ESP32 responds `ERR LOCKED`. RESET via manual `RESET\n` command.
- [ ] T034 [US4] Verify heartbeat + disconnect recovery — run agent_relay.py for 2+ minutes, confirm PING every 1s, unplug ESP32 USB → verify relay logs connection loss within 6s. Replug → verify state recovery.
- [ ] T035 End-to-end latency test — measure time from OpenCode agent state change to LED change, verify <500ms per SC-002. Log all transitions with PC timestamp vs ESP32 response timestamp.

**Checkpoint**: Full system operational — agent actions in OpenCode drive correct LED patterns on ESP32 without manual intervention

---

## Phase 5: Polish & Validation

**Purpose**: Build verification, hardware validation, and documentation

- [ ] T036 [P] Verify build excludes WiFi/Bluetooth — run `esp32_build`, inspect build log for `libwifi.a`, `libbt.a`, `libbtdm_app.a` — confirm NONE linked per Hardware Constraints §4
- [ ] T037 [P] Run firmware tests via `esp32_test_firmware` — verify boot, heartbeat stability, memory integrity
- [ ] T038 Flash firmware via `esp32_flash` or `esp32_full_cycle` — verify green LED on after flash (default IDLE state per SC acceptance scenario 3)
- [ ] T039 Run quickstart.md end-to-end validation — execute all 9 steps, verify each expected output (STATUS→IDLE, EXEC→yellow, QUESTION→blink, ERROR→red, RESET→green, PING→OK, SILENT→all off, FOO→ERR UNKNOWN, 6s silence→red fast blink)
- [ ] T040 [P] Verify serial error rate < 0.01% per SC-006 — run 1000 continuous STATE/STATUS command cycles, count any mismatches or dropped frames
- [ ] T041 Run `esp32_validate_deployment` final check — confirm all pre-deployment gates pass
- [ ] T042 [P] Update AGENTS.md plan reference if changed during implementation

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ─────────────────────────────────────────────────────────────┐
     │                                                                        │
     ├──► Phase 2 (PC Agent Monitor) ── independent of firmware ──────────┐  │
     │         │                                                           │  │
     │         └──► Phase 4 (Integration) ◄── depends on Phase 2 + 3 ──┐  │  │
     │                                                                   │  │  │
     ├──► Phase 3 (ESP32 Firmware) ── independent of PC script ─────│───┘  │  │
     │         │                                                      │      │  │
     │         │   Phase 3a (Pin + LED) ──► 3b (Serial) ──► 3c (Main)│      │  │
     │         │                                                      │      │  │
     │         └──────────────────────────────────────────────────────┘      │  │
     │                                                                       │  │
     └──► Phase 5 (Polish) ◄── depends on Phase 4 ──────────────────────────┘  │
                                                                                │
     ALL phases depend on Phase 1 (Setup) completion                            │
```

### Within Each Phase

**Phase 2 (PC Agent Monitor)**:
- T005 (AgentState enum) → T006, T007, T008 can all run in parallel
- T010, T011 (serial manager, heartbeat) are independent of T007, T008
- T012 (CLI args) depends on T005, T010

**Phase 3 (ESP32 Firmware)**:
- Phase 3a: T013 (pin_config.h) + T014 (led_controller.h) can run in parallel → T015, T016 depend on both headers
- Phase 3b: T018 (serial_protocol.h) → T019, T020, T021, T022 can run in parallel after header
- Phase 3c: T023 → T024 → T025, T026, T027, T028 all depend on T023 + T024 → T029 depends on T016

### User Story Mapping

| User Story | Priority | Phase | Key Tasks |
|---|---|---|---|
| US1 - Agent Executing Indicator | P1 | Phase 2 (T006) + Phase 3a (T014, T015) + Phase 4 (T031) | IDLE ↔ EXECUTING transitions |
| US2 - Agent Question Indicator | P2 | Phase 2 (T007) + Phase 3a (T014, T015, T016) + Phase 4 (T032) | G+Y 1Hz sync blink |
| US3 - Agent Error Indicator | P1 | Phase 2 (T008) + Phase 3a (T014, T015) + Phase 3c (T026) + Phase 4 (T033) | Red LED + error counter lock |
| US4 - Connection Loss Indicator | P2 | Phase 2 (T010, T011) + Phase 3a (T014, T015, T016) + Phase 3c (T027) + Phase 4 (T034) | Red 2Hz fast blink on timeout |

---

## Parallel Execution Examples

### Phase 3a: LED Controller (launch simultaneously)

```bash
# Create headers in parallel
Task: "Create src/pin_config.h — define pins, LED_ON/OFF, gpio_hold_dis"
Task: "Create src/led_controller.h — declare LedMode, LedBlink, AgentState, function signatures"

# After headers: implement in parallel
Task: "Create src/led_controller.cpp — led_init() + led_setState()"
Task: "Implement led_tick() — non-blocking millis() blink"
```

### Phase 3b: Serial Protocol (launch simultaneously)

```bash
# Create header
Task: "Create src/serial_protocol.h — declare CommandType, function signatures"

# After header: implement in parallel
Task: "Create src/serial_protocol.cpp — serial_init() + serial_process()"
Task: "Implement command matching — all 8 commands + ERR UNKNOWN"
Task: "Implement frame validation — 32 char limit, invalid frame counter"
Task: "Implement response helpers — serial_respond_ok(), serial_respond_err()"
```

### Phase 4: Integration (after Phase 2 + Phase 3 complete)

```bash
# Independent verification tasks
Task: "Wire EXECUTING/IDLE transitions (US1)"
Task: "Wire QUESTIONING transitions (US2)"
Task: "Wire ERROR transitions (US3)"
# Then
Task: "Verify heartbeat + disconnect recovery (US4)"
Task: "End-to-end latency test"
```

---

## Implementation Strategy

### MVP First (User Story 1 only — Agent Executing)

1. Complete **Phase 1: Setup** (T001-T004) — PlatformIO project
2. Complete **Phase 3a** (T013-T017) — LED controller with IDLE/EXECUTING states only
3. Complete **Phase 3b** (T018-T022) — serial protocol with IDLE/EXEC/PING/STATUS commands
4. Complete **Phase 3c** partial (T023, T024, T025) — main.cpp with IDLE/EXECUTING dispatch
5. **Flash and verify**: Green LED on boot, send `EXEC` → yellow LED, send `IDLE` → green LED
6. **STOP**: MVP delivers the core "agent working" visual signal

### Full Feature

After MVP validates hardware and serial communication:
1. **Phase 2**: Build agent_relay.py to automate state detection
2. **Remaining Phase 3**: Add QUESTIONING blink, ERROR counter, heartbeat watchdog
3. **Phase 4**: Connect relay to firmware, end-to-end test
4. **Phase 5**: Build verification, deployment validation

### Parallel Strategy

- **Phase 2 (Agent Monitor) and Phase 3 (Firmware)** are fully independent — can be developed simultaneously
- Within Phase 3: **3a (LED) + 3b (Serial)** are independent — create headers in parallel, implementations in parallel
- Phase 4 (Integration) requires both Phase 2 and Phase 3 complete

---

## Notes

- Reference light-test patterns: `gpio_hold_dis()`, `delay(1500)` for serial stability, pin `#define` style, `digitalWrite()` on/off pattern from `D:\Code\opencode-light\light-test\esp32-traffic-light\src\main.cpp`
- All firmware timing MUST use `millis()` — never `delay()` except the single `delay(1500)` in `serial_init()` for USB CDC enumeration
- Serial communication: `Serial` (USB CDC via `ARDUINO_USB_CDC_ON_BOOT=1`), NOT `Serial0` (hardware UART). The light-test uses `Serial0` because it's a different setup — this project uses USB CDC as the sole communication channel per constitution
- Type safety: No `String` class usage — use C-strings (`char[]`) and `strcmp()` per contracts note
- Commands are case-sensitive: `IDLE` valid, `idle` treated as `ERR UNKNOWN`
- `loop()` must return in <1ms — poll `Serial.available()`, check `millis()`, call `led_tick()`, no blocking operations
