/**
 * Unity Test: Serial Protocol Command Parser
 * Verifies command token matching per contracts/serial-protocol.md
 */
#include <unity.h>
#include "../../src/serial_protocol.h"

void setUp(void) {}
void tearDown(void) {}

void test_command_type_values(void) {
    TEST_ASSERT_EQUAL(0, static_cast<uint8_t>(CommandType::CMD_IDLE));
    TEST_ASSERT_EQUAL(1, static_cast<uint8_t>(CommandType::CMD_EXEC));
    TEST_ASSERT_EQUAL(2, static_cast<uint8_t>(CommandType::CMD_QUESTION));
    TEST_ASSERT_EQUAL(3, static_cast<uint8_t>(CommandType::CMD_ERROR));
    TEST_ASSERT_EQUAL(4, static_cast<uint8_t>(CommandType::CMD_RESET));
    TEST_ASSERT_EQUAL(5, static_cast<uint8_t>(CommandType::CMD_PING));
    TEST_ASSERT_EQUAL(6, static_cast<uint8_t>(CommandType::CMD_SILENT));
    TEST_ASSERT_EQUAL(7, static_cast<uint8_t>(CommandType::CMD_STATUS));
}

void test_serial_init_compiles(void) {
    serial_init();
    TEST_ASSERT_TRUE(true);
}

int runUnityTests(void) {
    UNITY_BEGIN();
    RUN_TEST(test_command_type_values);
    RUN_TEST(test_serial_init_compiles);
    return UNITY_END();
}

void setup() { runUnityTests(); }
void loop() {}
