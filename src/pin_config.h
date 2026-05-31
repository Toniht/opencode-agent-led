/**
 * Pin Configuration — ESP32-S3-R16N8 Agent Status LED
 * Pins: Green=GPIO4, Yellow=GPIO5, Red=GPIO6
 * Active-high: HIGH = LED on, LOW = LED off
 */

#pragma once
#include <Arduino.h>

// ── GPIO Pin Definitions ──────────────────────────────────────
#define PIN_GREEN  4
#define PIN_YELLOW 5
#define PIN_RED    6

// ── LED Polarity (active-high) ─────────────────────────────────
#define LED_ON  HIGH
#define LED_OFF LOW

// ── Release GPIO hold state from previous firmware ─────────────
inline void pins_release_hold() {
    gpio_hold_dis(GPIO_NUM_4);
    gpio_hold_dis(GPIO_NUM_5);
    gpio_hold_dis(GPIO_NUM_6);
}

// ── Initialize all LED pins as outputs, set to OFF ─────────────
inline void pins_init() {
    pins_release_hold();
    pinMode(PIN_GREEN,  OUTPUT);
    pinMode(PIN_YELLOW, OUTPUT);
    pinMode(PIN_RED,    OUTPUT);
    digitalWrite(PIN_GREEN,  LED_OFF);
    digitalWrite(PIN_YELLOW, LED_OFF);
    digitalWrite(PIN_RED,    LED_OFF);
}
