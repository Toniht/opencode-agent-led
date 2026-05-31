/**
 * Agent Status LED Plugin v5 — auto-start monitor on ESP32 detect.
 * Writes to .omo/monitor/agent_state, auto-launches bridge+relay pipeline.
 */
import { writeFileSync, appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { spawn } from "node:child_process";

let currentState = "IDLE";
let previousState = "IDLE";
let errorCount = 0;
let pipeline = null;       // bridge+relay child process
let portCheckTimer = null;

function log(dir, msg) {
  try {
    mkdirSync(join(dir, ".omo", "monitor"), { recursive: true });
    appendFileSync(join(dir, ".omo", "monitor", "agent_events.log"),
      `${new Date().toISOString()} ${msg}\n`, "utf-8");
  } catch {}
}

function writeState(dir, state) {
  try {
    mkdirSync(join(dir, ".omo", "monitor"), { recursive: true });
    writeFileSync(join(dir, ".omo", "monitor", "agent_state"), state, "utf-8");
    if (state !== currentState) {
      log(dir, `STATE: ${currentState} → ${state}`);
    }
    currentState = state;
  } catch (e) {
    log(dir, `ERROR: ${e.message}`);
  }
}

function detectESP32(dir) {
  return new Promise((resolve) => {
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

function startPipeline(dir) {
  if (pipeline) return;
  try {
    log(dir, "PIPELINE START");
    const bridge = spawn("python", [join(dir, "scripts", "agent_bridge.py"), "--interval", "0.3", "--stats"], { cwd: dir, stdio: ["ignore", "pipe", "inherit"] });
    const relay = spawn("python", [join(dir, "scripts", "agent_relay.py"), "-v"], { cwd: dir, stdio: [bridge.stdout, "inherit", "inherit"] });
    bridge.stdout.destroy();
    pipeline = { bridge, relay };
    bridge.on("exit", () => { if (pipeline) log(dir, "BRIDGE EXIT"); });
    relay.on("exit", () => { pipeline = null; log(dir, "RELAY EXIT"); });
  } catch (e) { log(dir, `PIPELINE ERROR: ${e.message}`); }
}

function stopPipeline(dir) {
  if (!pipeline) return;
  try {
    log(dir, "PIPELINE STOP");
    pipeline.bridge.kill();
    pipeline.relay.kill();
    pipeline = null;
  } catch {}
}

async function checkAndStart(dir) {
  const port = await detectESP32(dir);
  if (port && !pipeline) {
    log(dir, `ESP32 FOUND: ${port} → starting pipeline`);
    startPipeline(dir);
  } else if (!port && pipeline) {
    log(dir, "ESP32 GONE → stopping pipeline");
    stopPipeline(dir);
  }
}

/** @type {import("@opencode-ai/plugin").Plugin} */
const AgentLedPlugin = async ({ directory }) => {
  log(directory, "PLUGIN LOADED v5 (auto-monitor)");
  writeState(directory, "IDLE");

  // Check immediately, then every 3 seconds
  await checkAndStart(directory);
  portCheckTimer = setInterval(() => checkAndStart(directory), 3000);

  return {
    async event({ event }) {
      const type = event.type;
      const props = event.properties || {};
      log(directory, `EVENT: ${type} status=${props.status?.type || 'N/A'} session=${(props.sessionID||'').slice(0,12)}`);

      switch (type) {
        case "session.status": {
          const s = props.status?.type;
          if (s === "busy") { errorCount = 0; writeState(directory, "EXECUTING"); }
          else if (s === "idle") { writeState(directory, "IDLE"); }
          else if (s === "retry") { errorCount++; writeState(directory, errorCount >= 3 ? "ERROR" : "EXECUTING"); }
          break;
        }
        case "session.idle": writeState(directory, "IDLE"); break;
        case "session.error": errorCount++; writeState(directory, "ERROR"); log(directory, `ERROR #${errorCount}`); break;
        case "question.asked": previousState = currentState; writeState(directory, "QUESTION"); break;
        case "question.replied": writeState(directory, previousState || "IDLE"); break;
        default: break;
      }
    },

    async dispose() {
      if (portCheckTimer) clearInterval(portCheckTimer);
      stopPipeline(directory);
      log(directory, "PLUGIN DISPOSED");
      writeState(directory, "IDLE");
    },
  };
};

export default AgentLedPlugin;
