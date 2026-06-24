/**
 * Agent Status LED Plugin v7 — direct relay control, refined event handling.
 *
 * Improvements over v6:
 *   - 300ms debounce on high-frequency thinking events (message.part.delta)
 *   - 1500ms pending-done delay (prevents flicker on session.idle)
 *   - 500ms suppress window after error (prevents recovery flash)
 *   - subagent depth tracking via tool.execute.before/after (task tool)
 *   - auth_required state mapped from permission.asked / question.asked
 *   - handles 12+ event types for fine-grained session tracking
 *
 * Auto-detects ESP32, spawns relay, writes commands directly to stdin.
 */
import { appendFileSync, mkdirSync, writeFileSync, existsSync, unlinkSync } from "node:fs";
import { join } from "node:path";
import { spawn } from "node:child_process";
import { homedir } from "node:os";

// ── timing constants ───────────────────────────────────────────
const DEBOUNCE_MS = 300;        // throttle high-frequency thinking events
const PENDING_DONE_MS = 1500;   // delay before transitioning exec → idle
const SUPPRESS_MS = 500;        // suppress thinking after error

// ── state ──────────────────────────────────────────────────────
let currentState = "IDLE";
let previousState = "IDLE";
let errorCount = 0;
let errorLocked = false;
let subagentDepth = 0;
let isSessionActive = false;

// ── timers ─────────────────────────────────────────────────────
let debounceTimer = null;
let pendingDoneTimer = null;
let suppressThinkingUntil = 0;
let relay = null;
let portCheckTimer = null;

const stateToCmd = { IDLE: "IDLE", EXECUTING: "EXEC", QUESTION: "QUESTION", ERROR: "ERROR" };

// ── PID file path (set in plugin init) ────────────────────────
let pidFile = null;

// ── helpers ────────────────────────────────────────────────────

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

function cancelPendingDone() {
  if (pendingDoneTimer) { clearTimeout(pendingDoneTimer); pendingDoneTimer = null; }
}

function cancelDebounce() {
  if (debounceTimer) { clearTimeout(debounceTimer); debounceTimer = null; }
}

// ── state transitions ──────────────────────────────────────────

function transitionTo(dir, state, reason) {
  if (state === currentState && state !== "ERROR") return;
  const prev = currentState;
  currentState = state;
  const cmd = stateToCmd[state] || "IDLE";
  sendCmd(cmd);
  log(dir, `→ ${cmd}  (${reason}, prev=${prev})`);
}

/**
 * Mark the session as actively thinking. After the debounce interval
 * with no new events, send EXEC to the relay. Called by fine-grained
 * events (message.part.delta, session.diff, tool hooks, etc.).
 */
function markThinking(dir, source) {
  if (Date.now() < suppressThinkingUntil) {
    log(dir, `[suppressed] ${source}`);
    return;
  }
  // If a pending-done timer is running, cancel it — we're still active.
  cancelPendingDone();
  isSessionActive = true;

  // Debounce: only send EXEC at most every DEBOUNCE_MS.
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  } else {
    // First thinking event in a batch — send EXEC immediately.
    if (currentState !== "EXECUTING") {
      transitionTo(dir, "EXECUTING", source);
    }
  }
  debounceTimer = setTimeout(() => { debounceTimer = null; }, DEBOUNCE_MS);
}

/**
 * Activate the session (dismiss suppress window, cancel pending-done).
 * Returns false if suppress window is still active.
 */
function activateSession(dir, source) {
  if (Date.now() < suppressThinkingUntil) {
    log(dir, `[suppressed] ${source}`);
    return false;
  }
  cancelPendingDone();
  isSessionActive = true;
  return true;
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

function resolveRelayPath(dir) {
  // 1) Project-local scripts/ (for development)
  const localPath = join(dir, "scripts", "agent_relay.py");
  if (existsSync(localPath)) return localPath;

  // 2) User config plugins/ (for production install)
  const userPath = join(homedir(), ".config", "opencode", "plugins", "agent_relay.py");
  if (existsSync(userPath)) return userPath;

  return null;
}

function startRelay(dir) {
  if (relay) return;

  const relayPath = resolveRelayPath(dir);
  if (!relayPath) {
    log(dir, "RELAY NOT FOUND — place agent_relay.py in scripts/ or ~/.config/opencode/plugins/");
    return;
  }

  try {
    log(dir, `RELAY START (${relayPath})`);
    relay = spawn("python", [relayPath], {
      cwd: dir, stdio: ["pipe", "ignore", "pipe"]
    });
    relay.stderr.on("data", d => log(dir, `RELAY: ${d.toString().trim()}`));
    relay.on("exit", () => {
      // Clean up PID file on exit
      if (pidFile) { try { unlinkSync(pidFile); } catch {} }
      relay = null; log(dir, "RELAY EXIT");
    });
    relay.on("error", e => {
      if (pidFile) { try { unlinkSync(pidFile); } catch {} }
      relay = null; log(dir, `RELAY ERROR: ${e.message}`);
    });

    // Write PID file for safe process management
    try {
      mkdirSync(join(dir, ".omo", "monitor"), { recursive: true });
      writeFileSync(join(dir, ".omo", "monitor", "relay.pid"), String(relay.pid), "utf-8");
      pidFile = join(dir, ".omo", "monitor", "relay.pid");
      log(dir, `PID: ${relay.pid}`);
    } catch {}

    // Send initial state after relay boots
    setTimeout(() => sendCmd(currentState === "QUESTION" ? "QUESTION" : stateToCmd[currentState] || "IDLE"), 2000);
  } catch (e) { log(dir, `RELAY SPAWN ERROR: ${e.message}`); }
}

function stopRelay(dir) {
  if (!relay) return;
  try {
    log(dir, "RELAY STOP");
    relay.kill();
    relay = null;
    if (pidFile) { try { unlinkSync(pidFile); } catch {} pidFile = null; }
  } catch {}
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
  log(directory, "PLUGIN LOADED v7 (direct relay + refined events)");
  sendCmd("IDLE");

  await checkAndStart(directory);
  portCheckTimer = setInterval(() => checkAndStart(directory), 3000);

  return {
    // ═══════════════════════════════════════════════════════════════
    //  Core event hook  —  processes OpenCode's internal event stream
    // ═══════════════════════════════════════════════════════════════
    async event({ event }) {
      const type = event.type;
      const props = event.properties || {};
      const data = event.data || {};
      log(directory, `EVENT: ${type} status=${props.status?.type || 'N/A'}`);

      switch (type) {
        // ── session.status: granular busy/idle/retry signals ─
        case "session.status": {
          const s = props.status?.type;
          if (s === "busy") {
            errorCount = 0;
            errorLocked = false;
            activateSession(directory, "session.status:busy");
            transitionTo(directory, "EXECUTING", "session.status:busy");
          } else if (s === "idle") {
            // Start pending-done timer; fine-grained events can cancel it.
            if (isSessionActive) {
              cancelPendingDone();
              if (subagentDepth > 0) {
                log(directory, `[session.status.idle] subagentDepth=${subagentDepth}, deferring done`);
                break;
              }
              pendingDoneTimer = setTimeout(() => {
                if (isSessionActive) return; // activity happened during wait
                pendingDoneTimer = null;
                transitionTo(directory, "IDLE", "pending-done timeout");
              }, PENDING_DONE_MS);
            }
          } else if (s === "retry") {
            errorCount++;
            if (errorCount >= 3) {
              errorLocked = true;
              log(directory, `[error-lock] ${errorCount} retries → LOCKED`);
              transitionTo(directory, "ERROR", "retry lock");
              suppressThinkingUntil = Date.now() + SUPPRESS_MS;
            } else {
              activateSession(directory, "session.status:retry");
              transitionTo(directory, "EXECUTING", `retry ${errorCount}`);
            }
          }
          break;
        }

        // ── session.idle: explicit idle notification ──────────
        case "session.idle":
          if (isSessionActive) {
            cancelPendingDone();
            if (subagentDepth > 0) {
              log(directory, `[session.idle] subagentDepth=${subagentDepth}, deferring done`);
              break;
            }
            isSessionActive = false;
            pendingDoneTimer = setTimeout(() => {
              if (isSessionActive) return;
              pendingDoneTimer = null;
              transitionTo(directory, "IDLE", "session.idle (pending-done)");
            }, PENDING_DONE_MS);
          }
          break;

        // ── session.error: agent encountered an error ─────────
        case "session.error":
          errorCount++;
          cancelPendingDone();
          isSessionActive = false;
          if (errorCount >= 3) {
            errorLocked = true;
            log(directory, `[error-lock] ${errorCount} errors → LOCKED`);
            transitionTo(directory, "ERROR", "error lock");
            suppressThinkingUntil = Date.now() + SUPPRESS_MS;
          } else {
            // Don't escalate to ERROR yet — allow retry.
            // Transition to done via pending-done to show idle.
            log(directory, `[error] count=${errorCount}/3, showing done`);
            pendingDoneTimer = setTimeout(() => {
              if (isSessionActive) return;
              pendingDoneTimer = null;
              transitionTo(directory, "IDLE", "session.error (done)");
            }, PENDING_DONE_MS);
          }
          break;

        // ── permission.asked: system or user permission needed ─
        case "permission.asked":
          if (!activateSession(directory, "permission.asked")) break;
          previousState = currentState;
          transitionTo(directory, "QUESTION", "permission.asked");
          break;

        // ── permission.replied: permission granted/denied ─────
        case "permission.replied":
          markThinking(directory, "permission.replied");
          break;

        // ── question.asked: agent asks user a question ────────
        case "question.asked":
          if (!activateSession(directory, "question.asked")) break;
          previousState = currentState;
          transitionTo(directory, "QUESTION", "question.asked");
          break;

        // ── question.replied: user answered ───────────────────
        case "question.replied":
          markThinking(directory, "question.replied");
          break;

        // ── message.updated: assistant message content changed ─
        case "message.updated":
          if (data.role === "assistant") {
            markThinking(directory, "message.updated:assistant");
          }
          break;

        // ── message.part.updated: streaming chunk ─────────────
        case "message.part.updated":
          markThinking(directory, "message.part.updated");
          break;

        // ── message.part.delta: per-token delta (high freq) ──
        case "message.part.delta":
          markThinking(directory, "message.part.delta");
          break;

        // ── session.diff: file content changed ────────────────
        case "session.diff":
          if (isSessionActive) {
            markThinking(directory, "session.diff");
          }
          break;

        default:
          // Unknown event; log but don't change state.
          break;
      }
    },

    // ═══════════════════════════════════════════════════════════════
    //  Tool hooks  —  track subagent depth via task tool invocations
    // ═══════════════════════════════════════════════════════════════
    "tool.execute.before": async (input) => {
      const tool = input.tool || "?";
      if (tool === "task") {
        subagentDepth++;
        log(directory, `[subagent] depth++ → ${subagentDepth}  (tool=${tool})`);
      }
      if (activateSession(directory, `tool.execute.before:${tool}`)) {
        markThinking(directory, `tool.execute.before:${tool}`);
      }
    },

    "tool.execute.after": async (input) => {
      const tool = input.tool || "?";
      if (tool === "task") {
        subagentDepth = Math.max(0, subagentDepth - 1);
        log(directory, `[subagent] depth-- → ${subagentDepth}  (tool=${tool})`);
      }
      markThinking(directory, `tool.execute.after:${tool}`);
    },

    // ═══════════════════════════════════════════════════════════════
    //  Dispose  —  clean up all timers and subprocesses
    // ═══════════════════════════════════════════════════════════════
    async dispose() {
      if (portCheckTimer) clearInterval(portCheckTimer);
      cancelDebounce();
      cancelPendingDone();
      stopRelay(directory);
      log(directory, "PLUGIN DISPOSED");
    },
  };
};

export default AgentLedPlugin;
