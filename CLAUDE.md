# AI Audit — Openclaw hackathon build

$1,000 AI audit for SMBs, with Openclaw sub-agents as the headline differentiator.

## Pitch

Drop your URL → multi-agent swarm scrapes your public footprint → predicts your readiness across 20 questions with cited evidence → you review/override the pre-filled questionnaire in 60 seconds → deterministic scoring → 6-page PDF gap analysis → book a 30-minute expert call.

**Why this wins:** competitors will ship *either* a self-report form *or* a scraping tool. We ship the hybrid — agents hypothesize, human validates. That's the novel multi-agent behavior.

## Demo persona (for screenshot run)

**Meridian Tax & Advisory** — 28-person boutique accounting firm, Austin TX. COO fills out the audit. Priority function: client document intake & tax preparation. Tooling: QuickBooks Online, Excel, Outlook, shared drives. No AI policy. Two staff using personal ChatGPT accounts ungoverned. Expected profile: L1-L2 across most dimensions, produces a dramatic heatmap.

The product itself is industry-agnostic — only the demo uses this persona.

## Readiness framework (5 × 4)

**Dimensions:** D1 Strategy & Leadership · D2 Data & Infrastructure · D3 People & Skills · D4 Governance & Risk · D5 Use Cases & Adoption
**Levels:** L1 Ad-hoc · L2 Experimental · L3 Operational · L4 Transformational

Full cell content: `framework.json` (machine, imported by the app) and `planning/framework.md` (human-readable, same content).

## Architecture

```
┌──────────────┐   POST /api/audit-stream (SSE)
│  public/     │ ←─────────────────────────┐
│  index.html  │                           │
└──────┬───────┘                           │
       │ fetch                      ┌──────┴────────┐
       ▼                            │  FastAPI      │
┌──────────────┐                    │  server.py    │
│  Vercel      │ → Serveo tunnel ─→ │               │
│  (static)    │                    │  orchestrator │
└──────────────┘                    │               │
                                    │  Claude Agent │
                                    │  SDK sub-     │
                                    │  agents       │
                                    └───────────────┘
```

**Sub-agents (Claude Agent SDK):**
- `researcher` — scrapes website, LinkedIn, job posts, press; emits evidence dossier
- `strategy-auditor`, `data-auditor`, `technology-auditor`, `talent-auditor`, `governance-auditor` — each predicts L1–L4 answers to its 4 questions with evidence citations
- `critic` — challenges weak scores, forces `discovery_needed` flag where evidence is insufficient
- Main orchestrator runs the scoring math (Mkal72's rules) + stitches personalized narrative

## Stack

- **Python 3.11 + FastAPI + Claude Agent SDK** (`claude-agent-sdk` ≥ 0.1)
- **Anthropic Sonnet 4.6** for specialists + researcher; **Opus 4.7** for critic + synthesis
- **Static HTML + Tailwind CDN** frontend (preserved from regreenjr baseline)
- **Serveo** tunnel (`.serveousercontent.com`) to expose local FastAPI to Vercel-hosted static page
- **Vercel** for static hosting
- **api/audit.js** kept as Math.random fallback if tunnel drops during judging

## Conventions

- Questions and framework cells live as JSON at repo root. Never hardcode question text.
- Screener answers (`industry`, `size`, `role`, `priority_function`) are the only personalization variables. Don't invent new ones mid-build.
- Any question where evidence is insufficient → specialist returns L1 + `discovery_needed` flag — talking point for the expert call, not a gap.
- Commit directly to `main` frequently.

## Scoring & gap math

- Per-dimension score = mean(level) across its 4 questions, rounded to 0.1
- Overall readiness = mean of 5 dimension scores
- Target level per dimension = `min(current + 1, 4)` by default
- Top 5 gaps = questions with largest `target - current`, tiebreak by alignment with `priority_function`
- L4 cells use `sustain_extend` instead of `next_moves`

## Scope boundaries

- **Payments and real booking:** out of scope. Calendly stub, no Stripe.
- **Report:** 6 pages — Cover · Exec Summary · Readiness Heatmap · Top 5 Gaps · 90-day Roadmap · Next Steps.
- **Questionnaire:** 20 scored + 4 screener questions. Skip-logic only on "Don't know".

## Attribution

Framework content (`framework.json`, `questions.json`, `planning/`) originally authored by hackathon partner in [Mkal72/aiauditapp](https://github.com/Mkal72/aiauditapp). This repo adds the Openclaw sub-agent pre-fill layer on top.
