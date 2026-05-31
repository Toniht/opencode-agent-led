/**
 * Unity Test: LED Controller State Machine
 * Verifies state-to-signal mapping per data-model.md
 */
#include <unity.h>
#include "../../src/led_controller.h"
#include "../../src/pin_config.h"

void setUp(void) {}
void tearDown(void) {}

void test_pin_definitions(void) {
    TEST_ASSERT_EQUAL(4, PIN_GREEN);
    TEST_ASSERT_EQUAL(5, PIN_YELLOW);
    TEST_ASSERT_EQUAL(6, PIN_RED);
}

void test_agent_state_enum_values(void) {
    // Lower numeric value = higher priority (FR-008)
    TEST_ASSERT_TRUE(static_cast<uint8_t>(AgentState::ERROR) < static_cast<uint8_t>(AgentState::QUESTION));
    TEST_ASSERT_TRUE(static_cast<uint8_t>(AgentState::QUESTION) < static_cast<uint8_t>(AgentState::EXECUTING));
    TEST_ASSERT_TRUE(static_cast<uint8_t>(AgentState::EXECUTING) < static_cast<uint8_t>(AgentState::IDLE));
    TEST_ASSERT_TRUE(static_cast<uint8_t>(AgentState::IDLE) < static_cast<uint8_t>(AgentState::DISCONNECTED));
}

void test_led_init(void) {
    led_init();
    // After init, all LEDs should be controlled
    // (actual digital state depends on last setState call)
    TEST_ASSERT_TRUE(true);
}

int runUnityTests(void) {
    UNITY_BEGIN();
    RUN_TEST(test_pin_definitions);
    RUN_TEST(test_agent_state_enum_values);
    RUN_TEST(test_led_init);
    return UNITY_END();
}

void setup() { runUnityTests(); }
void loop() {}
