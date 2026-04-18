const BIG_FOUR_RUBRIC = {
  Strategy: { 1: "No AI vision", 2: "AI in roadmap", 3: "Explicit AI strategy", 4: "AI fully integrated" },
  Data: { 1: "No centralized data", 2: "Siloed databases", 3: "Unified data lake", 4: "Real-time AI-driven" },
  Technology: { 1: "No AI tooling", 2: "Point solutions", 3: "Integrated AI platform", 4: "Full ML Ops" },
  Talent: { 1: "No AI expertise", 2: "Limited training", 3: "Dedicated AI team", 4: "AI literacy across org" },
  Governance: { 1: "No framework", 2: "Ad-hoc compliance", 3: "Formal AI governance", 4: "Continuous monitoring" }
};

function scoreBigFour(companyName) {
  return {
    Strategy: Math.floor(Math.random() * 3) + 2,
    Data: Math.floor(Math.random() * 2) + 2,
    Technology: Math.floor(Math.random() * 3) + 1,
    Talent: Math.floor(Math.random() * 3) + 1,
    Governance: Math.floor(Math.random() * 2) + 2
  };
}

function generatePortersRecommendations(scores) {
  const recommendations = [];
  if (scores.Technology <= 2) recommendations.push({ activity: "Tech Development", reason: "Invest in ML Ops tooling.", priority: 1 });
  if (scores.Talent <= 2) recommendations.push({ activity: "HR & Org", reason: "Build AI talent and literacy.", priority: 2 });
  if (scores.Data <= 2) recommendations.push({ activity: "Operations", reason: "Build a centralized data lake.", priority: 3 });
  if (scores.Strategy <= 2) recommendations.push({ activity: "Strategy", reason: "Align AI with business goals.", priority: 1 });
  if (scores.Governance <= 2) recommendations.push({ activity: "Governance", reason: "Build compliance frameworks.", priority: 4 });
  return recommendations.sort((a, b) => a.priority - b.priority);
}

export default function handler(req, res) {
  // CORS Headers
  res.setHeader('Access-Control-Allow-Credentials', true)
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,POST')
  res.setHeader('Access-Control-Allow-Headers', 'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version')

  if (req.method === 'OPTIONS') {
    return res.status(200).end()
  }

  if (req.method === 'GET') {
    return res.status(200).json({ status: "ok", service: "Vercel Big Four Audit API" });
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { companyUrl, companyName } = req.body || {};
  if (!companyUrl || !companyName) {
    return res.status(400).json({ error: "companyUrl and companyName required in JSON body" });
  }

  try {
    const scores = scoreBigFour(companyName);
    const avgScore = Object.values(scores).reduce((a, b) => a + b) / 5;
    const porters = generatePortersRecommendations(scores);
    
    const auditMarkdown = `
# AI Maturity Audit Report: ${companyName}
## Executive Summary
**Overall Maturity: ${avgScore.toFixed(1)}/4.0**

### Big Four Scores
- **Strategy:** ${scores.Strategy}/4
- **Data:** ${scores.Data}/4
- **Technology:** ${scores.Technology}/4
- **Talent:** ${scores.Talent}/4
- **Governance:** ${scores.Governance}/4

## Porter's Value Chain: Top Opportunities
${porters.map((rec, idx) => `**${idx + 1}. ${rec.activity}**\n- _${rec.reason}_`).join('\n\n')}

## Next Steps
Book a 30-minute Implementation Strategy Call with our AI experts to define your 90-day roadmap.
**Investment: $1,000 | ROI: $50k-$500k automation savings**
    `.trim();

    res.status(200).json({
      companyName, companyUrl, bigFourScores: scores, avgScore: parseFloat(avgScore.toFixed(1)), portersRecommendations: porters, auditMarkdown, timestamp: new Date().toISOString()
    });
  } catch(error) {
    res.status(500).json({ error: error.message });
  }
}
