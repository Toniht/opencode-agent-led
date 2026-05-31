/**
 * Serial Protocol Parser — USB CDC line-based command processor
 * Baud: 115200 | Framing: newline-delimited text | Max line: 32 chars
 * Uses C-strings (strcmp) — no String class
 */

#pragma once
#include <Arduino.h>

// ── Parsed Command Types ──────────────────────────────────────
enum class CommandType : uint8_t {
    CMD_IDLE,
    CMD_EXEC,
    CMD_QUESTION,
    CMD_ERROR,
    CMD_RESET,
    CMD_PING,
    CMD_SILENT,
    CMD_STATUS,
    CMD_UNKNOWN,   // Unrecognized command or overflow
    CMD_NONE       // No complete line available yet
};

// ── Public API ─────────────────────────────────────────────────
void serial_init();
CommandType serial_process();
void serial_respond_ok();
void serial_respond_err(const char* reason);
