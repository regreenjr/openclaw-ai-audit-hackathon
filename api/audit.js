export default async function handler(req, res) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method Not Allowed' });
    }

    try {
        const { companyUrl, revenueTier } = req.body;
        if (!companyUrl) return res.status(400).json({ error: 'Missing companyUrl' });
        
        const tier = revenueTier || "$3-5M";

        // 1. Fetch the target website's raw HTML
        const siteRes = await fetch(companyUrl, { 
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36' }
        });
        const html = await siteRes.text();

        // 2. Execute technical DOM footprint scraping
        const hasFacebookPixel = html.includes('fbevents.js') || html.includes('fbq(');
        const hasGTM = html.includes('googletagmanager.com') || html.includes('gtag(') || html.includes('analytics.js');
        const hasChatbot = html.includes('intercom') || html.includes('drift') || html.includes('podium') || html.includes('chat') || html.includes('widget');
        
        // 3. Clean HTML for LLM payload
        const cleanText = html.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
                              .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
                              .replace(/<[^>]+>/g, ' ')
                              .replace(/\s+/g, ' ')
                              .substring(0, 15000); 

        // 4. Construct the prompt with rigorous financial routing data
        const prompt = `You are a ruthless 8-figure roofing marketing auditor. 
Analyze this website's text and technical metadata to grade their sales/marketing infrastructure.
The company is doing ${tier} in annual revenue.

INDUSTRY BENCHMARKS & LOGIC TO APPLY:
- At ${tier} revenue, they spend 8-10% on marketing.
- LSA (Google Local Services Ads) storm leads cost $200-$250+.
- Marketing agencies charge $2k-$5k/mo on retainer.
- If they do not have a chatbot/booking widget (24/7 capture), they are losing at least 4 LSA leads per week ($1,000 in sunk ad cost + lost job value).
- If they do not have programmatic local SEO (specific city pages), 65% of their Google Search budget is hitting wrong zip codes.

Website URL: ${companyUrl}
Tech Stack Discovered via live DOM scrape: 
- Meta/Facebook Pixel Installed: ${hasFacebookPixel}
- Google Tags/Analytics Installed: ${hasGTM}
- 24/7 Chatbot/Widget Installed: ${hasChatbot}

Website Text Content (truncated):
${cleanText}

Based on their actual tech stack and copywriting, grade them brutally.
Provide a JSON response with ONLY the following structure:
{
    "monthlyBleed": "[A formatted dollar amount between $8,000 and $45,000 depending on their revenue tier and how bad their tech stack is. Include the $ sign and commas]",
    "scores": {
        "Speed-to-Lead Velocity": [Score 1-5. 1 if no chatbot/fast booking.],
        "LSA & Cost-Per-Lead Efficiency": [Score 1-5 based on text detail and tracking tags.],
        "Direct Response Copywriting": [Score 1-5 based on text aggressiveness.],
        "Agency & Tech Stack Hygiene": [Score 1-5. If no GTM or Facebook pixel, score is 1.]
    },
    "recommendations": [
        { "activity": "Name of AI/Ops Fix", "reason": "Specific aggressive reason tailored to the actual gaps found and the financial bleed calculated.", "priority": 1 }
    ]
}
Provide exactly 4 recommendations mapped to their lowest scores. Call out the "agency retainer" tax, the "LSA $250 CPL" trap, and pitch AI Voice Agents, SMS nurturing, and programmatic SEO. Return ONLY valid JSON.`;

        // 5. Fire to Gemini 3.1 Pro via OpenRouter
        const orRes = await fetch("https://openrouter.ai/api/v1/chat/completions", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${process.env.OPENROUTER_API_KEY}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                model: "google/gemini-3.1-pro-preview",
                messages: [{ role: "user", content: prompt }],
                response_format: { type: "json_object" },
                temperature: 0.1
            })
        });

        const aiData = await orRes.json();
        if (aiData.error) throw new Error(aiData.error.message || "OpenRouter Error");

        const resultText = aiData.choices[0].message.content;
        res.status(200).json(JSON.parse(resultText));

    } catch (error) {
        console.error('Audit API Error:', error);
        res.status(500).json({ error: error.message || 'Failed to process audit.' });
    }
}
