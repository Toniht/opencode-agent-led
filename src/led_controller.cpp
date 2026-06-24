/**
 * LED Controller Implementation
 * Drives 3 LEDs with non-blocking millis()-based blink/breath patterns.
 * State-to-signal mapping per data-model.md §State-to-Signal Mapping.
 *
 * Mapping:
 *   IDLE         → Green BREATH (2s sine), Yellow OFF, Red OFF
 *   EXECUTING    → Green OFF,            Yellow ON,  Red OFF
 *   QUESTION     → Green SLOW_BLK (1Hz), Yellow SLOW_BLK (alt), Red OFF
 *   ERROR        → Green OFF,            Yellow OFF, Red SLOWEST_BLK (~1.6s)
 *   DISCONNECTED → Green OFF,            Yellow OFF, Red FAST_BLK (2Hz)
 *   SILENT       → Green OFF,            Yellow OFF, Red OFF
 */

#include "led_controller.h"
#include "pin_config.h"
#include <cmath>

// ── Static Blink/Breath State (index: 0=green, 1=yellow, 2=red) ─
static LedBlink blinkState[3];

// ── GPIO pin lookup ────────────────────────────────────────────
static const int ledPins[3] = {PIN_GREEN, PIN_YELLOW, PIN_RED};

// ── Breathing period (ms) ──────────────────────────────────────
static const unsigned long BREATH_PERIOD = 2000;  // 2-second sine cycle

// ── State-to-Signal Mapping ────────────────────────────────────
static LedSignal getSignal(AgentState state) {
    switch (state) {
    case AgentState::IDLE:
        return {LedMode::BREATH, LedMode::OFF, LedMode::OFF};
    case AgentState::EXECUTING:
        return {LedMode::OFF, LedMode::ON,  LedMode::OFF};
    case AgentState::QUESTION:
        return {LedMode::SLOW_BLINK, LedMode::SLOW_BLINK, LedMode::OFF};
    case AgentState::ERROR:
        return {LedMode::OFF, LedMode::OFF, LedMode::SLOWEST_BLINK};
    case AgentState::DISCONNECTED:
        return {LedMode::OFF, LedMode::OFF, LedMode::FAST_BLINK};
    case AgentState::SILENT:
    default:
        return {LedMode::OFF, LedMode::OFF, LedMode::OFF};
    }
}

// ── Apply a single LED mode ────────────────────────────────────
static void applyMode(int index, LedMode mode) {
    LedBlink& bl = blinkState[index];
    int pin = ledPins[index];

    // ── Detach analog mode if switching away from BREATH ─────
    if (bl.analogMode && mode != LedMode::BREATH) {
        ledcDetachPin(pin);
        bl.analogMode = false;
    }

    switch (mode) {
    case LedMode::OFF:
        bl.interval = 0;
        bl.state = false;
        digitalWrite(pin, LED_OFF);
        break;

    case LedMode::ON:
        bl.interval = 0;
        bl.state = true;
        digitalWrite(pin, LED_ON);
        break;

    case LedMode::SLOW_BLINK:
        bl.interval = 500;   // 500ms half-period → 1 Hz
        bl.state = true;
        bl.previousMillis = millis();
        digitalWrite(pin, LED_ON);
        break;

    case LedMode::FAST_BLINK:
        bl.interval = 250;   // 250ms half-period → 2 Hz
        bl.state = true;
        bl.previousMillis = millis();
        digitalWrite(pin, LED_ON);
        break;

    case LedMode::SLOWEST_BLINK:
        bl.interval = 800;   // 800ms half-period → ~1.6s full cycle
        bl.state = true;
        bl.previousMillis = millis();
        digitalWrite(pin, LED_ON);
        break;

    case LedMode::BREATH:
        bl.interval = 0;
        bl.analogMode = true;
        bl.breathStartTime = millis();
        bl.state = true;
        analogWrite(pin, 255);  // start at full brightness
        break;
    }
}

// ── Public API ─────────────────────────────────────────────────

void led_init() {
    pins_init();

    for (int i = 0; i < 3; i++) {
        blinkState[i].state = false;
        blinkState[i].previousMillis = 0;
        blinkState[i].interval = 0;
        blinkState[i].breathStartTime = 0;
        blinkState[i].analogMode = false;
    }
}

void led_setState(AgentState state) {
    LedSignal sig = getSignal(state);
    applyMode(0, sig.green);
    applyMode(1, sig.yellow);
    applyMode(2, sig.red);

    // QUESTION: green and yellow alternate (not sync)
    if (state == AgentState::QUESTION) {
        blinkState[1].state = !blinkState[0].state;  // yellow opposite of green
        digitalWrite(ledPins[1], blinkState[1].state ? LED_ON : LED_OFF);
    }
}

void led_tick() {
    unsigned long now = millis();

    for (int i = 0; i < 3; i++) {
        LedBlink& bl = blinkState[i];
        int pin = ledPins[i];

        // ── Breathing: sine-wave brightness ──────────────────
        if (bl.analogMode) {
            unsigned long elapsed = (now - bl.breathStartTime) % BREATH_PERIOD;
            float t = (float)elapsed / (float)BREATH_PERIOD;
            float brightness = (sinf(t * 2.0f * (float)M_PI) + 1.0f) / 2.0f;
            uint8_t value = (uint8_t)(brightness * 255.0f);
            analogWrite(pin, LED_ON == HIGH ? value : (uint8_t)(255 - value));
            continue;  // skip blink logic for breath pins
        }

        // ── Blinking: toggle at half-period intervals ────────
        if (bl.interval > 0) {
            // Wraparound-safe millis() comparison
            if (now - bl.previousMillis >= bl.interval) {
                bl.state = !bl.state;
                digitalWrite(pin, bl.state ? LED_ON : LED_OFF);
                bl.previousMillis = now;
            }
        }
    }
}
