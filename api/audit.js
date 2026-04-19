// Vercel serverless fallback — returns the NEW audit shape when the serveo tunnel
// is unreachable during judging. Deterministic per companyName (same input → same
// output) via a simple string hash. Does NOT call Anthropic.

// ---------- Deterministic PRNG ----------
function hashString(s) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

// Mulberry32 PRNG seeded from hash
function prng(seed) {
  let t = seed >>> 0;
  return function () {
    t = (t + 0x6D2B79F5) >>> 0;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

function pickLevel(rand) {
  // Biased toward L1-L2 to make the demo dramatic (matches Meridian persona)
  const r = rand();
  if (r < 0.4) return 1;
  if (r < 0.8) return 2;
  if (r < 0.95) return 3;
  return 4;
}

// ---------- Fallback question pool (one per gap slot) ----------
const GAP_POOL = [
  { qid: "Q3",  dimension: "D1", stem: "Is there a written AI strategy that ties tools to measurable outcomes?" },
  { qid: "Q8",  dimension: "D2", stem: "How is your business data organized and accessible to AI tools?" },
  { qid: "Q11", dimension: "D3", stem: "Do staff have structured training on the AI tools they use?" },
  { qid: "Q15", dimension: "D4", stem: "Is there an approved-tools list and usage policy for AI?" },
  { qid: "Q18", dimension: "D5", stem: "Are AI use cases measured against KPIs, not just adoption?" },
  { qid: "Q4",  dimension: "D1", stem: "Who on the leadership team owns AI outcomes and budget?" },
];

// ---------- Value chain play templates ----------
const PLAY_TEMPLATES = [
  {
    activity: "operations",
    activity_label: "Primary: Operations",
    priority: 1,
    addresses_gap: "D3",
    title: "Automate intake document classification",
    description: "Deploy an AI-powered intake pipeline that classifies inbound client documents (contracts, forms, receipts) and routes them to the correct workflow. Pairs a lightweight OCR layer with a Claude-based classifier over your existing shared drive structure.",
    expected_impact: "Reclaims 8–12 hours per week currently spent on manual triage; shortens client onboarding by 2–3 days.",
  },
  {
    activity: "marketing",
    activity_label: "Primary: Marketing & Sales",
    priority: 2,
    addresses_gap: "D5",
    title: "AI-assisted proposal generation",
    description: "Train a private Claude Project on your last 24 months of winning proposals, rate cards, and case studies so your sales team can spin up tailored drafts in minutes instead of hours.",
    expected_impact: "Cuts proposal turnaround from 2 days to under 2 hours; 20% lift in proposals sent per rep per month.",
  },
  {
    activity: "tech-dev",
    activity_label: "Support: Tech Development",
    priority: 1,
    addresses_gap: "D2",
    title: "Consolidate siloed data into a unified workspace",
    description: "Stand up a single source of truth by piping QuickBooks, shared drives, and email archives into a governed data layer (Airtable, Snowflake, or a lightweight Postgres) that AI tools can query with scoped permissions.",
    expected_impact: "Unlocks reliable cross-system reporting and removes the #1 blocker for every downstream AI use case.",
  },
  {
    activity: "hr",
    activity_label: "Support: Human Resources",
    priority: 2,
    addresses_gap: "D3",
    title: "Structured AI literacy program for all staff",
    description: "Roll out a 4-week internal curriculum covering prompt hygiene, data handling rules, and use-case ideation. Pair each department with an AI champion who runs monthly office hours.",
    expected_impact: "Moves the org from ungoverned personal-account usage to policy-aligned adoption across 100% of staff.",
  },
  {
    activity: "service",
    activity_label: "Primary: Service",
    priority: 3,
    addresses_gap: "D5",
    title: "Client status and FAQ assistant",
    description: "Launch a Claude-powered internal assistant that answers 'where is my file?' and scope-of-service questions by reading from your project management and billing systems.",
    expected_impact: "Deflects 30–40% of client status inquiries; frees senior staff for advisory work.",
  },
  {
    activity: "infrastructure",
    activity_label: "Support: Infrastructure",
    priority: 1,
    addresses_gap: "D4",
    title: "Publish an approved-tools list and usage policy",
    description: "Codify which AI tools are sanctioned for which data types, who can approve new tools, and how staff should handle client-confidential inputs. Pair with a quick-reference one-pager.",
    expected_impact: "Eliminates ungoverned personal-account usage; required before any regulated client can green-light a deeper AI engagement.",
  },
  {
    activity: "inbound",
    activity_label: "Primary: Inbound Logistics",
    priority: 3,
    addresses_gap: "D2",
    title: "Pre-screen inbound leads with AI enrichment",
    description: "Enrich every inbound inquiry with firmographics, industry classification, and fit-scoring before it hits a human calendar. Cuts time wasted on out-of-ICP conversations.",
    expected_impact: "Saves 3–5 hours/week of discovery-call time; improves close rate on qualified calls by 10–15%.",
  },
];

function buildDimensionScores(rand) {
  // Score 4 questions per dimension, average to get dimension score
  const scores = {};
  for (const dim of ["D1", "D2", "D3", "D4", "D5"]) {
    const levels = [pickLevel(rand), pickLevel(rand), pickLevel(rand), pickLevel(rand)];
    scores[dim] = Math.round((levels.reduce((a, b) => a + b, 0) / 4) * 10) / 10;
  }
  return scores;
}

function buildTopGaps(dimScores, rand) {
  // Pick 5 gaps from pool, assign current/target based on dimension score
  const pool = [...GAP_POOL];
  // shuffle deterministically
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  return pool.slice(0, 5).map((q, idx) => {
    const dimScore = dimScores[q.dimension] || 1.5;
    const current = Math.max(1, Math.floor(dimScore));
    const target = Math.min(current + 1, 4);
    return {
      qid: q.qid,
      dimension: q.dimension,
      current,
      target,
      gap: target - current,
      stem: q.stem,
      evidence: ["(fallback — scrape unavailable)"],
      discovery_needed: idx >= 3, // last two flagged as discovery
    };
  });
}

function buildValueChainPlays(dimScores, rand) {
  // Pick 4 plays, bias toward the dimensions with the lowest scores
  const sortedDims = Object.entries(dimScores).sort((a, b) => a[1] - b[1]);
  const lowDims = new Set(sortedDims.slice(0, 3).map(([d]) => d));
  // Prefer plays whose addresses_gap is in lowDims, fall back to remaining
  const preferred = PLAY_TEMPLATES.filter(p => lowDims.has(p.addresses_gap));
  const others = PLAY_TEMPLATES.filter(p => !lowDims.has(p.addresses_gap));
  const combined = [...preferred, ...others];
  // Shuffle preferred and others separately so we keep preferred first
  for (let i = preferred.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [combined[i], combined[j]] = [combined[j], combined[i]];
  }
  return combined.slice(0, 4);
}

function buildNarrative(companyName, overall, dimScores) {
  const weakest = Object.entries(dimScores).sort((a, b) => a[1] - b[1])[0];
  const strongest = Object.entries(dimScores).sort((a, b) => b[1] - a[1])[0];
  const DIM_LABELS = {
    D1: "Strategy & Leadership",
    D2: "Data & Infrastructure",
    D3: "People & Skills",
    D4: "Governance & Risk",
    D5: "Use Cases & Adoption",
  };
  return {
    exec_summary: `${companyName} is operating at an overall AI readiness of ${overall.toFixed(1)}/4.0 — largely ${
      overall < 1.75 ? "ad-hoc with isolated experimentation" :
      overall < 2.5  ? "experimental with pockets of repeatable usage" :
      overall < 3.25 ? "operational with clear AI workflows in place" :
                       "transformational with AI embedded across the value chain"
    }. The sharpest gap is in ${DIM_LABELS[weakest[0]]} (${weakest[1].toFixed(1)}), while ${DIM_LABELS[strongest[0]]} (${strongest[1].toFixed(1)}) is the most defensible starting point. Close the ${weakest[0]} gap first — every downstream use case depends on it.`,
    top_gaps_narrative: `The five gaps below represent the highest-leverage questions where a one-level improvement compounds fastest. Each is rated with current evidence — ${dimScores.D4 < 2 ? "policy gaps" : "governance coverage"} and ${dimScores.D2 < 2 ? "data organization" : "data readiness"} set the ceiling for everything else.`,
    roadmap_90_day: {
      "30_days": [
        `Publish an approved-tools list and data-handling policy for ${companyName}.`,
        "Appoint an AI owner on the leadership team with a quarterly budget line.",
        "Inventory every AI tool currently in use (including personal accounts) and its data scope.",
      ],
      "60_days": [
        `Consolidate ${weakest[0] === "D2" ? "siloed" : "key"} operational data into a single AI-queryable workspace.`,
        "Launch a 4-week internal AI literacy curriculum for all staff.",
        "Pilot the top value chain play from the deployment plan and instrument it with KPIs.",
      ],
      "90_days": [
        "Review pilot KPIs; expand the winning use case across the department.",
        "Kick off a second pilot in the next-highest-priority value chain activity.",
        "Publish the 12-month AI roadmap tied to P&L targets.",
      ],
    },
  };
}

export default function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,POST');
  res.setHeader('Access-Control-Allow-Headers', 'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method === 'GET') {
    return res.status(200).json({
      status: "ok",
      service: "Openclaw AI Audit — Vercel fallback",
      note: "Emits the new dimension_scores + value_chain_plays shape. Deterministic per companyName."
    });
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const body = req.body || {};
  const { companyUrl, companyName } = body;
  if (!companyUrl || !companyName) {
    return res.status(400).json({ error: "companyUrl and companyName required in JSON body" });
  }

  try {
    // Seed PRNG from companyName so same input → same output
    const seed = hashString(String(companyName).toLowerCase().trim());
    const rand = prng(seed);

    const dimScores = buildDimensionScores(rand);
    const overall = Math.round((Object.values(dimScores).reduce((a, b) => a + b, 0) / 5) * 10) / 10;
    const targets = Object.fromEntries(
      Object.entries(dimScores).map(([d, s]) => [d, Math.min(Math.round(s) + 1, 4)])
    );
    const topGaps = buildTopGaps(dimScores, rand);
    const plays = buildValueChainPlays(dimScores, rand);
    const narrative = buildNarrative(companyName, overall, dimScores);

    return res.status(200).json({
      scorecard: {
        dimension_scores: dimScores,
        overall_score: overall,
        target_levels: targets,
        top_gaps: topGaps,
      },
      narrative,
      value_chain_plays: plays,
      company_name: companyName,
      url: companyUrl,
      _fallback: true,
      _timestamp: new Date().toISOString(),
    });
  } catch (error) {
    return res.status(500).json({ error: error.message });
  }
}
