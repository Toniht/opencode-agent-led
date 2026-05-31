/**
 * Serial Protocol Implementation
 * Line-buffered parser for USB CDC at 115200 baud.
 * Matches commands via strcmp(), emits OK/ERR responses via Serial.print().
 *
 * Command tokens (case-sensitive):
 *   IDLE, EXEC, QUESTION, ERROR, RESET, PING, SILENT, STATUS
 *
 * Framing: newline-delimited text, max 32 chars per line.
 * Empty lines silently ignored. Unknown/overflow lines → CMD_UNKNOWN.
 */

#include "serial_protocol.h"
#include <cstring>

#define MAX_LINE_LEN 32

// ── Static Line Buffer (persists between calls for partial reads) ──
static char  lineBuffer[MAX_LINE_LEN + 1];
static int   lineIdx  = 0;
static bool  overflow = false;

// ── Trim leading/trailing whitespace (in-place) ────────────────
static void trim(char* str) {
    // Trim leading whitespace
    int start = 0;
    while (str[start] == ' ' || str[start] == '\t') {
        start++;
    }

    // Trim trailing whitespace + line endings
    int end = (int)strlen(str) - 1;
    while (end >= start &&
           (str[end] == ' '  || str[end] == '\t' ||
            str[end] == '\r' || str[end] == '\n')) {
        str[end] = '\0';
        end--;
    }

    // Shift string to start if leading whitespace was removed
    if (start > 0) {
        int i = 0;
        while (str[start] != '\0') {
            str[i++] = str[start++];
        }
        str[i] = '\0';
    }
}

// ── Match known command tokens against the trimmed line ────────
static CommandType matchCommand(const char* line) {
    if (strcmp(line, "IDLE") == 0)     return CommandType::CMD_IDLE;
    if (strcmp(line, "EXEC") == 0)     return CommandType::CMD_EXEC;
    if (strcmp(line, "QUESTION") == 0) return CommandType::CMD_QUESTION;
    if (strcmp(line, "ERROR") == 0)    return CommandType::CMD_ERROR;
    if (strcmp(line, "RESET") == 0)    return CommandType::CMD_RESET;
    if (strcmp(line, "PING") == 0)     return CommandType::CMD_PING;
    if (strcmp(line, "SILENT") == 0)   return CommandType::CMD_SILENT;
    if (strcmp(line, "STATUS") == 0)   return CommandType::CMD_STATUS;

    return CommandType::CMD_UNKNOWN;
}

// ── Public API ─────────────────────────────────────────────────

void serial_init() {
    Serial.begin(115200);
    delay(1500);   // USB CDC enumeration stability (per light-test pattern)
}

CommandType serial_process() {
    while (Serial.available() > 0) {
        char c = Serial.read();

        // ── Newline (Unix) ─────────────────────────────────────
        if (c == '\n') {
            lineBuffer[lineIdx] = '\0';
            lineIdx = 0;
            bool wasOverflow = overflow;
            overflow = false;

            trim(lineBuffer);
            if (strlen(lineBuffer) == 0) continue;  // ignore empty lines
            if (wasOverflow) return CommandType::CMD_UNKNOWN;
            return matchCommand(lineBuffer);
        }

        // ── Carriage Return (legacy Mac) or \r\n (Windows) ─────
        if (c == '\r') {
            lineBuffer[lineIdx] = '\0';
            lineIdx = 0;
            bool wasOverflow = overflow;
            overflow = false;

            // Consume trailing \n in \r\n pair
            if (Serial.peek() == '\n') {
                Serial.read();
            }

            trim(lineBuffer);
            if (strlen(lineBuffer) == 0) continue;
            if (wasOverflow) return CommandType::CMD_UNKNOWN;
            return matchCommand(lineBuffer);
        }

        // ── Normal character ───────────────────────────────────
        if (!overflow) {
            if (lineIdx < MAX_LINE_LEN) {
                lineBuffer[lineIdx++] = c;
            } else {
                overflow = true;   // line too long → invalid
            }
        }
        // When overflow, silently discard until newline
    }

    return CommandType::CMD_NONE;
}

void serial_respond_ok() {
    Serial.println("OK");
}

void serial_respond_err(const char* reason) {
    Serial.print("ERR ");
    Serial.println(reason);
}
