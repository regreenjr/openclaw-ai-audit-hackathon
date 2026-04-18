# Gapstone — Session Handoff

Everything a fresh Claude or engineer needs to resume work on this project.
Updated 2026-04-18 end-of-day (Openclaw hackathon).

## Product in one sentence

**Gapstone** is a $1,000 AI maturity audit for SMBs: drop a URL → 11 Claude Agent SDK sub-agents scrape public evidence and predict maturity → user reviews/corrects a pre-filled 20-question quiz → the two signals fuse into a combined report with scorecard, evidence-cited gaps, 90-day roadmap, Porter's Value Chain plays, vendor shortlist, and (for regulated industries) compliance scan. Lead-gens a $50k–$500k implementation engagement.

## Status: shipped + live

- **Repo:** https://github.com/regreenjr/openclaw-ai-audit-hackathon (branch `main`)
- **Live demo:** https://openclaw-ai-audit-hackathon.vercel.app
- **All 4 core tasks complete** (Supabase, Quiz UI, Combined Report, Vendor/Regulatory sub-agents)
- **11 sub-agents** running: researcher + 5 specialists (D1–D5) + 5 per-dim critics (parallel) + synthesizer + value_chain_strategist + vendor_recs + (gated) regulatory_scan + combiner

## Architecture

```
┌──────────────────────────────┐    cloudflared tunnel    ┌───────────────────────────┐
│ Frontend (Vercel static)     │  ←───────────────────→  │ Backend (local FastAPI)   │
│ public/index.html            │  *.trycloudflare.com    │ agent/src/server.py:8787  │
│ Vanilla JS + Tailwind CDN    │                          │ Claude Agent SDK (Python) │
│ SSE streaming, localStorage  │                          │                            │
└──────────────────────────────┘                          └──────────┬────────────────┘
                                                                      │
                                                  ┌───────────────────┴───┐
                                                  ▼                        ▼
                                        ┌──────────────────┐   ┌──────────────────┐
                                        │ Supabase         │   │ Anthropic API    │
                                        │ (project:        │   │ Sonnet 4.6 fast  │
                                        │  gapstone)       │   │ Opus 4.7 for     │
                                        │ audit_sessions   │   │   critic (unused,│
                                        │ single table     │   │   now Sonnet)    │
                                        └──────────────────┘   └──────────────────┘
```

### Pipeline phases (3-4 minutes end-to-end)

1. **Scrape audit** (~3 min) — `POST /api/audit-stream`
   - Researcher fetches 5 pages in parallel (max_turns=5)
   - 5 Specialists parallel (D1–D5) with dimension-scoped framework cells + questions
   - Preliminary scorecard emits IMMEDIATELY after specialists (heatmap appears ~2:20)
   - 5 per-dim critics run in parallel with synthesizer + value_chain (all 3 concurrent)
   - Final scorecard re-emits if critic revises
2. **Quiz** (user takes 2 min) — `POST /api/quiz/{session_id}`
3. **Combined report** (~100–160s) — `POST /api/combined-report/{session_id}/stream`
   - `_merge_scraped_and_quiz()` — user-authoritative; "Don't know" falls back to scraped + discovery flag
   - Re-scores
   - synthesizer + value_chain + vendor_recs + regulatory_scan (gated) all parallel

### Supabase schema (single table)

```
audit_sessions
├── id (uuid, pk)
├── company_url, company_name, screener (jsonb), contextual (jsonb)
├── scraped_evidence, scraped_answers, scraped_scorecard, scraped_narrative, scraped_value_chain_plays
├── quiz_answers, quiz_submitted_at
├── combined_scorecard, combined_narrative, combined_value_chain_plays
├── combined_vendor_recs, combined_regulatory_scan
└── status (created → scraped → quizzed → reported)
```

## Repo layout

```
openclaw-ai-audit-hackathon/
├── CLAUDE.md                  # brief for future Claudes
├── HANDOFF.md                 # ← this file
├── DEMO.md                    # pitch + 2-min demo script + criteria-mapping table
├── PITCH.md                   # 60s drive-by pitch
├── README.md                  # run instructions
├── start.sh                   # spawns server + cloudflared tunnel, prints URLs
├── stop.sh                    # kills both
├── sync-tunnel.sh             # updates DEFAULT_API_URL in index.html + redeploys to Vercel
├── demo-meridian.sh           # curl-streams an Anthropic audit (best real-data demo)
├── demo-meridian-real.sh      # Meridian Tax & Advisory persona (thin-evidence demo)
├── framework.json             # 5×4 maturity framework (L1–L4 for D1–D5)
├── questions.json             # 4 screener + 20 scored questions
├── planning/                  # premortem, hour-budget, framework/questions long-form
├── public/
│   ├── index.html             # entire frontend (vanilla + Tailwind CDN) — includes
│   │                          #   DEFAULT_API_URL baked in, verifyApiUrl health check,
│   │                          #   quiz + combining + combined-report UI
│   └── questions.json         # copy served by static host
├── api/audit.js               # Vercel serverless fallback (deterministic, demo-safe)
└── agent/
    ├── pyproject.toml         # claude-agent-sdk, fastapi, supabase, httpx, bs4, sse-starlette
    ├── .env                   # ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_KEY (gitignored)
    ├── .env.example
    └── src/
        ├── server.py          # FastAPI app — /api/audit-stream, /api/quiz/{id},
        │                      #   /api/combined-report/{id}(/stream), /api/session/{id}, /health
        ├── orchestrator.py    # run_audit, run_combined_report, all sub-agent fns,
        │                      #   _merge_scraped_and_quiz, regulatory_applies gate
        ├── prompts.py         # system prompts per sub-agent
        ├── tools.py           # custom MCP server with fetch_url tool
        ├── scoring.py         # deterministic scoring (per-dim mean, top-5 gaps, target levels)
        ├── db.py              # Supabase client + create/update/get helpers
        ├── loaders.py         # loads framework.json / questions.json
        └── events.py          # AuditEvent + EventBus for SSE streaming
```

## How to run (fresh machine)

```bash
# One-time setup
brew install cloudflared uv
cd ~/openclaw-ai-audit-hackathon
cd agent && uv venv --python 3.11 && uv pip install -e . && cd ..
cp agent/.env.example agent/.env
# Edit agent/.env: paste ANTHROPIC_API_KEY. SUPABASE_URL/KEY are already documented in handoff.
```

```bash
# Every session
./start.sh                 # spawns server + cloudflared tunnel, prints URLs
./sync-tunnel.sh           # syncs new tunnel URL to Vercel (only needed if re-running)
# ...demo / develop...
./stop.sh
```

## Credentials (rotate these post-hackathon)

- **ANTHROPIC_API_KEY:** in `agent/.env` (NOT committed). Pasted in chat on 2026-04-18; should be rotated at console.anthropic.com.
- **Supabase project `gapstone`:**
  - URL: `https://svorjlngtojetopzysck.supabase.co`
  - Anon key is in `agent/.env`. Permissive RLS (`using (true) with check (true)`) for hackathon; tighten before prod.
  - Org: `Solving Alpha` (wzxgpyzoucwgendudmuc), us-east-1
- **Vercel project:** `openclaw-ai-audit-hackathon` under `solvingalphamarketing-2164`. CLI already linked (`.vercel/` gitignored).

## Hard lessons from today (don't rediscover these)

1. **serveo's TLS cert is self-signed and Chrome rejects it** (`net::ERR_CERT_AUTHORITY_INVALID`) — curl tests pass because curl has a separate trust store. Use **cloudflared quick tunnels** instead. `start.sh` already does this.
2. **sse-starlette uses `\r\n\r\n` frame delimiters** (SSE spec), not `\n\n`. Frontend parser must normalize CRLF → LF before splitting. Already handled in `public/index.html` streamAudit / streamCombinedReport.
3. **Vercel CDN edge caches HTML** (`x-vercel-cache: HIT`, age up to ~600s). After `vercel deploy --prod`, user might still see stale HTML on hard refresh. Bust via `?nocache=<ts>` or wait.
4. **HTML5 `<input type="url">` rejects bare domains** (blocks `acme.com`). Use `type="text"` + `inputmode="url"` + JS `normalizeUrl()` helper. Fixed.
5. **wait_for in chrome-devtools MCP matches hidden DOM text**. Don't list strings that exist in hidden elements — you'll get false positives. Use runtime-unique strings only.
6. **Claude Agent SDK venv from `uv venv` doesn't include pip.** Must `uv pip install` not `./venv/bin/pip install`.
7. **DNS on this Mac (OpenDNS/Umbrella)** classifies `*.serveousercontent.com` as phishing. Doesn't affect end users on other networks but blocked local curls. Non-issue with cloudflared.
8. **Model IDs that work:** `claude-sonnet-4-6`, `claude-opus-4-7`, `claude-sonnet-4-5`, `claude-opus-4-1`. Currently we use Sonnet 4.6 for all sub-agents (critic switched from Opus 4.7 for speed).
9. **Backend cannot run on Vercel functions** — Claude Agent SDK spawns a `claude` CLI subprocess that can't live in Vercel's serverless model. Cloudflared tunnel to a local/VM process is the current path.
10. **Quiz pre-fill uses pre-critic specialist data** (captured from `specialist.result` SSE events). Frontend has a `hydrateScrapedAnswersFromServer()` fallback that fetches merged post-critic data from `/api/session/{id}` — but it only fills missing keys, doesn't overwrite. Minor UX polish opportunity: change to "always prefer server data" so critic revisions show up in quiz.

## Open items / post-demo

- **Move backend off local+tunnel to a real host** (Railway/Fly.io recommended; Vercel can't host the subprocess-spawning agent model). Removes the cert/tunnel fragility permanently.
- **Tighten Supabase RLS** — currently permissive `(true)` policy. Needs per-session ownership model before real users.
- **Add auth / payment gate** at the $1k CTA. Currently just a dead anchor.
- **PDF export** via `window.print()` works but the @media print stylesheet could use a pass (some dark gradients bleed through on some printers).
- **Performance:** full combined pipeline is ~2.5–3 min. Tight for live demo attention — first scorecard renders at ~2:20 (preliminary) which is OK. Haiku for specialists could cut further but with quality risk.
- **Vendor search is knowledge-only** (no web_search tool) — Mkal72's TS port used Anthropic's web_search_20260209 tool; we skipped for simplicity. Could wire our fetch_url MCP to search providers if needed.
- **Delta UX** deliberately skipped: user said unsure about surfacing "agents said L3, you said L1" style diffs. Code captures `agreed_with_agent` boolean per answer already.

## Demo flow (for judges)

1. Open `https://openclaw-ai-audit-hackathon.vercel.app`
2. Type `anthropic.com` (best real data) — Industry: `AI research` — Priority: `accelerating safety research outputs`
3. Click **Launch Agent Swarm** — narrate the 11 sub-agents lighting up
4. At ~2:20 the preliminary scorecard lands. Show heatmap + Top 5 gaps with evidence citations.
5. Click **Continue to Self-Assessment** — walk through the confidence-tiered pre-fills (emerald = strong evidence, sky = suggested, amber = discovery needed)
6. Click **Generate Combined Report** — narrate the combiner fusing signals, re-scoring, and running 4 sub-agents in parallel (synth, value_chain, vendor_recs, regulatory_scan)
7. Final combined report appears with vendor shortlists (real products, real pricing) and Porter's Value Chain plays
8. Click **Download PDF** — print-friendly 4–5 page report
9. Close with the $1k Strategy Call CTA

## Judging criteria (from DEMO.md)

| Criterion | Feature | Evidence |
|---|---|---|
| **Creativity** | Predict-then-validate hybrid: agents argue with other agents via per-dim critics; user confirms/overrides | `orchestrator.py:178-211` (run_critic), critic.challenge events |
| **Works** | Live end-to-end against public company; SSE streaming; deterministic scoring math outside LLM | `orchestrator.py:264-323` (run_audit), `scoring.py` pure Python |
| **Practical utility** | $1,000 audit replaces $50k Deloitte. Meridian persona = exact buyer | CLAUDE.md:11-13 (persona), 6-page PDF scope |
| **Technical depth** | 11 isolated `query()` calls with different system prompts + models; `asyncio.gather` parallelism; custom MCP tool server for researcher; Supabase persistence | `orchestrator.py` imports, MODEL_FAST/DEEP tiering |

## Recent commit history (last 10 on main)

```
c117a9e  fix: swap serveo → cloudflared (browser-trusted TLS cert)
a7b0ee1  feat: bake DEFAULT_API_URL into frontend + sync-tunnel.sh helper
f25f0ba  fix: detect stale tunnel URL on load, auto-clear + prompt
fa7db53  feat: port vendor-recs + regulatory-scan agents from Mkal72
3891614  feat: combined report agent — fuses scraped evidence + user quiz answers
fb7d145  feat: add Supabase persistence + quiz self-assessment flow (rebrand to Gapstone)
0cb8a60  fix: accept any URL format on input (bare domain, www, http, https)
ec8636e  perf: parallelize critic by dimension + run critic/synth/vcs concurrently
19e0c60  fix: normalize CRLF SSE delimiters in frontend stream parser
1d59c74  feat: ship multi-agent AI maturity audit with Openclaw sub-agents
```

## What to do first in the next session

1. `cd ~/openclaw-ai-audit-hackathon && cat HANDOFF.md` (this file)
2. `./start.sh` — boot server + tunnel
3. Run `./demo-meridian.sh` to smoke-test end-to-end
4. If tunnel URL changed, `./sync-tunnel.sh` to refresh Vercel
5. Read `DEMO.md` for the demo script

If the demo is done and you want to keep building, the priority list is in "Open items / post-demo" above — Railway backend deploy is the highest-leverage next move.
