/**
 * LED Controller — Non-blocking state machine for 3-color traffic light
 * Drives Green (GPIO4), Yellow (GPIO5), Red (GPIO6) via millis()-based patterns
 */

#pragma once
#include <Arduino.h>

// ── LED Output Mode ───────────────────────────────────────────
enum class LedMode : uint8_t {
    OFF           = 0,
    ON            = 1,
    SLOW_BLINK    = 2,   // 1 Hz (500ms on, 500ms off)
    FAST_BLINK    = 3,   // 2 Hz (250ms on, 250ms off)
    SLOWEST_BLINK = 4,   // 0.625 Hz (800ms on, 800ms off) — ~1.6s period
    BREATH        = 5    // 2-second sine-wave breathing (analogWrite)
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

// ── Per-LED Blink/Breath State Tracking ────────────────────────
struct LedBlink {
    bool state;                     // Current output: HIGH or LOW
    unsigned long previousMillis;   // Last toggle / tick timestamp (ms)
    unsigned long interval;         // 0 = steady, >0 = half-period in ms
    unsigned long breathStartTime;  // Start of current 2s breath cycle (ms)
    bool analogMode;               // true = analogWrite(), false = digitalWrite()
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
