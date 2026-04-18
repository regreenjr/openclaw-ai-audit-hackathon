#!/usr/bin/env bash
# Openclaw AI Audit — one-shot launcher
# Loads env -> kills stale procs -> starts FastAPI -> opens serveo tunnel -> prints URLs.
# Safe to re-run.

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$ROOT/agent"
ENV_FILE="$AGENT_DIR/.env"
VENV_PY="$AGENT_DIR/.venv/bin/python"

SERVER_LOG="/tmp/openclaw-server.log"
TUNNEL_LOG="/tmp/openclaw-tunnel.log"
SERVER_PID_FILE="/tmp/openclaw.pid"
TUNNEL_PID_FILE="/tmp/openclaw-tunnel.pid"

VERCEL_URL="${VERCEL_URL:-https://openclaw-ai-audit-hackathon.vercel.app}"

say() { printf '[start.sh] %s\n' "$*"; }
die() { printf '[start.sh] ERROR: %s\n' "$*" >&2; exit 1; }

# --- 1. Pre-flight ---------------------------------------------------------
[ -f "$ENV_FILE" ] || die "Missing $ENV_FILE. Copy agent/.env.example and fill ANTHROPIC_API_KEY."
[ -x "$VENV_PY" ] || die "Missing venv at $VENV_PY. Run: cd agent && uv venv && uv pip install -e ."

# --- 2. Load env (export VAR=value — ignore blanks/comments) --------------
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    ''|\#*) continue ;;
    *=*)
      key="${line%%=*}"
      val="${line#*=}"
      # strip surrounding quotes if present
      val="${val%\"}"; val="${val#\"}"
      val="${val%\'}"; val="${val#\'}"
      export "$key=$val"
      ;;
  esac
done < "$ENV_FILE"

[ -n "${ANTHROPIC_API_KEY:-}" ] || die "ANTHROPIC_API_KEY not set after loading $ENV_FILE."
PORT="${PORT:-8787}"

# --- 3. Kill stale processes ---------------------------------------------
say "Killing any existing server/tunnel processes..."
pkill -f "uvicorn src.server" >/dev/null 2>&1 || true
pkill -f "ssh.*serveo" >/dev/null 2>&1 || true
rm -f "$SERVER_PID_FILE" "$TUNNEL_PID_FILE" "$SERVER_LOG" "$TUNNEL_LOG"
sleep 1

# --- 4. Start FastAPI server ---------------------------------------------
say "Starting FastAPI server on :$PORT ..."
cd "$AGENT_DIR" || die "Cannot cd into $AGENT_DIR"
nohup "$VENV_PY" -m uvicorn src.server:app --host 0.0.0.0 --port "$PORT" \
  > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > "$SERVER_PID_FILE"
cd "$ROOT"

# --- 5. Wait for /health -------------------------------------------------
say "Waiting for /health to return 200 (up to 10s)..."
ok=0
for _ in $(seq 1 20); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health" 2>/dev/null || true)"
  if [ "$code" = "200" ]; then ok=1; break; fi
  sleep 0.5
done
[ "$ok" = "1" ] || { tail -n 30 "$SERVER_LOG" >&2; die "Server did not become healthy. See $SERVER_LOG"; }
say "Server healthy (pid $SERVER_PID)."

# --- 6. Start serveo tunnel ---------------------------------------------
say "Starting serveo tunnel ..."
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
  -R 80:localhost:"$PORT" serveo.net > "$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!
echo "$TUNNEL_PID" > "$TUNNEL_PID_FILE"

# --- 7. Poll tunnel log for URL -----------------------------------------
# Serveo's "Forwarding HTTP traffic from <url>" line is what we want.
# The URL is on *.serveousercontent.com (not serveo.net, which is their dashboard).
# ANSI color codes are in the log — strip them before matching.
say "Waiting for tunnel URL (up to 15s)..."
TUNNEL_URL=""
for _ in $(seq 1 30); do
  if [ -s "$TUNNEL_LOG" ]; then
    TUNNEL_URL="$(
      sed -E 's/\x1b\[[0-9;]*m//g' "$TUNNEL_LOG" \
      | grep -Eo 'https://[A-Za-z0-9.-]+\.serveousercontent\.com' \
      | head -n1 || true
    )"
    [ -n "$TUNNEL_URL" ] && break
  fi
  sleep 0.5
done

# --- 8. Summary ----------------------------------------------------------
echo
echo "================================================================"
echo " Openclaw AI Audit — RUNNING"
echo "================================================================"
printf "  Local server : http://127.0.0.1:%s  (pid %s)\n" "$PORT" "$SERVER_PID"
if [ -n "$TUNNEL_URL" ]; then
  printf "  Tunnel URL   : %s  (pid %s)\n" "$TUNNEL_URL" "$TUNNEL_PID"
  printf "  Frontend URL : %s?api=%s\n" "$VERCEL_URL" "$TUNNEL_URL"
else
  printf "  Tunnel URL   : (not detected yet — see %s)\n" "$TUNNEL_LOG"
  printf "  Frontend URL : %s?api=<TUNNEL_URL_WHEN_READY>\n" "$VERCEL_URL"
fi
echo "  Logs         : $SERVER_LOG | $TUNNEL_LOG"
echo "  Stop         : ./stop.sh"
echo "================================================================"
