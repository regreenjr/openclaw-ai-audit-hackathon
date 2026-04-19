# Readiness framework (5 × 4) — human-readable

Same content as `framework.json`. Use this for reading, comments, and sharing. App imports the JSON.

**Dimensions:** D1 Strategy & Leadership · D2 Data & Infrastructure · D3 People & Skills · D4 Governance & Risk · D5 Use Cases & Adoption
**Levels:** L1 Ad-hoc · L2 Experimental · L3 Operational · L4 Transformational

At audit time the stitch layer:
- Pulls the cell matching the respondent's current level per dimension → that paragraph becomes the diagnosis in the report (rewritten with industry / priority_function).
- Pulls the same cell's `next_moves` → seed for the 90-day roadmap; LLM personalizes with the respondent's context.
- For L4 cells, uses `sustain_extend` instead.

---

## D1 — Strategy & Leadership

### L1 Ad-hoc
*Current state:* AI comes up reactively, usually when a staff member brings in a tool they have seen elsewhere. No defined vision for how AI fits the business. Spend is incidental, hidden inside other line items.
*Next moves:*
1. 60-minute leadership workshop to name 3 business outcomes AI should support this year.
2. One-page AI point-of-view stating what AI is *for* in this business — and what it is not.
3. Assign a single executive sponsor (even part-time) to own AI decisions.

### L2 Experimental
*Current state:* Leadership supports a few pilots, but there is no written strategy or formal tie to business goals. Priorities shift with attention; projects start and stall. Senior staff discuss AI without shared definitions.
*Next moves:*
1. Produce a written 12-18 month AI roadmap with 3-5 named initiatives, owners, and success metrics.
2. Stand up a bi-weekly AI steering check-in with the sponsor and initiative owners.
3. Tie each initiative to an existing business KPI so AI spend maps to numbers the company already tracks.

### L3 Operational
*Current state:* Documented AI roadmap with executive sponsorship and clear owners. Initiatives prioritized annually and measured against KPIs. AI appears in the operating plan.
*Next moves:*
1. Elevate AI from operational roadmap to strategic plan — annual plan, board updates, investor/partner comms.
2. Shift from project ROI to portfolio view: which combinations of initiatives compound?
3. Quarterly competitive scan of peer and adjacent-industry AI deployments, used to rebalance priorities.

### L4 Transformational
*Current state:* AI is core to strategy, reviewed at the board level, and shapes how the business competes. Leadership treats AI capability as a long-term differentiator, not a cost center.
*Sustain & extend:*
1. Build AI literacy at board/ownership level via briefings and external advisors.
2. Make AI capability a criterion in M&A, hiring, and partner decisions.
3. Publish an external AI point-of-view to compound brand and talent advantages.

## D2 — Data & Infrastructure

### L1 Ad-hoc
*Current state:* Data lives in spreadsheets, shared drives, and email threads. Information moves by manual copy-paste. No single source of truth for core entities (customers, jobs, transactions). Reports are re-stitched each time they are needed.
*Next moves:*
1. One-page data map of the top 5 data sources and where each truly lives today.
2. Pick one core entity (clients, matters, orders) and consolidate it into a single system of record.
3. Establish a shared naming convention and folder structure for files that must stay in drives for now.

### L2 Experimental
*Current state:* Core systems of record exist but operate as islands. Data quality varies, integrations are manual or brittle, and a cross-system view requires someone to pull it by hand.
*Next moves:*
1. Identify the 2-3 integrations that would unlock the most time savings; implement via lightweight iPaaS (Zapier, Make) or native connectors.
2. Designate data owners per system — one person accountable for definitions, quality, access.
3. Move AI-relevant data (documents, transcripts, interactions) into a searchable, permissioned store an AI system could safely query.

### L3 Operational
*Current state:* Data is centralized in a warehouse or lake, integrations are standardized via APIs, and governance exists. Teams self-serve common reports. Data quality is monitored with named owners.
*Next moves:*
1. Stand up a retrieval layer (vector store + structured views) so AI tools work against governed data, not ad-hoc exports.
2. Introduce data contracts for top upstream sources so schema changes do not silently break AI use.
3. Move to near-real-time availability on the 2-3 datasets that drive operational AI.

### L4 Transformational
*Current state:* Unified, real-time, ML-ready platform supports self-serve analytics and governed AI workloads. Data contracts, lineage, and quality signals continuously monitored.
*Sustain & extend:*
1. Treat data as a product — named products, SLAs, roadmaps, internal customers.
2. Invest in model/data observability (drift, freshness, usage).
3. Evaluate whether proprietary data enables new offerings (benchmarks, insights products, data partnerships).

## D3 — People & Skills

### L1 Ad-hoc
*Current state:* Most staff have limited direct experience with AI tools. No training exists. Staff who do use AI use personal accounts without guidance.
*Next moves:*
1. 60-minute all-hands on what AI is, what the business endorses using it for, and what to avoid.
2. Issue approved AI tool accounts to the ~20% of staff whose roles benefit most.
3. Publish a short "how we use AI here" guide with 5-10 concrete examples drawn from real jobs in the business.

### L2 Experimental
*Current state:* A handful of early-adopter staff use AI tools, often self-taught, sometimes through personal accounts. Knowledge stays in pockets; nothing is documented or shared systematically.
*Next moves:*
1. Build structured training by role, with real prompts and workflows tied to each role's actual tasks.
2. Create a shared prompt library or playbook tied to recurring workflows, with a named maintainer.
3. Name internal AI champions per team, with explicit time allocated to support peers.

### L3 Operational
*Current state:* Most teams have baseline AI training, champions exist, and specialist ownership (or a small team) drives adoption. Practices are documented and shared.
*Next moves:*
1. Add AI fluency to hiring rubrics and onboarding so new hires start at the organization's baseline.
2. Establish role-specific certifications or completion tracking so AI fluency is measurable per team.
3. Allocate dedicated continuous-learning budget — internal hackathons, conferences, paid subscriptions.

### L4 Transformational
*Current state:* AI fluency is a baseline expectation across the workforce. Specialized talent is available, a learning culture is in place, and AI-assisted work is the norm.
*Sustain & extend:*
1. Build internal certifications with external credibility so staff skills are portable and the employer brand benefits.
2. Rotate staff through an AI guild or center of excellence to seed capability across teams.
3. Offer client- or partner-facing AI enablement — customer success compounds retention.

## D4 — Governance & Risk

### L1 Ad-hoc
*Current state:* No written AI policy. Staff use whatever tools they discover, often pasting sensitive information into public AI services. Vendor decisions are made independently at the team level.
*Next moves:*
1. One-page AI acceptable use policy covering approved tools, prohibited data types, and an escalation path.
2. Add a 5-question AI review to existing procurement or vendor intake.
3. Map which regulations or contractual obligations apply to your data (confidentiality, client privilege, PHI, PII, payment data) so policy focuses on the highest-stakes categories.

### L2 Experimental
*Current state:* Informal guidelines (a Slack post or memo) exist, but nothing enforceable. Vendor selection is ad-hoc per team. Risks surface reactively when something goes wrong.
*Next moves:*
1. Upgrade the memo into a formal signed policy covering acceptable use, data handling, vendor review, incident reporting.
2. Run AI risk assessments on the top 3-5 tools in use — what data flows in, where does it go, what could go wrong?
3. Give legal/compliance visibility into AI initiatives before, not after, go-live.

### L3 Operational
*Current state:* Formal policy covers acceptable use, data, and vendors. Risks assessed pre-deployment and documented. Legal/compliance is part of the process.
*Next moves:*
1. Move from assessment-at-launch to continuous monitoring — periodic output reviews, vendor changes, new regulations.
2. Establish a model/tool review board (small cross-functional committee, monthly).
3. Train staff on the policy annually with scenario-based exercises, not just read-and-acknowledge.

### L4 Transformational
*Current state:* Governance is continuous and embedded — auditable, monitored, with a model review board, red-teaming, and proactive regulator and partner engagement.
*Sustain & extend:*
1. Publish a trust and transparency statement clients and partners can reference in their own procurement.
2. Contribute to industry working groups or standards bodies.
3. Invest in automated controls (DLP, prompt logging, approval workflows) so governance scales without proportional headcount.

## D5 — Use Cases & Adoption

### L1 Ad-hoc
*Current state:* No AI-powered workflows in production. Any AI use is individual experimentation. No mechanism for deciding which use cases to pursue or how to measure them.
*Next moves:*
1. 2-hour use-case workshop: list repetitive, high-volume, information-heavy tasks; score by value × feasibility; pick 2-3 to pilot.
2. Pilot one low-risk, internal-facing workflow (drafting, summarization, extraction) before anything client-facing.
3. Define success upfront — time saved per task, error rate, NPS — so the pilot produces evidence, not anecdote.

### L2 Experimental
*Current state:* 1-2 AI pilots exist — sometimes informally — but nothing is systematically scaled, measured, or prioritized. Interesting ideas win over high-value ones.
*Next moves:*
1. Introduce a lightweight value × feasibility × strategic-fit prioritization framework and actually apply it to the backlog.
2. Establish pre/post baselines on current pilots so value is measurable, not guessed.
3. Create a productionization checklist — owner, monitoring, retirement trigger — before you scale anything.

### L3 Operational
*Current state:* Multiple AI workflows run in production across departments, with ROI tracked and a defined scaling path. A portfolio is emerging.
*Next moves:*
1. Move to portfolio-level management: quarterly review, retire underperformers, double down on winners.
2. Tie value tracking to finance systems so AI-attributed savings or revenue appear in the P&L, not slides.
3. Launch one flagship client-facing AI capability that differentiates the business externally, not just internally.

### L4 Transformational
*Current state:* Dozens of AI capabilities run across the business, managed as a portfolio, with continuous optimization, standard scaling playbooks, and value measured continuously.
*Sustain & extend:*
1. Explore AI-native offerings — productized services, outcome-based contracts, new pricing models.
2. Invest in agent/orchestration layers so new use cases ship faster and cheaper than the last.
3. Treat AI capability as a moat — measure your rate of improvement against competitors, not your own past.
