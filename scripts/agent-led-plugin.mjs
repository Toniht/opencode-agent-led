/**
 * Agent Status LED Plugin v4 — explicit event-driven, no auto-idle.
 * Writes to .omo/agent_state, logs to .omo/agent_events.log.
 */
import { writeFileSync, appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

let currentState = "IDLE";
let previousState = "IDLE";
let errorCount = 0;

function log(dir, msg) {
  try {
    mkdirSync(join(dir, ".omo"), { recursive: true });
    appendFileSync(join(dir, ".omo", "agent_events.log"),
      `${new Date().toISOString()} ${msg}\n`, "utf-8");
  } catch {}
}

function writeState(dir, state) {
  try {
    mkdirSync(join(dir, ".omo"), { recursive: true });
    writeFileSync(join(dir, ".omo", "agent_state"), state, "utf-8");
    if (state !== currentState) {
      log(dir, `STATE: ${currentState} → ${state}`);
    }
    currentState = state;
  } catch (e) {
    log(dir, `ERROR: ${e.message}`);
  }
}

/** @type {import("@opencode-ai/plugin").Plugin} */
const AgentLedPlugin = async ({ directory }) => {
  log(directory, "PLUGIN LOADED v4");
  writeState(directory, "IDLE");

  return {
    async event({ event }) {
      const type = event.type;
      const props = event.properties || {};

      log(directory, `EVENT: ${type} status=${props.status?.type || 'N/A'} session=${(props.sessionID||'').slice(0,12)}`);

      switch (type) {
        case "session.status": {
          const status = props.status?.type;
          if (status === "busy") {
            errorCount = 0;
            writeState(directory, "EXECUTING");
          } else if (status === "idle") {
            writeState(directory, "IDLE");
          } else if (status === "retry") {
            errorCount++;
            writeState(directory, errorCount >= 3 ? "ERROR" : "EXECUTING");
          }
          break;
        }

        case "session.idle":
          writeState(directory, "IDLE");
          break;

        case "session.error":
          errorCount++;
          writeState(directory, "ERROR");
          log(directory, `ERROR #${errorCount}`);
          break;

        case "question.asked":
          previousState = currentState;
          writeState(directory, "QUESTION");
          break;

        case "question.replied":
          writeState(directory, previousState || "IDLE");
          break;

        default:
          break;
      }
    },

    async dispose() {
      log(directory, "PLUGIN DISPOSED");
      writeState(directory, "IDLE");
    },
  };
};

export default AgentLedPlugin;
