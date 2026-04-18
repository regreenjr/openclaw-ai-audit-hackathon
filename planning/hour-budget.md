# Hour budget — 6.5 hour hackathon

Times are elapsed from start. Any task that threatens to run long triggers a cut from the list in `premortem.md`.

| Elapsed | Task | Definition of done |
|---------|------|--------------------|
| 0:00 – 0:30 | Kick off. Skim `CLAUDE.md`, `framework.json`, `questions.json`. Confirm no changes to dimensions, levels, or question set. Create Next.js scaffold. | Repo cloned, Next.js app runs locally, TypeScript + Tailwind + shadcn installed. |
| 0:30 – 1:15 | Polish framework cell wording. Optional batch call: rewrite all 20 cells for punchier prose. Keep it out of the critical path if pressed for time. | `framework.json` frozen. |
| 1:15 – 2:30 | Build the form wizard. Screener (Q0-Q3) + 20 scored questions (Q4-Q23). Progress bar. Client-side validation. Answers → scoring → stored in memory keyed by session ID. | Respondent can complete the form and land on a "Generating your audit..." screen. |
| 2:30 – 3:30 | Scoring engine + `/report/[id]` HTML route. Compute per-dimension scores, gaps, top-5 gap list. Build the report page layout (6 fixed sections). | Report page renders at `/report/[id]` with placeholder copy wherever the stitch call has not run yet. |
| 3:30 – 4:30 | Stitch call: Claude generates personalized Exec Summary, Top 5 Gaps narrative, and 90-day Roadmap from (answers + matched cells + screener tokens). Heatmap component (Recharts or SVG). | Report page renders end-to-end with real personalized content. |
| 4:30 – 5:15 | Puppeteer PDF pipeline. `/api/pdf/[id]` endpoint renders the report route and returns a styled PDF. Download button on the result page. | Downloadable PDF works for the Meridian persona run. |
| 5:15 – 5:45 | Landing page. Pitch, pricing ($1,000), "Start Audit" CTA, "Book Expert" Calendly stub. Polish. | Landing looks sharp, CTAs route correctly. |
| 5:45 – 6:00 | Optional: Openclaw sub-agent swap for one call (e.g. industry-specific benchmarking). Cut if behind. | If shipped, narrate in pitch. Otherwise skip cleanly. |
| 6:00 – 6:30 | End-to-end test with the Meridian persona. Fix bugs. Demo rehearsal. | Persona run completes, PDF downloads, pitch has been said out loud once. |

## Checkpoints

- **H+2:30** — Form works end to end (no scoring yet). If not, cut skip-logic.
- **H+4:30** — Report renders with personalized content. If not, ship with generic cell wording only.
- **H+5:15** — PDF downloads cleanly. If not, demo the HTML report page instead.
- **H+6:00** — Nothing new ships after this. Only bug fixes.

## Pair split suggestions (if useful)

- **One of you** on scaffolding + form wizard + scoring engine (a well-defined, can-work-solo path through H+2:30).
- **The other** on the report page layout + stitch prompt + Puppeteer pipeline (the LLM + PDF side).
- Reconverge at H+3:30 to connect scoring → report and again at H+5:15 for integration testing.
