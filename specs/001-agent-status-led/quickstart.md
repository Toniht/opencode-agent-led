# Quickstart: Agent Status LED Indicator

**Feature**: 001-agent-status-led | **Phase**: 1 | **Date**: 2026-05-31

This guide walks through building, flashing, and verifying the ESP32-S3 firmware using the esp32-devops MCP tools.

---

## Prerequisites

- ESP32-S3-R16N8 development board connected via USB
- Traffic light LED module connected to GPIO pins: Green=4, Yellow=5, Red=6
- PlatformIO CLI installed (`pio --version`)
- esp32-devops MCP configured in `opencode.json` (already done in this project)

---

## Hardware Setup

```
ESP32-S3-R16N8          Traffic Light Module
     GPIO4 ────────────── G (Green LED, pin 4)
     GPIO5 ────────────── Y (Yellow LED, pin 5)
     GPIO6 ────────────── R (Red LED, pin 6)
     GND   ────────────── GND (common ground)
```

**Note**: If module is common-anode, connect VCC instead of GND and invert LED polarities in firmware (`#define LED_ON LOW`).

---

## Step 1: Create PlatformIO Project

Use the esp32-devops MCP to scaffold the project at repo root:

```
esp32_create_project(
    name: "agent-status-led",
    projectPath: ".",
    board: "esp32-s3-devkitc-1",
    template: "bare"
)
```

This creates:
```
platformio.ini           # Board config
src/
└── main.cpp             # Bare Arduino template (to be customized)
```

---

## Step 2: Customize platformio.ini

After project creation, update `platformio.ini`:

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

; USB CDC — native USB serial
build_flags =
    -DBOARD_HAS_PSRAM
    -DARDUINO_USB_CDC_ON_BOOT=1

; Upload via native USB
upload_protocol = esp-builtin
```

**Verify with**:
```
esp32_validate_project
```

---

## Step 3: Write Firmware (src/main.cpp)

Replace the generated `src/main.cpp` with the state machine implementation (see `data-model.md` and `contracts/serial-protocol.md`). Key elements:

1. **Pin definitions**: `LED_GREEN=4`, `LED_YELLOW=5`, `LED_RED=6`
2. **State enum**: `IDLE`, `EXECUTING`, `QUESTIONING`, `ERROR`, `DISCONNECTED`, `SILENT`
3. **Serial parser**: Read lines from `Serial`, match against command keywords
4. **LED controller**: `digitalWrite()` for steady states, `millis()` for blinking
5. **Heartbeat watchdog**: Track `lastActivity`, trigger DISCONNECTED after 5s
6. **Error counter**: Lock red LED after 3 consecutive ERROR commands
7. **No `delay()` calls** — all timing via `millis()`

---

## Step 4: Build Firmware

```
esp32_build
```

Or directly:
```powershell
pio run -t upload
```

Expected output includes memory usage:
```
RAM:   [==        ]  15.2% (used 49828 bytes from 327680 bytes)
Flash: [=         ]   8.7% (used 284672 bytes from 3342336 bytes)
```

**Verify no WiFi/Bluetooth symbols** in the build output. The firmware should not link `libwifi.a`, `libbt.a`, or any wireless-related libraries.

---

## Step 5: Detect ESP32 Port

```
esp32_detect_ports
esp32_list_ports
```

On Windows, typical output:
```
COM3: Silicon Labs CP210x USB to UART Bridge (ESP32 detected)
```

Note the COM port (e.g., `COM3`).

---

## Step 6: Flash Firmware

```
esp32_flash(port: "COM3")
```

Or use the combined build+flash:
```
esp32_full_cycle(port: "COM3")
```

Or directly:
```powershell
pio run -t upload
```

Expected output ends with:
```
Leaving...
Hard resetting via RTS pin...
```

**After flashing**: Green LED should light up (default IDLE state on boot).

---

## Step 7: Monitor Serial Output

Open the serial monitor to see firmware output and send test commands:

```powershell
pio device monitor -b 115200
```

**Test commands** — type these into the monitor and press Enter:

```
STATUS       → Should respond: IDLE
EXEC         → Should respond: OK, Yellow LED turns on
QUESTION     → Should respond: OK, Green+Yellow blink 1Hz
ERROR        → Should respond: OK, Red LED turns on
RESET        → Should respond: OK, Green LED turns on
PING         → Should respond: OK (heartbeat)
SILENT       → Should respond: OK, all LEDs off
IDLE         → Should respond: OK, Green LED turns on
FOO          → Should respond: ERR UNKNOWN
```

---

## Step 8: Verify Heartbeat Timeout

1. Send a few `PING` commands — LEDs should reflect current state
2. Stop sending commands for 6 seconds
3. Red LED should start fast blinking (2Hz) — DISCONNECTED state
4. Send `IDLE` — Red should stop blinking, Green should turn on
5. Serial should show `OK` response

---

## Step 9: Run Pre-Deployment Checks

```
esp32_test_firmware(port: "COM3")
esp32_validate_deployment(port: "COM3")
```

These check boot behavior, heartbeat stability, and memory integrity.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Build fails: "board not found" | Run `pio platform update` or check `board = esp32-s3-devkitc-1` in platformio.ini |
| Flash fails: "no serial port" | Check USB connection, verify COM port with `esp32_list_ports` |
| No LED response | Verify GPIO pin numbers (4,5,6) in `pinMode()` calls. Check common-cathode vs common-anode wiring. |
| Serial monitor: garbled text | Ensure baud rate matches: monitor at 115200, firmware `Serial.begin(115200)` |
| DISCONNECTED triggers immediately | Check `heartbeatTimeout` constant (default 5000ms). Ensure PC sends `PING` within the window. |
| esp32-devops tools fail | Verify `FIRMWARE_TOOLKIT_PATH` in `opencode.json` points to correct directory. Build/flash tools should work; test/benchmark tools need FirmwareToolkit scripts. |

---

## Command Summary (esp32-devops MCP)

| Tool | Purpose |
|------|---------|
| `esp32_create_project` | Scaffold new PlatformIO project |
| `esp32_validate_project` | Check project structure |
| `esp32_build` | Compile firmware |
| `esp32_flash` | Upload firmware to ESP32 |
| `esp32_full_cycle` | Build + Flash in one step |
| `esp32_clean` | Clean build artifacts |
| `esp32_list_ports` | List available serial ports |
| `esp32_detect_ports` | Auto-detect ESP32 devices |
| `esp32_test_firmware` | Run boot/heartbeat/memory tests |
| `esp32_validate_deployment` | Full pre-deployment check |
