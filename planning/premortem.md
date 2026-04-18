# Pre-mortem: 6-7 hour hackathon build

Everything listed here is a landmine that could eat >1 hour if not sidestepped.

## 1. Framework paralysis

**Trap:** "No framework + any SMB" is a research black hole. Pulling Gartner, MIT CISR, Microsoft, Deloitte frameworks and synthesizing could eat 2-3 hours.

**Sidestep:** Lock the 5×4 grid already in `framework.json`. Dimensions and levels are fixed. Do not revisit after hour 0:30.

## 2. Decision tree combinatorial blowup

**Trap:** "Branching for any SMB" explodes fast. True branching tree is over-engineered.

**Sidestep:** Fixed 20 scored questions in linear order. Branching = skip-logic only (skip Qn if prior answer was "Don't know"). No adaptive re-ordering.

## 3. "I don't know where I want to be"

**Trap:** Users can't self-assess targets for every dimension, creating blank states in the report.

**Sidestep:** Don't ask targets. System sets target = `min(current + 1, 4)` by default. UI offers a one-click override to L4 per dimension.

## 4. PDF generation rabbit hole

**Trap:** Picking a PDF library blind eats 1-2 hours.

**Sidestep:** HTML `/report/[id]` route + Puppeteer `page.pdf()`. Same code serves browser preview and PDF. Puppeteer MCP is already installed.

## 5. Canned vs. dynamic recommendations

**Trap:** Hard-coded recs look weak; fully dynamic is unreliable and slow.

**Sidestep:** Framework cells pre-authored in `framework.json` (current_state + next_moves/sustain_extend). At audit time, one Claude stitch call rewrites the cells for the customer's industry, size, and priority_function. Fast, cheap, personalized.

## 6. Openclaw sub-agent integration

**Trap:** Nice-to-have framed as must-have consumes hours.

**Sidestep:** Build with direct Anthropic SDK behind a clean `runAgent()` interface. If time permits at H+4:30, swap ONE call (industry-specific benchmarking) through Openclaw. Narrate the rest in the pitch.

## 7. Design polish eating hours 5-7

**Trap:** Custom design from scratch.

**Sidestep:** shadcn/ui + Tailwind, one premium landing template, lock design at H+5:15. No custom components beyond what shadcn offers.

## 8. Report scope creep

**Trap:** "Impressive = long" wrong for a demo. 20-page PDFs break layout and eat time.

**Sidestep:** 6-page PDF, fixed sections: Cover → Exec Summary → Maturity Heatmap → Top 5 Gaps → 90-day Roadmap → Next Steps / Book Expert CTA.

## 9. "Any SMB" breadth killing question specificity

**Trap:** Generic questions feel boring; specific ones feel off-target.

**Sidestep:** Questions stay generic (common business/consulting terms). Personalization happens in 3 questions (Q15, Q19, Q23) via `{{priority_function}}` and `{{industry}}` tokens, and in the PDF's Exec Summary, Top 5 Gaps, and 90-day Roadmap sections via the stitch call.

## 10. Testing time squeeze

**Trap:** Last-minute bug on demo day.

**Sidestep:** Protected 30-45 minute block at H+5:30 for end-to-end test of the Meridian persona run. Nothing new ships after that.

## Aggressive cuts (in order) if behind schedule

1. Openclaw sub-agent integration (narrate it instead)
2. Real payment flow (stub the $1000 CTA)
3. Real booking flow (Calendly placeholder)
4. Visual heatmap (fall back to a text/emoji table)
5. Skip-logic on "Don't know" (go fully linear)
6. Industry personalization in Q15/Q19/Q23 (use the generic fallback wording)
