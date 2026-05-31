# Implementation Plan: Agent Status LED Indicator

**Branch**: `001-agent-status-led` | **Date**: 2026-05-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-agent-status-led/spec.md`

## Summary

Implement an ESP32-S3-R16N8 firmware that drives a 3-color LED traffic light module (Green=GPIO 4, Yellow=GPIO 5, Red=GPIO 6) to visually indicate OpenCode agent status. The firmware receives state commands over USB serial (USB-only per constitution), parses them with CRC validation, and drives LEDs using non-blocking patterns. States follow priority: Error > Question > Executing > Idle. The PC-side relay script reads OpenCode agent events and sends serial commands to the ESP32. Flashing and monitoring use the esp32-devops MCP toolchain (`pio run -t upload`; `pio device monitor`).

## Technical Context

**Language/Version**: C++17 (Arduino framework via PlatformIO ESP32 core 3.x); Python 3.11+ (PC relay script)

**Primary Dependencies**: 
- PlatformIO (build system)
- Arduino-ESP32 core (framework = arduino)
- ESP32-S3 hardware support (USB CDC serial, GPIO)
- Python `pyserial` (PC relay script)

**Storage**: N/A (stateless firmware — no persistent storage needed)

**Testing**: PlatformIO Unity test framework for firmware; manual integration testing via esp32-devops MCP

**Target Platform**: ESP32-S3-R16N8 (16MB Flash, 8MB PSRAM, USB-OTG) — USB serial only

**Project Type**: Embedded firmware + PC-side relay script

**Performance Goals**: 
- State-change-to-LED latency: <500ms (SC-002)
- LED pattern update loop: non-blocking 10ms tick
- Serial baud rate: 115200 (SC-006)
- Frame error rate: <0.01% with CRC validation (SC-006)
- Heartbeat timeout: 5 seconds (SC-005)

**Constraints**: 
- USB-only communication (constitution §Hardware Constraints)
- No WiFi, no Bluetooth initialization or code
- LED blink patterns: 1Hz (question), 2Hz (disconnected), 50% duty cycle
- State priority: Error > Question > Executing > Idle
- Power: USB bus-powered only

**Scale/Scope**: Single ESP32 device, 3 GPIO outputs, 5 LED states, 1 serial command protocol

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| **I. Think Before Coding** | ✅ PASS | Spec fully clarifies 5 states, priorities, edge cases, and success criteria. All assumptions documented in spec §Assumptions. |
| **II. Simplicity First** | ✅ PASS | Single firmware file (led_controller) + serial parser. No speculative features. 5 states, 3 LEDs — no over-engineering. |
| **III. Surgical Changes** | ✅ PASS | Greenfield project — no existing code to modify. All new code is directly traceable to spec requirements. |
| **IV. Goal-Driven Execution** | ✅ PASS | Success criteria SC-001 through SC-006 are verifiable and measurable. Each FR has corresponding acceptance scenarios. |
| **Hardware §USB-Only** | ✅ PASS | USB serial CDC only. No WiFi/Bluetooth includes in build. PlatformIO config excludes wireless frameworks. |
| **Hardware §Build Verification** | ✅ PASS | Build will be verified via `esp32-devops` MCP to confirm no wireless compilation units. |
| **Agent §Delegation First** | ✅ PASS | Implementation will be decomposed into parallel subagent tasks. |
| **Agent §Parallel by Default** | ✅ PASS | Firmware and PC script are independent work units — will execute in parallel. |
| **Agent §Todo Accountability** | ✅ PASS | Detailed todo list with WHERE/HOW/WHY/EXPECTED will be created before implementation. |
| **Quality Gates** | PENDING | Will verify: Constitution Compliance, Surgical Scope, Simplicity Audit, Verification Evidence, Self-Review at implementation completion. |

**Gate Result**: ✅ ALL CONSTITUTION CHECKS PASS. No violations to justify.

### Post-Design Re-Evaluation (Phase 1 Complete)

| Principle | Status | Design Evidence |
|-----------|--------|-----------------|
| **I. Think Before Coding** | ✅ PASS | All 7 research questions resolved with rationales and alternatives in research.md. Serial protocol fully specified in contracts/serial-protocol.md. Data model defines all entities, state transitions, and validation rules. |
| **II. Simplicity First** | ✅ PASS | Design uses: `enum + switch` state machine (5 states, not OOP pattern), millis()-based blink (no RTOS/FreeRTOS), newline-delimited text protocol (no JSON/binary). Single `main.cpp` with modular headers — no speculative abstractions. |
| **III. Surgical Changes** | ✅ PASS | Greenfield — all new code is directly traceable to spec requirements. No existing code to modify. |
| **IV. Goal-Driven Execution** | ✅ PASS | Each FR maps to verifiable acceptance scenarios. SC-001 through SC-006 provide measurable success criteria. |
| **Hardware §USB-Only** | ✅ PASS | platformio.ini uses `upload_protocol = esp-builtin` (native USB serial only). No WiFi/Bluetooth includes in build flags. `ARDUINO_USB_CDC_ON_BOOT=1` for USB CDC serial — no external UART chip needed. |
| **Hardware §Build Verification** | ✅ PASS | Build verification planned via `esp32_validate_project` + manual inspection for wireless library linkage. |
| **Quality Gates** | ✅ | Pending implementation — will verify at build/test time. |

**Post-Design Gate Result**: ✅ ALL CHECKS PASS. Design is consistent with constitution principles.

## Project Structure

### Documentation (this feature)

```text
specs/001-agent-status-led/
├── spec.md              # Feature specification
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (serial protocol contract)
└── tasks.md             # Phase 2 output (/speckit.tasks command — NOT created here)
```

### Source Code (repository root)

```text
# PlatformIO project at repository root (single embedded project)
platformio.ini           # PlatformIO build configuration
src/
├── main.cpp             # Entry point — setup() + loop()
├── led_controller.h     # LED state machine (non-blocking patterns)
├── led_controller.cpp
├── serial_protocol.h    # Serial command parser + CRC validation
├── serial_protocol.cpp
└── pin_config.h         # GPIO pin definitions

scripts/
└── agent_relay.py       # PC-side: reads OpenCode events, sends serial commands

test/
└── test_led_controller/ # PlatformIO Unity tests
    ├── test_led_controller.cpp
    └── test_serial_protocol.cpp
```

**Structure Decision**: Single PlatformIO project at root. This is the only embedded firmware in the repository, so a root-level PlatformIO project is the simplest structure. The PC relay script lives in `scripts/` as it's not part of the firmware build. This follows the constitution's Simplicity First principle — no unnecessary directory nesting.

## Complexity Tracking

> No constitution violations to justify — table intentionally empty.

