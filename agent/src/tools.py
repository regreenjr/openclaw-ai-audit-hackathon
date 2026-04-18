"""Custom MCP tools exposed to sub-agents.

Currently: fetch_url — fetches a public URL, strips scripts/styles, returns plain text.
Keeps responses short enough to fit in a sub-agent's context.
"""

from __future__ import annotations

from typing import Any

import httpx
from bs4 import BeautifulSoup
from claude_agent_sdk import create_sdk_mcp_server, tool

MAX_CHARS = 8000
USER_AGENT = "openclaw-audit-bot/0.1 (+https://github.com/regreenjr/openclaw-ai-audit-hackathon)"


@tool("fetch_url", "Fetch a public URL and return extracted text. Strips scripts, styles, and boilerplate.", {"url": str})
async def fetch_url(args: dict[str, Any]) -> dict[str, Any]:
    url = args["url"]
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15.0,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            content_type = r.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return {
                    "content": [{"type": "text", "text": f"[skipped: content-type {content_type}]"}],
                    "is_error": True,
                }
            html = r.text
    except httpx.HTTPError as e:
        return {
            "content": [{"type": "text", "text": f"[fetch failed: {type(e).__name__}: {e}]"}],
            "is_error": True,
        }

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    title = (soup.title.string.strip() if soup.title and soup.title.string else "").replace("\n", " ")
    text = soup.get_text(separator="\n", strip=True)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + f"\n\n[truncated from {len(text)} chars]"

    prefix = f"URL: {url}\nTITLE: {title}\n\n" if title else f"URL: {url}\n\n"
    return {"content": [{"type": "text", "text": prefix + text}]}


def build_research_server():
    return create_sdk_mcp_server(
        name="research",
        version="0.1.0",
        tools=[fetch_url],
    )
