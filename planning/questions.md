# Questionnaire — human-readable

Same content as `questions.json`. App imports the JSON.

## Screener (Q0-Q3, not scored — feeds personalization)

- **Q0 — Industry (free text)** → normalized by LLM; becomes `{{industry}}`.
- **Q1 — Size**: Fewer than 10 · 10-50 · 51-250 · 251-1000 · More than 1000
- **Q2 — Role**: Owner/CEO · COO/Ops · CIO/CTO/IT · Department head · Other
- **Q3 — Priority function (free text)**: "If AI fixed one thing this year, what would create the most value?" → becomes `{{priority_function}}`

## Scored questions (Q4-Q23)

Each has 5 options. A→L1, B→L2, C→L3, D→L4, E="Don't know" (scored L1, flagged `discovery_needed`).

### D1 Strategy & Leadership

- **Q4.** How would you describe your organization's AI strategy?
- **Q5.** Who owns AI decisions at your company?
- **Q6.** How is AI investment prioritized?
- **Q7.** How does leadership measure AI success?

### D2 Data & Infrastructure

- **Q8.** How is your business data organized?
- **Q9.** How well do your business systems integrate?
- **Q10.** How would you rate your data quality?
- **Q11.** What is your cloud and compute readiness for AI workloads?

### D3 People & Skills

- **Q12.** How AI-literate is your overall workforce?
- **Q13.** What AI training or enablement do you provide?
- **Q14.** Do you have dedicated AI, data, or ML talent in-house?
- **Q15.** How are teams encouraged to experiment with AI (particularly around `{{priority_function}}`)?

### D4 Governance & Risk

- **Q16.** Do you have written AI usage policies?
- **Q17.** How do you evaluate third-party AI vendors or tools?
- **Q18.** How do you manage AI-related risks (privacy, accuracy, bias)?
- **Q19.** How does AI use intersect with your compliance obligations (in `{{industry}}`)?

### D5 Use Cases & Adoption

- **Q20.** How many AI-powered workflows or features do you have in production today?
- **Q21.** How do you decide which AI use cases to pursue?
- **Q22.** How do you measure ROI of AI initiatives?
- **Q23.** When a pilot succeeds, how do you scale it (particularly around `{{priority_function}}`)?

## Personalization plan

- Q4-Q14, Q16-Q18, Q20-Q22: generic consulting language, no industry tokens.
- Q15, Q19, Q23: template `{{priority_function}}` or `{{industry}}` — only 3 questions carry localization so wording stays trustworthy.
- **PDF stitch call:** rewrites Exec Summary, Top 5 Gaps, and 90-day Roadmap with full `{{industry}} + {{size}} + {{priority_function}}` context. Heatmap and scorecard stay generic.
