"""FastAPI server: SSE stream + JSON one-shot endpoints for the audit pipeline."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from . import orchestrator
from .events import EventBus

load_dotenv()

app = FastAPI(title="Openclaw AI Audit Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuditRequest(BaseModel):
    companyUrl: str
    companyName: str = ""
    industry: str = "unknown"
    size: str = "unknown"
    role: str = "unknown"
    priorityFunction: str = Field("unknown", alias="priority_function")

    class Config:
        populate_by_name = True


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "openclaw-audit-agent",
        "has_api_key": bool(os.getenv("ANTHROPIC_API_KEY")),
    }


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "openclaw-audit-agent",
        "endpoints": "/api/audit-stream (SSE), /api/audit (JSON), /health",
    }


def _screener(req: AuditRequest) -> dict[str, str]:
    return {
        "industry": req.industry,
        "size": req.size,
        "role": req.role,
        "priority_function": req.priorityFunction,
    }


def _company_name(req: AuditRequest) -> str:
    if req.companyName:
        return req.companyName
    try:
        from urllib.parse import urlparse
        host = urlparse(req.companyUrl).hostname or req.companyUrl
        return host.replace("www.", "").split(".")[0].title()
    except Exception:
        return req.companyUrl


@app.post("/api/audit-stream")
async def audit_stream(req: AuditRequest):
    """SSE stream of live agent events + final audit JSON."""
    bus = EventBus()

    async def pipeline():
        try:
            await orchestrator.run_audit(
                url=req.companyUrl,
                company_name=_company_name(req),
                screener=_screener(req),
                bus=bus,
            )
        except Exception:
            pass

    async def event_gen():
        task = asyncio.create_task(pipeline())
        try:
            async for ev in bus.stream():
                yield {"event": ev.type, "data": ev.to_sse().removeprefix("data: ").rstrip()}
        finally:
            if not task.done():
                task.cancel()

    return EventSourceResponse(event_gen())


@app.post("/api/audit")
async def audit_oneshot(req: AuditRequest) -> dict[str, Any]:
    """Synchronous one-shot audit (no streaming). Returns the full report JSON."""
    bus = EventBus()
    drain_task = asyncio.create_task(_drain(bus))
    result = await orchestrator.run_audit(
        url=req.companyUrl,
        company_name=_company_name(req),
        screener=_screener(req),
        bus=bus,
    )
    await drain_task
    return result


async def _drain(bus: EventBus) -> None:
    async for _ in bus.stream():
        pass


# Convenience for `python -m src.server`
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8787"))
    uvicorn.run("src.server:app", host="0.0.0.0", port=port, reload=True)
