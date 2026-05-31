# Research: Agent Status LED Indicator

**Feature**: 001-agent-status-led | **Phase**: 0 | **Date**: 2026-05-31

## Research Questions Resolved

### RQ-1: ESP32-S3-R16N8 Board Capabilities & GPIO Availability

**Decision**: Use ESP32-S3-R16N8 with Arduino framework, GPIO pins 4 (Green), 5 (Yellow), 6 (Red).

**Rationale**:
- ESP32-S3-WROOM-1-N16R8 module: 16MB flash (OPI), 8MB PSRAM (OPI), dual-core Xtensa LX7 @ 240 MHz
- GPIO 4, 5, 6 are **fully available and unrestricted** — no boot configuration conflicts, no internal flash/PSRAM usage. All three are RTC_GPIO pins in the VDD3P3_RTC power domain.
- GPIO 35, 36, 37 are reserved for internal 8-line PSRAM communication — avoid these.
- Default drive strength 20mA per pin — sufficient for standard LED current (~5-10mA with resistor).
- All three pins are on VDD3P3_RTC power domain — usable in deep sleep if needed (not currently required).

**Alternatives considered**:
- ESP32-C3: Rejected — limited GPIO multiplexing, different pin layout.
- ESP32 (original): Rejected — user specified ESP32-S3-R16N8 development board.
- Using LEDC PWM for brightness control: Rejected for simplicity — on/off suffices per spec; PWM adds unnecessary complexity.

**Sources**: Espressif ESP32-S3 Datasheet, Micro Robotics ESP32-S3 Manual, PlatformIO community forums.

---

### RQ-2: PlatformIO Configuration for ESP32-S3-R16N8

**Decision**: Use `espressif32` platform with `esp32-s3-devkitc-1` board, Arduino framework, 115200 baud.

**Rationale**:
- Stock PlatformIO `espressif32` platform (v6.x) supports ESP32-S3 out of the box.
- Board `esp32-s3-devkitc-1` is the closest match for ESP32-S3-R16N8 (the R16N8 variant uses same pinout, different flash memory configuration).
- PSRAM configuration: `board_build.psram_type = opi` (Octal PSRAM on ESP32-S3-WROOM-1-N16R8).
- No WiFi/Bluetooth compilation needed — `bare` template, exclude wireless libraries.
- Monitor speed 115200 matches the serial protocol (consistent with esp32-devops MCP defaults).

**PlatformIO configuration**:
```ini
[env:esp32-s3-devkitc-1]
platform = espressif32
board = esp32-s3-devkitc-1
framework = arduino
monitor_speed = 115200

; Flash: 16MB QIO
board_build.flash_mode = qio
board_upload.flash_size = 16MB
board_build.partitions = default_16MB.csv

; PSRAM: 8MB Octal (WROOM-1 N16R8 module)
board_build.arduino.memory_type = qio_opi
board_build.psram_type = opi

; USB CDC — native USB serial via USB-OTG
build_flags =
    -DBOARD_HAS_PSRAM
    -DARDUINO_USB_CDC_ON_BOOT=1

; Upload via native USB (esp-builtin), not external UART chip
upload_protocol = esp-builtin
```

**Alternatives considered**:
- `pioarduino` community platform (Arduino core 3.x): Considered — but stock `espressif32` platform (v6.x) already bundles Arduino core 3.x for ESP32-S3. Using it directly avoids third-party platform overhead.
- ESP-IDF framework: Rejected — Arduino framework provides `digitalWrite`, `pinMode`, `Serial` with zero setup overhead. ESP-IDF would require GPIO driver, UART driver, and FreeRTOS task management.

**Sources**: PlatformIO ESP32-S3 community discussions, espressif32 platform documentation.

---

### RQ-3: Non-Blocking LED Blink Patterns

**Decision**: Use `millis()`-based timing with per-LED state tracking structs. No hardware timers or RMT.

**Rationale**:
- `millis()` returns `unsigned long` with 49.7-day wraparound. Subtraction pattern `(now - previous >= interval)` is wraparound-safe (modulo arithmetic).
- Each LED channel independently tracks `previousMillis`, `interval`, and `state` in a `LedBlink` struct array.
- Two blink modes required:
  - **1Hz (slow blink)**: 500ms on, 500ms off — for Questioning state (green + yellow simultaneously)
  - **2Hz (fast blink)**: 250ms on, 250ms off — for Disconnected state (red only)
- Pattern: `interval > 0` means blinking is active; `interval = 0` means steady state (controlled by `digitalWrite` directly).
- Blocking `delay()` is NEVER used — the `loop()` function must continuously read serial input at 115200 baud to avoid buffer overflow.

**Alternatives considered**:
- Hardware RMT (Remote Control Transceiver) for CPU-free blinking: Rejected — adds complexity (RMT driver initialization, buffer management) with no benefit. The CPU overhead of `millis()` check in `loop()` is negligible (< 1 µs per iteration).
- FreeRTOS task for LED control: Rejected per Simplicity First — single-threaded Arduino `loop()` is sufficient.
- ESP32 Timer API: Rejected — `millis()` is simpler and sufficient for Hz-range blinking.

**Source**: Arduino BlinkWithoutDelay example, Arduino StackExchange millis() wraparound analysis.

---

### RQ-4: Serial Command Protocol Design

**Decision**: Newline-delimited text protocol with simple keyword commands and heartbeat mechanism.

**Rationale**:
- Line-based parsing (`Serial.read()` until `\n` or `\r`) is the simplest reliable approach for 115200 baud.
- Commands are simple keywords: `IDLE`, `EXEC`, `QUESTION`, `ERROR`, `RESET`, `PING`, `SILENT`.
- Heartbeat: PC sends `PING\n` every ~1-2 seconds. ESP32 tracks `lastActivity` timestamp. If no data for 5000ms → Disconnected state.
- Response: Firmware acknowledges with `OK <command>\n` or `ERR <reason>\n`.
- No binary framing — text commands are human-readable via serial monitor (debuggable).
- No checksum needed — line-based text with \n delimiter provides implicit framing; invalid lines silently ignored. After 10 consecutive unparseable lines → Disconnected (per FR-011).

**Command set** (see contracts/serial-protocol.md for full specification):

| Command | Direction | Effect |
|---------|-----------|--------|
| `IDLE` | PC → ESP32 | Set state: Idle (green steady) |
| `EXEC` | PC → ESP32 | Set state: Executing (yellow steady) |
| `QUESTION` | PC → ESP32 | Set state: Questioning (green+yellow 1Hz blink) |
| `ERROR` | PC → ESP32 | Set state: Error (red steady) |
| `RESET` | PC → ESP32 | Reset error count, return to Idle |
| `PING` | PC → ESP32 | Heartbeat — reset timeout |
| `SILENT` | PC → ESP32 | Turn off all LEDs (override) |
| `STATUS` | PC → ESP32 | Query current state |
| `OK <cmd>` | ESP32 → PC | Command acknowledged |
| `ERR <msg>` | ESP32 → PC | Command failed |

**Alternatives considered**:
- Binary framing with checksum: Rejected — overengineered. Text protocol is debuggable, extensible, and sufficient for < 500ms latency over 115200 baud USB.
- JSON over serial: Rejected — parsing overhead on ESP32, unnecessary for 7 simple commands.
- Modbus/RTU: Rejected — wrong domain (industrial protocol for sensor networks, not single-device LED control).

---

### RQ-5: State Machine Architecture

**Decision**: Priority-based switch with error counter and heartbeat watchdog.

**Rationale**:
- 5 states with clear priority: `ERROR > QUESTION > EXECUTING > IDLE > DISCONNECTED`
- `Disconnected` is a **derived state** — not set by command, triggered by heartbeat timeout. It auto-resolves when serial activity resumes.
- Error counter: Tracks consecutive `ERROR` commands. At 3 consecutive errors → red LED locked (persists until `RESET`).
- State transition table:

| Current State | Command | Next State | LED Pattern |
|---|---|---|---|
| Any | `ERROR` | ERROR (increment counter) | Red steady |
| Any | `QUESTION` | QUESTION | Green+Yellow 1Hz blink |
| Any | `EXEC` | EXECUTING | Yellow steady |
| Any | `IDLE` | IDLE | Green steady |
| ERROR | `RESET` | IDLE (counter=0) | Green steady |
| Any | `SILENT` | SILENT (override) | All off |
| Any | Timeout (5s) | DISCONNECTED | Red 2Hz blink |

**Alternatives considered**:
- Event-driven state transitions (callback-based): Rejected — single-threaded Arduino `loop()` with serial polling is simpler.
- State pattern (OOP): Rejected — overengineered for 5 states. `enum + switch` is the idiomatic embedded pattern.

---

### RQ-6: esp32-devops MCP Tool Usage

**Decision**: Use `esp32_create_project` for initial scaffolding, `esp32_build` + `esp32_flash` for deployment, manual `pio device monitor` for verification.

**Rationale**:
- `esp32_create_project` with `template="bare"` generates a working `platformio.ini` + `src/main.cpp` scaffold. Then customize `main.cpp` with the state machine implementation.
- `esp32_full_cycle` maps to build + flash (`pio run -t upload`). Serial monitoring (`pio device monitor`) must be run separately in a different terminal.
- `esp32_validate_project` checks project structure before build.
- `esp32_validate_deployment` runs pre-deployment checks.
- Port detection: `esp32_detect_ports` auto-discovers ESP32 devices (via serial-port-manager.py in FirmwareToolkit).
- **Key limitation**: `FIRMWARE_TOOLKIT_PATH` in opencode.json points to the MCP directory, which lacks the Python scripts. Build/flash tools work without them (they use their own batch scripts); test/benchmark tools require FirmwareToolkit installation.

**Sources**: esp32-devops-mcp source code (build.ts, project.ts, serial.ts), RELEASE_NOTES.md.

---

### RQ-7: LED Hardware Configuration

**Decision**: Active-high output (`HIGH` = LED on, `LOW` = LED off) with inline current-limiting resistors.

**Rationale**:
- Most ESP32 dev boards have 3.3V GPIO output. Standard LED forward voltage ~2V (green/yellow) to ~1.8V (red).
- With 220Ω resistor: current = (3.3V - 2.0V) / 220Ω ≈ 6mA — safe for GPIO and visible brightness.
- If common-anode module: invert logic (`LOW` = on) in firmware by changing `LED_ON` / `LED_OFF` defines.
- `pinMode(pin, OUTPUT)` + `digitalWrite(pin, state)` — standard Arduino API.

**Alternatives considered**:
- LEDC PWM for dimming: Rejected — not specified in requirements.
- Dedicated LED driver IC: Rejected — overengineered for 3 LEDs.

---

## Summary of Decisions

| Decision | Choice | Key Factor |
|----------|--------|------------|
| Framework | Arduino on PlatformIO | Lowest complexity, built-in GPIO/Serial APIs |
| Board config | esp32-s3-devkitc-1 | Closest match for ESP32-S3-R16N8 |
| LED control | `digitalWrite()` + `millis()` blinking | Non-blocking, no external deps |
| Serial protocol | Newline-delimited text | Human-readable, debuggable, simple parsing |
| State machine | `enum` + `switch` + priority ordering | Idiomatic embedded C++ |
| Heartbeat | 5s timeout on any serial activity | Covers all states, not just PING |
| Project location | Repository root | Simplest structure — single embedded project |
| Deployment | esp32-devops MCP build + flash | Integrated with project tooling |
