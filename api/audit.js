export default async function handler(req, res) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method Not Allowed' });
    }

    try {
        const { companyUrl } = req.body;
        if (!companyUrl) {
            return res.status(400).json({ error: 'Missing companyUrl' });
        }

        // 1. Fetch the target website's raw HTML
        const siteRes = await fetch(companyUrl, { 
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36' }
        });
        const html = await siteRes.text();

        // 2. Perform basic technical footprint scraping
        const hasFacebookPixel = html.includes('fbevents.js') || html.includes('fbq(');
        const hasGTM = html.includes('googletagmanager.com') || html.includes('gtag(') || html.includes('analytics.js');
        const hasChatbot = html.includes('intercom') || html.includes('drift') || html.includes('podium') || html.includes('chat') || html.includes('widget');
        const hasCalendly = html.includes('calendly.com');

        // 3. Clean the HTML down to text to send to the LLM (bypassing massive token limits)
        const cleanText = html
            .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
            .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
            .replace(/<[^>]+>/g, ' ') // strip remaining tags
            .replace(/\s+/g, ' ') // collapse whitespace
            .substring(0, 15000); // Hard limit to first 15k chars (~4k tokens)

        // 4. Construct the prompt for the actual audit
        const prompt = `You are a ruthless 8-figure roofing marketing auditor. 
Analyze this website's text and technical metadata to grade their sales/marketing infrastructure.

Website URL: ${companyUrl}
Tech Stack Discovered via DOM scrape: 
- Meta/Facebook Pixel Installed: ${hasFacebookPixel}
- Google Tags Installed: ${hasGTM}
- 24/7 Chatbot/Widget Installed: ${hasChatbot}
- Direct Calendar Booking (Calendly etc): ${hasCalendly}

Website Text Content (truncated):
${cleanText}

Based on the actual tech stack and copywriting, grade them brutally.
Provide a JSON response with ONLY the following structure:
{
    "scores": {
        "Lead Capture Friction": [Score 1-5. 1 if no chatbot/fast booking.],
        "Local SEO & Service Depth": [Score 1-5 based on text detail.],
        "Direct Response Copywriting": [Score 1-5 based on text aggressiveness.],
        "Marketing Tech Stack": [Score 1-5 based strictly on the Pixels/Tags found above.]
    },
    "avgScore": "[Average formatted to 1 decimal]",
    "recommendations": [
        { "activity": "Name of AI/Ops Fix", "reason": "Specific aggressive reason tailored to the actual gaps found in their site data", "priority": 1 }
    ]
}
Provide exactly 4 recommendations mapped to their lowest scores. Focus on AI voice, SMS nurturing, programmatic SEO, and API integrations. Return ONLY valid JSON.`;

        // 5. Route through OpenRouter to Gemini 3.1 Pro
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
        
        if (aiData.error) {
            throw new Error(aiData.error.message || "OpenRouter Error");
        }

        const resultText = aiData.choices[0].message.content;
        
        // Ensure returning clean JSON
        res.status(200).json(JSON.parse(resultText));

    } catch (error) {
        console.error('Audit API Error:', error);
        res.status(500).json({ error: error.message || 'Failed to process audit.' });
    }
}
