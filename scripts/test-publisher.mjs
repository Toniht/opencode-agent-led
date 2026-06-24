/**
 * Test Publisher — Simulates OpenCode agent state transitions for LED testing.
 *
 * Sends state commands to agent_relay.py via stdin pipe.
 * Usage:
 *   node scripts/test-publisher.mjs                     # auto-detect ESP32
 *   node scripts/test-publisher.mjs --port COM4         # explicit port
 *   node scripts/test-publisher.mjs --dry-run           # no serial, log only
 *   node scripts/test-publisher.mjs --sequence quick    # fast test (short delays)
 *   node scripts/test-publisher.mjs --sequence full     # full test (default)
 *   node scripts/test-publisher.mjs --loop 3            # repeat test N times
 */

import { spawn } from "node:child_process";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const RELAY_PATH = resolve(__dirname, "agent_relay.py");

// ── sequences ──────────────────────────────────────────────────

const QUICK_SEQ = [
  ["IDLE",    800],
  ["EXEC",   1200],
  ["QUESTION",1500],
  ["EXEC",   1000],
  ["IDLE",    800],
  ["ERROR",  1200],
  ["IDLE",   1000],
];

const FULL_SEQ = [
  ["IDLE",   2000],
  ["EXEC",   3000],
  ["QUESTION",3000],
  ["EXEC",   2000],
  ["IDLE",   2000],
  ["ERROR",  2000],
  ["IDLE",   2000],
  ["EXEC",   1500],
  ["IDLE",   1000],
];

// ── args ───────────────────────────────────────────────────────

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { port: null, dryRun: false, sequence: "full", loop: 1 };
  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--port": case "-p": opts.port = args[++i]; break;
      case "--dry-run": opts.dryRun = true; break;
      case "--sequence": opts.sequence = args[++i]; break;
      case "--loop": opts.loop = parseInt(args[++i], 10) || 1; break;
    }
  }
  return opts;
}

// ── ESP32 auto-detect ──────────────────────────────────────────

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

// ── relay spawn ────────────────────────────────────────────────

function startRelay(port, dryRun) {
  const pyArgs = [RELAY_PATH];
  if (dryRun) pyArgs.push("--dry-run");
  else if (port) pyArgs.push("--port", port);
  pyArgs.push("-v");

  console.log(`[test-publisher] starting agent_relay.py ${pyArgs.slice(1).join(" ")}`);

  const relay = spawn("python", pyArgs, {
    cwd: ROOT,
    stdio: ["pipe", "inherit", "inherit"],
  });

  relay.on("exit", code => {
    console.log(`[test-publisher] relay exited (code=${code})`);
    process.exit(code ?? 0);
  });

  relay.on("error", e => {
    console.error(`[test-publisher] relay spawn error: ${e.message}`);
    process.exit(1);
  });

  return relay;
}

// ── state sender ───────────────────────────────────────────────

function send(relay, cmd, delay) {
  return new Promise(resolve => {
    console.log(`  → ${cmd}  (wait ${delay}ms)`);
    if (relay.stdin && !relay.killed) {
      try { relay.stdin.write(cmd + "\n"); } catch {}
    }
    setTimeout(resolve, delay);
  });
}

// ── main ───────────────────────────────────────────────────────

async function main() {
  const opts = parseArgs();
  const seq = opts.sequence === "quick" ? QUICK_SEQ : FULL_SEQ;
  const loops = Math.max(1, opts.loop);

  console.log("╔══════════════════════════════════════════╗");
  console.log("║  Agent Status LED — Test Publisher      ║");
  console.log("╠══════════════════════════════════════════╣");
  console.log(`║  Sequence: ${opts.sequence.padEnd(14)}   Loops: ${String(loops).padEnd(10)}║`);
  console.log(`║  Steps:   ${String(seq.length).padEnd(14)}   Dry run: ${String(opts.dryRun).padEnd(10)}║`);
  console.log("╚══════════════════════════════════════════╝\n");

  let port = opts.port;
  if (!opts.dryRun && !port) {
    port = await detectESP32();
    if (!port) {
      console.error("[test-publisher] No ESP32 detected. Use --port or --dry-run.");
      process.exit(1);
    }
    console.log(`[test-publisher] auto-detected ESP32: ${port}\n`);
  }

  const relay = startRelay(port, opts.dryRun);

  // Wait for relay to boot (2s)
  await new Promise(r => setTimeout(r, 2000));

  for (let l = 1; l <= loops; l++) {
    if (loops > 1) console.log(`\n── Loop ${l}/${loops} ──\n`);
    for (const [cmd, delay] of seq) {
      await send(relay, cmd, delay);
    }
  }

  console.log("\n[test-publisher] sequence complete. Press Ctrl+C to exit.");
}

main().catch(e => { console.error(e); process.exit(1); });
