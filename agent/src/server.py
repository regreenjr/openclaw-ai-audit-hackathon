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

from . import db, orchestrator
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
        "db_enabled": db.is_enabled(),
    }


class QuizSubmission(BaseModel):
    """User self-assessment answers. Shape: {Q4: 3, Q5: 2, ...} — level per question."""
    answers: dict[str, int]
    contextual: dict[str, Any] = Field(default_factory=dict)


@app.get("/api/session/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    s = db.get_session(session_id)
    if not s:
        return {"error": "session not found", "session_id": session_id}
    return s


@app.post("/api/quiz/{session_id}")
async def submit_quiz(session_id: str, submission: QuizSubmission) -> dict[str, Any]:
    """Persist user quiz answers. Returns session_id so the frontend can redirect to /report/{id}."""
    ok = db.update_quiz(session_id, submission.answers)
    if not ok:
        return {"error": "failed to save quiz", "session_id": session_id}
    return {"session_id": session_id, "status": "quizzed"}


@app.post("/api/combined-report/{session_id}")
async def combined_report_oneshot(session_id: str) -> dict[str, Any]:
    """Fuse scraped agent output with user quiz answers → final combined report.
    Blocks until complete. Returns the full fused report JSON."""
    bus = EventBus()
    drain_task = asyncio.create_task(_drain(bus))
    try:
        result = await orchestrator.run_combined_report(session_id, bus)
        await bus.close()
        await drain_task
        return result
    except Exception as e:
        await bus.close()
        return {"error": str(e), "session_id": session_id}


@app.post("/api/combined-report/{session_id}/stream")
async def combined_report_stream(session_id: str):
    """SSE variant of the combined-report endpoint — stream events as the combiner runs."""
    bus = EventBus()

    async def pipeline():
        try:
            await orchestrator.run_combined_report(session_id, bus)
        except Exception:
            pass
        finally:
            await bus.close()

    async def event_gen():
        task = asyncio.create_task(pipeline())
        try:
            async for ev in bus.stream():
                yield {"event": ev.type, "data": ev.to_sse().removeprefix("data: ").rstrip()}
        finally:
            if not task.done():
                task.cancel()

    return EventSourceResponse(event_gen())


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "openclaw-audit-agent",
        "endpoints": "/api/audit-stream (SSE), /api/audit (JSON), /health",
    }


def _normalize_url(raw: str) -> str:
    """Accept any of: acme.com, www.acme.com, http://acme.com, https://acme.com/path.
    Returns a canonical https://host[/path] URL, or the input stripped if unparseable."""
    from urllib.parse import urlparse, urlunparse
    import re
    s = (raw or "").strip()
    if not s:
        return ""
    # Strip leading @ or bare // some pastes include
    s = re.sub(r"^@", "", s)
    s = re.sub(r"^/+", "", s)
    # Prepend https:// if no protocol
    if not re.match(r"^https?://", s, re.IGNORECASE):
        s = "https://" + s
    try:
        parsed = urlparse(s)
        if not parsed.hostname or "." not in parsed.hostname:
            return s  # let the researcher agent surface the error downstream
        path = parsed.path or ""
        return urlunparse((parsed.scheme, parsed.netloc, path.rstrip("/"), "", "", ""))
    except Exception:
        return s


def _screener(req: AuditRequest) -> dict[str, str]:
    return {
        "industry": req.industry,
        "size": req.size,
        "role": req.role,
        "priority_function": req.priorityFunction,
    }


def _company_name(req: AuditRequest, normalized_url: str) -> str:
    if req.companyName:
        return req.companyName
    try:
        from urllib.parse import urlparse
        host = urlparse(normalized_url).hostname or normalized_url
        if not host:
            return "Company"
        label = host.replace("www.", "").split(".")[0]
        return label[:1].upper() + label[1:] if label else "Company"
    except Exception:
        return "Company"


@app.post("/api/audit-stream")
async def audit_stream(req: AuditRequest):
    """SSE stream of live agent events + final audit JSON."""
    bus = EventBus()

    normalized_url = _normalize_url(req.companyUrl)

    async def pipeline():
        try:
            await orchestrator.run_audit(
                url=normalized_url,
                company_name=_company_name(req, normalized_url),
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
    normalized_url = _normalize_url(req.companyUrl)
    result = await orchestrator.run_audit(
        url=normalized_url,
        company_name=_company_name(req, normalized_url),
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
