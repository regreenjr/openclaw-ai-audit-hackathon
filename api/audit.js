export const config = {
  runtime: 'edge', // Fast global edge execution
};

async function askKimi(apiKey, prompt, systemInstruction = "You are a ruthless marketing auditor.") {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000); 

    try {
        const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${apiKey}`,
                "Content-Type": "application/json",
                "HTTP-Referer": "https://robbgreen.com",
                "X-Title": "K2.6 Swarm Edge"
            },
            signal: controller.signal,
            body: JSON.stringify({
                model: "moonshotai/kimi-k2.6", 
                messages: [{ role: "user", content: prompt }],
                temperature: 0.1,
                system: systemInstruction
            })
        });

        clearTimeout(timeout);
        const data = await response.json();
        
        if (data.error) throw new Error(data.error.message);
        
        return data.choices[0].message.content;
    } catch (e) {
        clearTimeout(timeout);
        console.error("Kimi Agent failed:", e.message);
        return "ERROR: " + e.message;
    }
}

export default async function handler(req) {
    if (req.method !== 'POST') {
        return new Response(JSON.stringify({ error: 'Method Not Allowed' }), { status: 405 });
    }

    try {
        const body = await req.json();
        let { companyUrl, revenueTier } = body;
        if (!companyUrl) return new Response(JSON.stringify({ error: 'Missing companyUrl' }), { status: 400 });
        
        const tier = revenueTier || "$3-5M";
        if (!/^https?:\/\//i.test(companyUrl)) companyUrl = 'https://' + companyUrl;

        // 1. The Scraper Agent
        const scraperController = new AbortController();
        const scraperTimeout = setTimeout(() => scraperController.abort(), 6000); 

        let html = '';
        try {
            const siteRes = await fetch(companyUrl, { 
                headers: { 
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                },
                signal: scraperController.signal
            });
            
            if (siteRes.status === 200) {
                html = await siteRes.text();
            } else {
                html = `HTTP ${siteRes.status} response.`;
            }
            clearTimeout(scraperTimeout);
        } catch(fe) {
            html = 'Homepage failed to load.';
        }

        const hasFacebookPixel = html.includes('fbevents.js') || html.includes('fbq(');
        const hasGTM = html.includes('googletagmanager.com') || html.includes('gtag(') || html.includes('analytics.js');
        const hasChatbot = html.includes('intercom') || html.includes('drift') || html.includes('podium') || html.includes('chat') || html.includes('widget');
        
        const cleanText = html.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
                              .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
                              .replace(/<[^>]+>/g, ' ')
                              .replace(/\s+/g, ' ')
                              .substring(0, 10000); 

        // 2. Parallel K2.6 Swarm (Executed concurrently)
        const copyPrompt = `Analyze the tone, aggression, and clarity of this roofing website's copywriting. Is it a generic boring brochure or a high-converting direct-response sales page? Reply with 2 sentences and a score from 1.0 to 5.0.\n\nTEXT:\n${cleanText.substring(0, 5000)}`;
        const techPrompt = `Analyze this roofing website's tech stack footprint: Facebook Pixel: ${hasFacebookPixel}, Google Tags: ${hasGTM}, 24/7 Chatbot: ${hasChatbot}. Is this a modern data-driven sales machine or an outdated liability? Reply with 2 sentences and a score from 1.0 to 5.0.`;

        const openRouterKey = process.env.OPENROUTER_API_KEY;

        const [copyAnalysis, techAnalysis] = await Promise.all([
            askKimi(openRouterKey, copyPrompt, "You are a direct response copywriting analyst. Be brutal."),
            askKimi(openRouterKey, techPrompt, "You are a technical marketing infrastructure auditor.")
        ]);

        // 3. Orchestrator Synthesis
        const finalPrompt = `You are a ruthless 8-figure roofing marketing auditor. 
Synthesize these two agent reports into a final brutal JSON output.
The company is doing ${tier} in annual revenue. They spend 8-10% on marketing. LSA leads cost $250.

Agent 1 (Copywriting Analysis): ${copyAnalysis}
Agent 2 (Tech Stack Analysis): ${techAnalysis}

Return ONLY this JSON structure, heavily penalizing them if Agent 2 found no chatbot or pixels:
{
    "monthlyBleed": "[Calculate exact dollar amount lost to Speed-to-Lead lag and Agency Retainer waste based on their ${tier} revenue bracket. Formatted string: e.g. $14,500]",
    "scores": {
        "Speed-to-Lead Velocity": [Final numeric score 1.0-5.0],
        "LSA & Cost-Per-Lead Efficiency": [Final numeric score 1.0-5.0],
        "Direct Response Copywriting": [Final numeric score 1.0-5.0],
        "Agency & Tech Stack Hygiene": [Final numeric score 1.0-5.0]
    },
    "recommendations": [
        { "activity": "AI Voice Agents", "reason": "Specific aggressive reason based on the agent reports.", "priority": 1 },
        { "activity": "Programmatic SEO", "reason": "Specific reason...", "priority": 2 },
        { "activity": "SMS Nurturing", "reason": "Specific reason...", "priority": 3 },
        { "activity": "Pixel Architecture", "reason": "Specific reason...", "priority": 4 }
    ]
}`;
        
        let finalOutput = await askKimi(openRouterKey, finalPrompt, "You output pure unformatted JSON. Just { ... }");
        finalOutput = finalOutput.replace(/```json/g, '').replace(/```/g, '').trim();

        return new Response(finalOutput, {
            status: 200,
            headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
        });

    } catch (error) {
        console.error('Audit API Error:', error);
        return new Response(JSON.stringify({
            monthlyBleed: "$18,500+",
            scores: { "Speed-to-Lead Velocity": 1.5, "LSA & Cost-Per-Lead Efficiency": 2.0, "Direct Response Copywriting": 2.5, "Agency & Tech Stack Hygiene": "Timeout." },
            recommendations: [
                { activity: "Fatal API Timeout Detected", reason: "Your website failed to load or blocked the payload.", priority: 1 },
                { activity: "AI Voice Agents", reason: "LSA Leads cost $250. You are bleeding them. Implement an autonomous inbound voice system.", priority: 2 },
                { activity: "Programmatic SEO", reason: "Your current agency is burning budget on generic localized zip codes.", priority: 3 },
                { activity: "SMS Nurturing", reason: "Speed to lead is king. If your human rep doesn't text in 4 minutes, the job is dead.", priority: 4 }
            ]
        }), { status: 200, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' } });
    }
}
