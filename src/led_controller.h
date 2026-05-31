/**
 * LED Controller — Non-blocking state machine for 3-color traffic light
 * Drives Green (GPIO4), Yellow (GPIO5), Red (GPIO6) via millis()-based patterns
 */

#pragma once
#include <Arduino.h>

// ── LED Output Mode ───────────────────────────────────────────
enum class LedMode : uint8_t {
    OFF        = 0,
    ON         = 1,
    SLOW_BLINK = 2,   // 1 Hz (500ms on, 500ms off)
    FAST_BLINK = 3    // 2 Hz (250ms on, 250ms off)
};

// ── Agent Operational State ────────────────────────────────────
// Lower numeric value = higher priority
enum class AgentState : uint8_t {
    ERROR        = 0,  // Priority 0 — highest
    QUESTION     = 1,  // Priority 1
    EXECUTING    = 2,  // Priority 2
    IDLE         = 3,  // Priority 3
    DISCONNECTED = 4,  // Priority 4 — lowest (derived, auto-triggered)
    SILENT       = 5   // Special overlay — all LEDs off
};

// ── Per-LED Blink State Tracking ──────────────────────────────
struct LedBlink {
    bool state;                     // Current output: HIGH or LOW
    unsigned long previousMillis;   // Last toggle timestamp (ms)
    unsigned long interval;         // 0 = steady, >0 = blink half-period in ms
};

// ── LED Output Signal Configuration ───────────────────────────
struct LedSignal {
    LedMode green;
    LedMode yellow;
    LedMode red;
};

// ── Public API ─────────────────────────────────────────────────
void led_init();
void led_setState(AgentState state);
void led_tick();
