# Openclaw AI Audit

$1,000 AI-readiness audit for SMBs, built on a swarm of Openclaw/Claude sub-agents that pre-fill the questionnaire from a company's public footprint.

See `CLAUDE.md` for product pitch, architecture, framework, and scoring rules.

---

## Run it

### Prereqs

- Python 3.11 + [`uv`](https://github.com/astral-sh/uv) installed
- `ssh` client available on PATH (for the serveo tunnel)
- An Anthropic API key in `agent/.env` as `ANTHROPIC_API_KEY=sk-ant-...`

### Quickstart

```bash
cp agent/.env.example agent/.env      # then edit and paste your ANTHROPIC_API_KEY
cd agent && uv venv && uv pip install -e . && cd ..
./start.sh
```

`start.sh` is idempotent — safe to re-run. It will:

1. Load env vars from `agent/.env`
2. Kill any stale server/tunnel processes
3. Launch FastAPI at `http://127.0.0.1:8787` (logs: `/tmp/openclaw-server.log`)
4. Wait until `/health` returns 200
5. Open a [serveo.net](https://serveo.net) reverse tunnel (logs: `/tmp/openclaw-tunnel.log`)
6. Print the public `https://*.serveo.net` URL and the Vercel frontend URL

### Point the deployed frontend at your tunnel

The static frontend reads its API base from the `?api=` query param and persists it to `localStorage`. After `start.sh` prints the tunnel URL, visit once:

```
https://openclaw-ai-audit-hackathon.vercel.app?api=https://<your-tunnel>.serveo.net
```

From then on the same browser will keep using that backend until you pass a different `?api=` or clear storage.

### Stopping

```bash
./stop.sh
```

Kills the server + tunnel and clears `/tmp/openclaw-*` pidfiles and logs.

### Deploying the static frontend (Vercel)

Docs-only — do **not** run as part of normal dev:

```bash
vercel deploy --prod public/
```

The repo's `vercel.json` is already configured for a static build out of `public/`.

### Troubleshooting

- **Tunnel URL changes on every restart.** Each `./start.sh` run produces a fresh `https://*.serveo.net` hostname — re-hit the Vercel URL with the new `?api=` param.
- **`/health` never becomes 200.** Check `/tmp/openclaw-server.log`. Usually a missing dep (`uv pip install -e .` inside `agent/`) or bad `ANTHROPIC_API_KEY`.
- **Serveo unavailable / blocked.** Local-only fallback for judging:
  ```bash
  python3 -m http.server -d public 3000
  # then open: http://localhost:3000?api=http://localhost:8787
  ```
  Note: the Vercel-hosted frontend won't work against `localhost` — use the local static server for this fallback.
- **Stale server hung on :8787.** `./stop.sh` then `./start.sh` again; `start.sh` will `pkill -f "uvicorn src.server"` itself.
- **`curl https://<tunnel>.serveousercontent.com/health` returns an `opendns.com/phish...` redirect.** Your local DNS (Cisco OpenDNS/Umbrella) classifies the serveo hostname as suspicious and hijacks it **only on this machine**. The public internet — and therefore the Vercel-hosted frontend — will resolve it correctly. To sanity-check locally, bypass DNS:
  ```bash
  SERVEO_IP=$(dig +short @8.8.8.8 <your-tunnel>.serveousercontent.com | head -1)
  curl --resolve <your-tunnel>.serveousercontent.com:443:$SERVEO_IP \
       https://<your-tunnel>.serveousercontent.com/health
  ```
