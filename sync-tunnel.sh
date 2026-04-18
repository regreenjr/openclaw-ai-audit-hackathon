#!/usr/bin/env bash
# sync-tunnel.sh — update public/index.html's DEFAULT_API_URL to the current
# running serveo tunnel, then re-deploy to Vercel prod.
#
# Run this after ./start.sh when the tunnel URL has changed.

set -euo pipefail

cd "$(dirname "$0")"

TUNNEL_LOG="/tmp/openclaw-tunnel.log"
if [[ ! -f "$TUNNEL_LOG" ]]; then
  echo "[sync-tunnel] ERROR: $TUNNEL_LOG not found. Run ./start.sh first." >&2
  exit 1
fi

# Extract the most recent tunnel URL from the tunnel log.
# Supports both cloudflared (*.trycloudflare.com) and legacy serveo (*.serveousercontent.com).
TUNNEL_URL="$(
  { grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" || true; } | tail -1
)"
if [[ -z "$TUNNEL_URL" ]]; then
  TUNNEL_URL="$(
    { grep -oE 'https://[a-f0-9]+-[0-9]+-[0-9]+-[0-9]+-[0-9]+\.serveousercontent\.com' "$TUNNEL_LOG" || true; } | tail -1
  )"
fi
if [[ -z "$TUNNEL_URL" ]]; then
  echo "[sync-tunnel] ERROR: no tunnel URL found in $TUNNEL_LOG" >&2
  exit 1
fi

echo "[sync-tunnel] Current tunnel URL: $TUNNEL_URL"

INDEX="public/index.html"
if ! grep -q '^\s*const DEFAULT_API_URL = ' "$INDEX"; then
  echo "[sync-tunnel] ERROR: DEFAULT_API_URL line not found in $INDEX" >&2
  exit 1
fi

# In-place update — macOS sed -i requires an empty suffix arg
sed -i '' "s|^\( *const DEFAULT_API_URL = \"\)[^\"]*|\1${TUNNEL_URL}|" "$INDEX"

CURRENT="$(grep -oE '^ *const DEFAULT_API_URL = "[^"]*"' "$INDEX" | head -1)"
echo "[sync-tunnel] Updated index.html: $CURRENT"

echo "[sync-tunnel] Deploying to Vercel prod..."
if ! command -v vercel >/dev/null 2>&1; then
  echo "[sync-tunnel] vercel CLI not found on PATH. Skipping deploy." >&2
  exit 0
fi
vercel deploy --prod --yes 2>&1 | tail -5

echo
echo "================================================================"
echo " Synced. Share this URL:"
echo "   https://openclaw-ai-audit-hackathon.vercel.app"
echo " (DEFAULT_API_URL now baked in — no ?api= param required)"
echo "================================================================"
