#!/usr/bin/env bash
# Openclaw AI Audit — stop server + tunnel, clean up tmp files.
set -u

SERVER_LOG="/tmp/openclaw-server.log"
TUNNEL_LOG="/tmp/openclaw-tunnel.log"
SERVER_PID_FILE="/tmp/openclaw.pid"
TUNNEL_PID_FILE="/tmp/openclaw-tunnel.pid"

say() { printf '[stop.sh] %s\n' "$*"; }

kill_pidfile() {
  local f="$1" label="$2"
  if [ -f "$f" ]; then
    pid="$(cat "$f" 2>/dev/null || true)"
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 0.3
      kill -9 "$pid" 2>/dev/null || true
      say "Killed $label (pid $pid)."
    fi
    rm -f "$f"
  fi
}

kill_pidfile "$SERVER_PID_FILE" "server"
kill_pidfile "$TUNNEL_PID_FILE" "tunnel"

# Belt-and-suspenders: pattern kills
pkill -f "uvicorn src.server" >/dev/null 2>&1 && say "Killed stray uvicorn." || true
pkill -f "ssh.*serveo"        >/dev/null 2>&1 && say "Killed stray serveo ssh." || true

rm -f "$SERVER_LOG" "$TUNNEL_LOG"
say "Cleaned tmp logs and pidfiles. Done."
