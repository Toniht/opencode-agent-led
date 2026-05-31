/**
 * Agent Status LED Plugin v6 — direct relay control, no bridge pipe.
 * Auto-detects ESP32, spawns relay, writes commands directly to stdin.
 */
import { writeFileSync, appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { spawn } from "node:child_process";

let currentState = "IDLE";
let previousState = "IDLE";
let errorCount = 0;
let relay = null;
let portCheckTimer = null;

const stateToCmd = { IDLE: "IDLE", EXECUTING: "EXEC", QUESTION: "QUESTION", ERROR: "ERROR" };

function log(dir, msg) {
  try {
    mkdirSync(join(dir, ".omo", "monitor"), { recursive: true });
    appendFileSync(join(dir, ".omo", "monitor", "agent_events.log"),
      `${new Date().toISOString()} ${msg}\n`, "utf-8");
  } catch {}
}

function sendCmd(cmd) {
  if (relay && relay.stdin && !relay.killed) {
    try { relay.stdin.write(cmd + "\n"); } catch {}
  }
}

function detectESP32() {
  return new Promise(resolve => {
    const py = spawn("python", ["-c",
      "import serial.tools.list_ports; ports=list(serial.tools.list_ports.comports());" +
      "esp=[p.device for p in ports if p.vid in (0x303A,0x10C4,0x1A86) or 'CH34' in (p.description or '') or 'ESP' in (p.description or '')];" +
      "print(esp[0] if esp else '')"
    ], { stdio: ["ignore", "pipe", "ignore"] });
    let out = "";
    py.stdout.on("data", d => out += d.toString());
    py.on("close", () => resolve(out.trim()));
    py.on("error", () => resolve(""));
  });
}

function startRelay(dir) {
  if (relay) return;
  try {
    log(dir, "RELAY START");
    relay = spawn("python", [join(dir, "scripts", "agent_relay.py")], {
      cwd: dir, stdio: ["pipe", "ignore", "pipe"]
    });
    relay.stderr.on("data", d => log(dir, `RELAY: ${d.toString().trim()}`));
    relay.on("exit", () => { relay = null; log(dir, "RELAY EXIT"); });
    relay.on("error", e => { relay = null; log(dir, `RELAY ERROR: ${e.message}`); });
    // Send initial state after relay boots
    setTimeout(() => sendCmd(currentState === "QUESTION" ? "QUESTION" : stateToCmd[currentState] || "IDLE"), 2000);
  } catch (e) { log(dir, `RELAY SPAWN ERROR: ${e.message}`); }
}

function stopRelay(dir) {
  if (!relay) return;
  try { log(dir, "RELAY STOP"); relay.kill(); relay = null; } catch {}
}

async function checkAndStart(dir) {
  const port = await detectESP32();
  if (port && !relay) {
    log(dir, `ESP32 FOUND: ${port}`);
    startRelay(dir);
  } else if (!port && relay) {
    log(dir, "ESP32 GONE");
    stopRelay(dir);
  }
}

/** @type {import("@opencode-ai/plugin").Plugin} */
const AgentLedPlugin = async ({ directory }) => {
  log(directory, "PLUGIN LOADED v6 (direct relay)");
  sendCmd("IDLE");

  await checkAndStart(directory);
  portCheckTimer = setInterval(() => checkAndStart(directory), 3000);

  return {
    async event({ event }) {
      const type = event.type;
      const props = event.properties || {};
      log(directory, `EVENT: ${type} status=${props.status?.type || 'N/A'}`);

      switch (type) {
        case "session.status": {
          const s = props.status?.type;
          if (s === "busy") { errorCount = 0; currentState = "EXECUTING"; sendCmd("EXEC"); log(directory, "→ EXEC"); }
          else if (s === "idle") { currentState = "IDLE"; sendCmd("IDLE"); log(directory, "→ IDLE"); }
          else if (s === "retry") { errorCount++; currentState = errorCount >= 3 ? "ERROR" : "EXECUTING"; sendCmd(currentState === "ERROR" ? "ERROR" : "EXEC"); }
          break;
        }
        case "session.idle": currentState = "IDLE"; sendCmd("IDLE"); break;
        case "session.error": errorCount++; currentState = "ERROR"; sendCmd("ERROR"); break;
        case "question.asked": previousState = currentState; currentState = "QUESTION"; sendCmd("QUESTION"); break;
        case "question.replied": currentState = previousState || "IDLE"; sendCmd(stateToCmd[currentState] || "IDLE"); break;
      }
    },

    async dispose() {
      if (portCheckTimer) clearInterval(portCheckTimer);
      stopRelay(directory);
      log(directory, "PLUGIN DISPOSED");
    },
  };
};

export default AgentLedPlugin;
