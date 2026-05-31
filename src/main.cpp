/**
 * Agent Status LED Indicator — Main Entry Point
 * ESP32-S3-R16N8 firmware | Platform: espressif32 | Framework: Arduino
 * USB-only (no WiFi, no Bluetooth) | 115200 baud | Non-blocking millis() blink
 *
 * State Machine (data-model.md §AgentState):
 *   ERROR (0) > QUESTION (1) > EXECUTING (2) > IDLE (3)
 *   DISCONNECTED — auto-triggered by heartbeat timeout (5s) or 10 invalid frames
 *   SILENT — overlay (all LEDs off, preserves underlying state)
 *
 * Serial Commands (contracts/serial-protocol.md):
 *   IDLE, EXEC, QUESTION, ERROR, RESET, PING, SILENT, STATUS
 */

#include <Arduino.h>
#include "pin_config.h"
#include "led_controller.h"
#include "serial_protocol.h"

// ── System Runtime State (data-model.md §SystemRuntime) ────────
static AgentState    currentState       = AgentState::IDLE;
static AgentState    underlyingState    = AgentState::IDLE;  // beneath SILENT/DISCONNECTED
static uint8_t       errorCount         = 0;
static bool          errorLocked        = false;
static unsigned long lastActivity       = 0;
static uint8_t       invalidFrames      = 0;
static bool          silentMode         = false;
static const unsigned long bootGracePeriod  = 10000;  // 10s — no DISCONNECTED during boot
static const unsigned long heartbeatTimeout = 5000;   // 5s  — spec compliant (FR-007, SC-005)

// ── State name lookup for STATUS response ──────────────────────
static const char* getStateName(AgentState state) {
    switch (state) {
    case AgentState::IDLE:         return "IDLE";
    case AgentState::EXECUTING:    return "EXECUTING";
    case AgentState::QUESTION:     return "QUESTIONING";
    case AgentState::ERROR:        return "ERROR";
    case AgentState::DISCONNECTED: return "DISCONNECTED";
    case AgentState::SILENT:       return "SILENT";
    default:                       return "UNKNOWN";
    }
}

// ── Set the effective LED state ────────────────────────────────
// Handles SILENT overlay, DISCONNECTED auto-save, and normal transitions.
static void applyState(AgentState newState, bool force = false) {

    // ── SILENT: overlay — preserve underlying state ────────────
    if (newState == AgentState::SILENT) {
        if (!silentMode) {
            underlyingState = currentState;
        }
        silentMode = true;
        currentState = AgentState::SILENT;
        led_setState(AgentState::SILENT);
        return;
    }

    // ── Non-SILENT: clear silent overlay ───────────────────────
    silentMode = false;

    // ── DISCONNECTED: save state to restore on recovery ────────
    if (newState == AgentState::DISCONNECTED) {
        if (currentState != AgentState::DISCONNECTED) {
            // Save current non-overlay state for recovery
            if (currentState != AgentState::SILENT) {
                underlyingState = currentState;
            }
            currentState = AgentState::DISCONNECTED;
            led_setState(AgentState::DISCONNECTED);
        }
        return;
    }

    // ── Priority guard (FR-008): ERROR(0) > QUESTION(1) > EXECUTING(2) > IDLE(3) ──
    // IDLE is always accepted (natural resting state). Other transitions: higher
    // priority states cannot be overridden by lower priority states.
    if (!force
        && newState != AgentState::IDLE
        && static_cast<uint8_t>(newState) > static_cast<uint8_t>(currentState)
        && currentState != AgentState::DISCONNECTED
        && currentState != AgentState::SILENT) {
        return;  // reject lower-priority state transition (except to IDLE)
    }

    // ── Normal state transition ────────────────────────────────
    currentState = newState;
    led_setState(currentState);
}

// ── Setup: one-time initialization ─────────────────────────────
void setup() {
    serial_init();
    led_init();

    // Initialize runtime
    currentState    = AgentState::IDLE;
    underlyingState = AgentState::IDLE;
    lastActivity    = millis();
    led_setState(AgentState::IDLE);

    // Startup banner (pattern from light-test)
    Serial.println("\n=== Agent Status LED Indicator ===");
    Serial.printf("Green=GPIO%d Yellow=GPIO%d Red=GPIO%d\n",
                  PIN_GREEN, PIN_YELLOW, PIN_RED);
    Serial.println("READY");
}

// ── Loop: command dispatch + heartbeat + LED tick ──────────────
void loop() {
    CommandType cmd = serial_process();
    bool validCommand = false;

    // ── Command dispatch ───────────────────────────────────────
    if (cmd != CommandType::CMD_NONE) {
        switch (cmd) {

        // --- State-setting commands (blocked if errorLocked) ---
        case CommandType::CMD_IDLE:
            if (errorLocked) {
                serial_respond_err("LOCKED");
                break;
            }
            applyState(AgentState::IDLE);
            serial_respond_ok();
            validCommand = true;
            break;

        case CommandType::CMD_EXEC:
            if (errorLocked) {
                serial_respond_err("LOCKED");
                break;
            }
            applyState(AgentState::EXECUTING);
            serial_respond_ok();
            validCommand = true;
            break;

        case CommandType::CMD_QUESTION:
            if (errorLocked) {
                serial_respond_err("LOCKED");
                break;
            }
            applyState(AgentState::QUESTION);
            serial_respond_ok();
            validCommand = true;
            break;

        case CommandType::CMD_ERROR:
            if (errorLocked) {
                serial_respond_err("LOCKED");
            } else {
                errorCount++;
                if (errorCount >= 3) {
                    errorLocked = true;
                    serial_respond_err("LOCKED");
                } else {
                    serial_respond_ok();
                }
                applyState(AgentState::ERROR);
            }
            validCommand = true;
            break;

        // --- RESET: clear error counter + lock, force IDLE (bypass priority) ──
        case CommandType::CMD_RESET:
            errorCount  = 0;
            errorLocked = false;
            applyState(AgentState::IDLE, true);  // force=true bypasses priority guard
            serial_respond_ok();
            validCommand = true;
            break;

        // --- PING: heartbeat — no state change ─────────────────
        case CommandType::CMD_PING:
            serial_respond_ok();
            validCommand = true;
            break;

        // --- SILENT: LED override — preserves underlying state ─
        case CommandType::CMD_SILENT:
            applyState(AgentState::SILENT);
            serial_respond_ok();
            validCommand = true;
            break;

        // --- STATUS: respond with current state name ───────────
        case CommandType::CMD_STATUS:
            Serial.println(getStateName(currentState));
            validCommand = true;
            break;

        // --- Unknown / overflow / invalid ──────────────────────
        case CommandType::CMD_UNKNOWN:
            invalidFrames++;
            if (invalidFrames >= 10) {
                applyState(AgentState::DISCONNECTED);
            }
            serial_respond_err("UNKNOWN");
            break;

        default:
            break;
        }

        // ── Update heartbeat on any valid command ──────────────
        if (validCommand) {
            lastActivity  = millis();
            invalidFrames = 0;

            // Recover from DISCONNECTED on valid serial input
            if (currentState == AgentState::DISCONNECTED) {
                AgentState restore = underlyingState;
                if (restore == AgentState::SILENT) {
                    restore = AgentState::IDLE;  // safety fallback
                }
                currentState = restore;
                silentMode   = false;
                led_setState(currentState);
            }
        }
    }

    // ── Heartbeat Watchdog: after boot grace, 5s timeout → DISCONNECTED ──
    unsigned long now = millis();
    if (now > bootGracePeriod && (now - lastActivity) > heartbeatTimeout) {
        if (currentState != AgentState::DISCONNECTED) {
            applyState(AgentState::DISCONNECTED);
        }
    }

    // ── Update non-blocking LED blink patterns ─────────────────
    led_tick();
}
