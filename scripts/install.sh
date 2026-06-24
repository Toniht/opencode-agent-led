#!/usr/bin/env bash
# Agent Status LED — One-Command Install (Linux/macOS)
# Usage: bash scripts/install.sh
#        bash scripts/install.sh --plugin-only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGINS_DIR="$HOME/.config/opencode/plugins"
CONFIG_FILE="$HOME/.config/opencode/opencode.jsonc"
SKIP_FLASH=0

[[ "${1:-}" == "--plugin-only" || "${1:-}" == "--skip-flash" ]] && SKIP_FLASH=1

echo
echo "╔══════════════════════════════════════════════╗"
echo "║   Agent Status LED — Installer v2           ║"
echo "╚══════════════════════════════════════════════╝"
echo

# ── Step 1: Python deps ───────────────────
echo "[1/4] Python dependencies..."
command -v python3 >/dev/null 2>&1 || { echo "  [FAIL] Python 3 required"; exit 1; }
python3 -c "import serial" >/dev/null 2>&1 || {
    echo "  Installing pyserial..."
    python3 -m pip install pyserial -q
}
echo "  [OK]   Python + pyserial"

# ── Step 2: Detect ESP32 + Flash ──────────
if [[ $SKIP_FLASH -eq 1 ]]; then
    echo "[2/4] Skip firmware (--plugin-only)"
else
    echo "[2/4] ESP32 detection..."
    ESP_PORT=$(python3 -c "
import serial.tools.list_ports
ports = list(serial.tools.list_ports.comports())
esp = [p.device for p in ports if p.vid in (0x303A, 0x10C4, 0x1A86) or 'CH34' in (p.description or '') or 'ESP' in (p.description or '')]
print(esp[0] if esp else '')
" 2>/dev/null)

    if [[ -z "$ESP_PORT" ]]; then
        echo "  [SKIP] No ESP32 found — connect USB and re-run"
    else
        echo "  [OK]   Found: $ESP_PORT"

        command -v pio >/dev/null 2>&1 || {
            echo "  Installing PlatformIO..."
            python3 -m pip install platformio -q 2>/dev/null
        }

        echo "  Flashing $ESP_PORT..."
        cd "$PROJECT_DIR"
        if pio run -t upload --upload-port "$ESP_PORT" 2>&1 | grep -q "SUCCESS"; then
            echo "  [OK]   Firmware flashed"
        else
            echo "  [FAIL] Flash failed — check USB connection"
        fi
    fi
fi

# ── Step 3: User-level plugin ─────────────
echo "[3/4] Plugin install..."
mkdir -p "$PLUGINS_DIR"
cp -f "$SCRIPT_DIR/agent-led-plugin.mjs" "$PLUGINS_DIR/agent-led-plugin.mjs"
cp -f "$SCRIPT_DIR/agent_relay.py" "$PLUGINS_DIR/agent_relay.py"
echo "  [OK]   Copied to $PLUGINS_DIR"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo '{ "plugin": ["./plugins/agent-led-plugin.mjs"] }' > "$CONFIG_FILE"
elif ! grep -q "agent-led-plugin" "$CONFIG_FILE" 2>/dev/null; then
    # Append to existing plugin array
    python3 -c "
import json
with open('$CONFIG_FILE', 'r') as f:
    c = json.load(f)
c['plugin'] = list(c.get('plugin', [])) + ['./plugins/agent-led-plugin.mjs']
with open('$CONFIG_FILE', 'w') as f:
    json.dump(c, f, indent=2)
" 2>/dev/null || echo "  [WARN] Could not auto-register plugin. Add './plugins/agent-led-plugin.mjs' to $CONFIG_FILE manually."
fi
echo "  [OK]   Registered in opencode.jsonc"

# ── Step 4: Verify ────────────────────────
echo "[4/4] Verify..."
ERR=0
[[ -f "$PLUGINS_DIR/agent-led-plugin.mjs" ]] || { echo "  [MISS] plugin"; ERR=$((ERR+1)); }
[[ -f "$PLUGINS_DIR/agent_relay.py" ]]      || { echo "  [MISS] relay";  ERR=$((ERR+1)); }
grep -q "agent-led-plugin" "$CONFIG_FILE" 2>/dev/null || { echo "  [MISS] config"; ERR=$((ERR+1)); }
[[ $ERR -eq 0 ]] && echo "  [OK]   All checks passed" || echo "  [$ERR issue(s)]"

echo
echo "╔══════════════════════════════════════════════╗"
echo "║  Done! Restart OpenCode to activate.        ║"
echo "║  Test: node scripts/test-publisher.mjs      ║"
echo "╚══════════════════════════════════════════════╝"
