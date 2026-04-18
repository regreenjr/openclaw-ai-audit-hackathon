"""Orchestrates the multi-agent audit pipeline.

Phases:
1. Researcher  — one sub-agent with fetch_url tool, emits evidence dossier
2. 5 Specialists (parallel) — each predicts L1-L4 for its 4 questions with citations
3. Critic     — challenges weak scores, enforces discovery_needed flag
4. Scoring    — deterministic math from Mkal72's rules (not LLM)
5. Synthesizer — writes exec summary, top-gaps narrative, 90-day roadmap

Each agent is a separate query() call to Claude Agent SDK with an isolated context
window. Parallelism via asyncio.gather. Events stream to frontend via SSE.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Callable

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

from . import db, loaders, prompts, scoring
from .events import AuditEvent, EventBus
from .tools import build_research_server

DIMENSIONS = ["D1", "D2", "D3", "D4", "D5"]

MODEL_FAST = "claude-sonnet-4-6"   # specialists + researcher
MODEL_DEEP = "claude-opus-4-7"     # critic + synthesizer — deeper reasoning


JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)


def extract_json(text: str) -> dict[str, Any] | None:
    """Extract the last fenced ```json block from an agent response."""
    matches = JSON_BLOCK_RE.findall(text)
    if not matches:
        # Fallback: try the whole thing
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return None
    for raw in reversed(matches):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue
    return None


async def _stream_agent(
    agent_id: str,
    prompt_text: str,
    options: ClaudeAgentOptions,
    bus: EventBus,
) -> str:
    """Run a single sub-agent, stream its thoughts + tool uses, return concatenated assistant text."""
    await bus.emit(AuditEvent(type="agent.start", agent=agent_id))
    chunks: list[str] = []
    try:
        async for msg in query(prompt=prompt_text, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
                        # Emit short preview — keep terminal scroll reasonable
                        preview = block.text.strip().split("\n")[0][:180]
                        if preview:
                            await bus.emit(AuditEvent(
                                type="agent.thought",
                                agent=agent_id,
                                data={"text": preview},
                            ))
                    elif isinstance(block, ToolUseBlock):
                        await bus.emit(AuditEvent(
                            type="agent.tool_use",
                            agent=agent_id,
                            data={"tool": block.name, "input": block.input},
                        ))
            elif isinstance(msg, ResultMessage):
                await bus.emit(AuditEvent(
                    type="agent.done",
                    agent=agent_id,
                    data={
                        "cost_usd": round(getattr(msg, "total_cost_usd", 0.0) or 0.0, 4),
                        "duration_ms": getattr(msg, "duration_ms", 0),
                    },
                ))
    except Exception as e:
        await bus.emit(AuditEvent(
            type="agent.error",
            agent=agent_id,
            data={"error": str(e)},
        ))
        raise
    return "".join(chunks)


async def run_researcher(
    url: str,
    company_name: str,
    bus: EventBus,
) -> dict[str, Any]:
    server = build_research_server()
    options = ClaudeAgentOptions(
        system_prompt=prompts.RESEARCHER_SYSTEM,
        mcp_servers={"research": server},
        allowed_tools=["mcp__research__fetch_url"],
        model=MODEL_FAST,
        max_turns=5,  # hard cap: 1 turn for fetches, 1 for JSON output, 3 safety buffer
    )
    user_prompt = (
        f"Research the company: **{company_name}**\n"
        f"Starting URL: {url}\n\n"
        "Use fetch_url to gather evidence from the homepage and 5-8 relevant deeper pages "
        "(about/team/careers/blog/security/trust/product). Prioritize pages that speak to AI "
        "strategy, data/engineering, talent posture, governance, and shipped AI features. "
        "End with the JSON dossier."
    )
    text = await _stream_agent("researcher", user_prompt, options, bus)
    dossier = extract_json(text) or {"company_summary": "", "signals": {d: [] for d in DIMENSIONS}, "sources": []}
    await bus.emit(AuditEvent(type="evidence", agent="researcher", data=dossier))
    return dossier


async def run_specialist(
    dim_id: str,
    evidence: dict[str, Any],
    bus: EventBus,
) -> dict[str, Any]:
    dim_name = loaders.dimension_name(dim_id)
    agent_id = f"specialist.{dim_id}"
    cells_text = loaders.dimension_cells_text(dim_id)
    questions_text = loaders.dimension_questions_text(dim_id)
    q_start = loaders.first_question_id(dim_id).replace("Q", "")
    system = prompts.SPECIALIST_SYSTEM.format(
        dim_id=dim_id,
        dim_name=dim_name,
        dim_cells=cells_text,
        dim_questions=questions_text,
        evidence=json.dumps(evidence, indent=2),
        q_start=q_start,
    )
    options = ClaudeAgentOptions(
        system_prompt=system,
        allowed_tools=[],
        model=MODEL_FAST,
        max_turns=2,
    )
    user_prompt = (
        f"Score the 4 questions for dimension {dim_id} ({dim_name}) against the evidence above. "
        "For each question, pick the level that best fits, cite 1-3 evidence quotes, set confidence, "
        "and flag discovery_needed where evidence is thin. End with the JSON block."
    )
    text = await _stream_agent(agent_id, user_prompt, options, bus)
    parsed = extract_json(text) or {"dimension": dim_id, "answers": {}}

    # Stitch stem from questions.json if specialist forgot to include it
    for q in loaders.dimension_questions_list(dim_id):
        qid = q["id"]
        if qid in parsed.get("answers", {}):
            parsed["answers"][qid].setdefault("stem", q["stem"])
            parsed["answers"][qid].setdefault("dimension", dim_id)

    await bus.emit(AuditEvent(type="specialist.result", agent=agent_id, data=parsed))
    return parsed


async def _run_critic_dim(
    dim_id: str,
    specialist_result: dict[str, Any],
    bus: EventBus,
) -> dict[str, Any]:
    """Per-dimension critic. Lightweight — emits thoughts/challenges under 'critic.{dim}'
    but not agent.start/done (aggregate wrapper handles those for the UI)."""
    dim_name = loaders.dimension_name(dim_id)
    agent_id = f"critic.{dim_id}"
    system = prompts.CRITIC_DIM_SYSTEM.format(
        dim_id=dim_id,
        dim_name=dim_name,
        specialist_result=json.dumps(specialist_result, indent=2),
    )
    options = ClaudeAgentOptions(
        system_prompt=system,
        allowed_tools=[],
        model=MODEL_FAST,
        max_turns=1,
    )
    user_prompt = f"Review the {dim_id} specialist's 4 scores. Revise only weak ones. JSON only."
    chunks: list[str] = []
    try:
        async for msg in query(prompt=user_prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
    except Exception as e:
        await bus.emit(AuditEvent(type="agent.error", agent=agent_id, data={"error": str(e)}))
        return {"revisions": {}, "challenges_raised": []}
    text = "".join(chunks)
    parsed = extract_json(text) or {"revisions": {}, "challenges_raised": []}
    for ch in parsed.get("challenges_raised", []):
        await bus.emit(AuditEvent(type="critic.challenge", agent=agent_id, data={"text": ch}))
    return parsed


async def run_critic(
    specialist_results: list[dict[str, Any]],
    bus: EventBus,
) -> dict[str, dict[str, Any]]:
    """Run 5 per-dimension critics in parallel — massively faster than one critic over 20 answers."""
    await bus.emit(AuditEvent(type="agent.start", agent="critic"))
    per_dim_results = await asyncio.gather(*[
        _run_critic_dim(sr.get("dimension", "D?"), sr, bus) for sr in specialist_results
    ])

    # Merge back: start from specialist answers, overlay per-dim revisions
    merged: dict[str, dict[str, Any]] = {}
    for sr in specialist_results:
        for qid, ans in sr.get("answers", {}).items():
            merged[qid] = dict(ans)
    total_revisions = 0
    for dr in per_dim_results:
        for qid, rev in dr.get("revisions", {}).items():
            merged[qid] = dict(rev)
            total_revisions += 1

    await bus.emit(AuditEvent(
        type="critic.result", agent="critic",
        data={"revisions_count": total_revisions, "parallel_critics": len(per_dim_results)},
    ))
    await bus.emit(AuditEvent(type="agent.done", agent="critic", data={}))
    return merged


async def run_synthesizer(
    scorecard: dict[str, Any],
    answers: dict[str, dict[str, Any]],
    screener: dict[str, str],
    bus: EventBus,
) -> dict[str, Any]:
    # Pull the current-level cell for each dimension to seed the narrative
    current_cells: dict[str, dict] = {}
    next_moves: dict[str, list[str]] = {}
    for dim_id in DIMENSIONS:
        cur_level = int(round(scorecard["dimension_scores"][dim_id]))
        cur_level = max(1, min(cur_level, 4))
        cell = loaders.current_cell(dim_id, cur_level)
        current_cells[dim_id] = {
            "level": f"L{cur_level}",
            "name": loaders.dimension_name(dim_id),
            "current_state": cell["current_state"],
        }
        next_moves[dim_id] = cell.get("next_moves") or cell.get("sustain_extend") or []

    system = prompts.SYNTHESIZER_SYSTEM.format(
        industry=screener.get("industry", "unknown"),
        size=screener.get("size", "unknown"),
        role=screener.get("role", "unknown"),
        priority_function=screener.get("priority_function", "unknown"),
        scorecard=json.dumps(scorecard, indent=2),
        top_gaps=json.dumps(scorecard.get("top_gaps", []), indent=2),
        current_cells=json.dumps(current_cells, indent=2),
        next_moves=json.dumps(next_moves, indent=2),
    )
    options = ClaudeAgentOptions(
        system_prompt=system,
        allowed_tools=[],
        model=MODEL_FAST,  # Sonnet 4.6 — structured JSON output for the PDF report
        max_turns=1,
    )
    user_prompt = (
        "Write the three narrative sections for the 6-page PDF report. Reference the client's "
        "priority function and industry naturally. Stick to the scorecard and next_moves provided. "
        "Be concise — the PDF has limited page real estate."
    )
    text = await _stream_agent("synthesizer", user_prompt, options, bus)
    parsed = extract_json(text) or {
        "exec_summary": "",
        "top_gaps_narrative": "",
        "roadmap_90_day": {"30_days": [], "60_days": [], "90_days": []},
    }
    await bus.emit(AuditEvent(type="narrative", agent="synthesizer", data=parsed))
    return parsed


async def run_value_chain_strategist(
    scorecard: dict[str, Any],
    screener: dict[str, str],
    synthesizer_result: dict[str, Any],
    bus: EventBus,
) -> list[dict[str, Any]]:
    system = prompts.VALUE_CHAIN_SYSTEM.format(
        industry=screener.get("industry", "unknown"),
        size=screener.get("size", "unknown"),
        priority_function=screener.get("priority_function", "unknown"),
        scorecard=json.dumps(scorecard, indent=2),
        top_gaps=json.dumps(scorecard.get("top_gaps", []), indent=2),
        synthesizer_narrative=json.dumps(synthesizer_result, indent=2),
    )
    options = ClaudeAgentOptions(
        system_prompt=system,
        allowed_tools=[],
        model=MODEL_FAST,  # Sonnet 4.6 — structured JSON output, speed over depth
        max_turns=1,
    )
    user_prompt = (
        "Produce 3-5 Porter Value Chain plays tied to the top_gaps and priority_function. "
        "One activity per play, no duplicates, max 2 at priority 1. End with the JSON block."
    )
    text = await _stream_agent("value_chain_strategist", user_prompt, options, bus)
    parsed = extract_json(text)
    if parsed is None:
        print("[value_chain_strategist] WARN: extract_json returned None — defaulting to [].")
        plays: list[dict[str, Any]] = []
    else:
        plays = parsed.get("plays", []) or []
    await bus.emit(AuditEvent(
        type="value_chain",
        agent="value_chain_strategist",
        data={"plays": plays},
    ))
    return plays


async def run_audit(
    url: str,
    company_name: str,
    screener: dict[str, str],
    bus: EventBus,
) -> dict[str, Any]:
    """Top-level pipeline."""
    try:
        # Create persistent session row in Supabase (no-ops if not configured)
        session_id = db.create_session(
            company_url=url,
            company_name=company_name,
            screener=screener,
        )
        await bus.emit(AuditEvent(type="pipeline.start", agent="orchestrator", data={
            "company_name": company_name, "url": url,
            "session_id": session_id,
        }))

        # Phase 1: Research
        evidence = await run_researcher(url, company_name, bus)

        # Phase 2: 5 Specialists in parallel
        await bus.emit(AuditEvent(type="pipeline.phase", agent="orchestrator",
                                  data={"phase": "specialists", "count": 5}))
        specialist_results = await asyncio.gather(
            *[run_specialist(d, evidence, bus) for d in DIMENSIONS]
        )

        # Preliminary scorecard from specialists ONLY — emit now so UI renders immediately
        preliminary_answers: dict[str, dict[str, Any]] = {}
        for sr in specialist_results:
            for qid, ans in sr.get("answers", {}).items():
                preliminary_answers[qid] = dict(ans)
        prelim_scorecard = scoring.compute_report(
            preliminary_answers,
            priority_function=screener.get("priority_function", ""),
        )
        await bus.emit(AuditEvent(
            type="scorecard", agent="orchestrator",
            data={**prelim_scorecard, "preliminary": True},
        ))

        # Phases 3+5+6 PARALLEL: critic (5 per-dim in parallel internally) + synthesizer + value chain.
        # Synth and VCS use the preliminary scorecard; final scorecard re-emits if critic revises.
        await bus.emit(AuditEvent(type="pipeline.phase", agent="orchestrator",
                                  data={"phase": "critic + synth + value_chain (parallel)"}))

        async def _critic_then_rescore() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
            merged = await run_critic(specialist_results, bus)
            final = scoring.compute_report(
                merged, priority_function=screener.get("priority_function", ""),
            )
            # Re-emit scorecard with critic revisions merged in
            await bus.emit(AuditEvent(
                type="scorecard", agent="orchestrator",
                data={**final, "preliminary": False},
            ))
            return merged, final

        (merged_and_final, narrative, value_chain_plays) = await asyncio.gather(
            _critic_then_rescore(),
            run_synthesizer(prelim_scorecard, preliminary_answers, screener, bus),
            run_value_chain_strategist(prelim_scorecard, screener, {}, bus),
        )
        merged_answers, scorecard = merged_and_final

        # Persist scraped phase output
        db.update_scraped(
            session_id=session_id or "",
            evidence=evidence,
            answers=merged_answers,
            scorecard=scorecard,
            narrative=narrative,
            value_chain_plays=value_chain_plays,
        )

        result = {
            "session_id": session_id,
            "company_name": company_name,
            "url": url,
            "screener": screener,
            "evidence": evidence,
            "answers": merged_answers,
            "scorecard": scorecard,
            "narrative": narrative,
            "value_chain_plays": value_chain_plays,
        }
        await bus.emit(AuditEvent(type="pipeline.complete", agent="orchestrator", data={
            "overall_score": scorecard["overall_score"],
            "session_id": session_id,
        }))
        return result
    except Exception as e:
        await bus.emit(AuditEvent(type="pipeline.error", agent="orchestrator",
                                  data={"error": str(e), "type": type(e).__name__}))
        raise
    finally:
        await bus.close()


# =============================================================================
# Vendor recommendations + regulatory scan (ported from Mkal72/aiauditapp)
# =============================================================================

REGULATED_INDUSTRY_KEYWORDS = [
    "accounting", "tax", "audit", "bookkeep", "cpa",
    "health", "medical", "clinic", "dental", "pharma", "biotech",
    "law", "legal", "attorney",
    "finance", "financial", "bank", "wealth", "advisor",
    "insurance", "broker",
    "real estate", "mortgage", "credit",
    "education", "school", "childcare",
    "hr", "payroll", "benefits",
    "government", "gov", "public sector",
]


def regulatory_applies(screener: dict[str, Any], scorecard: dict[str, Any]) -> bool:
    """Gate for regulatory scan: run only when industry matches a regulated keyword
    OR the audit surfaced a compliance-flavored gap with discovery_needed."""
    industry = (screener.get("industry") or "").lower()
    if any(kw in industry for kw in REGULATED_INDUSTRY_KEYWORDS):
        return True
    for gap in scorecard.get("top_gaps", []):
        if gap.get("discovery_needed") and re.search(
            r"compliance|regulat", gap.get("stem", "") or "", re.IGNORECASE
        ):
            return True
    return False


async def run_vendor_recs(
    scorecard: dict[str, Any],
    screener: dict[str, str],
    contextual: dict[str, Any],
    bus: EventBus,
) -> dict[str, Any]:
    system = prompts.VENDOR_RECS_SYSTEM.format(
        industry=screener.get("industry", "unknown"),
        size=screener.get("size", "unknown"),
        priority_function=screener.get("priority_function", "unknown"),
        painful_workflow=(contextual.get("painful_workflow") or "not specified")[:500],
        top_gaps=json.dumps(scorecard.get("top_gaps", [])[:5], indent=2),
    )
    options = ClaudeAgentOptions(
        system_prompt=system,
        allowed_tools=[],
        model=MODEL_FAST,
        max_turns=1,
    )
    user_prompt = (
        "Produce a vendor shortlist for the 2-3 most actionable gaps. "
        "Real products only, current pricing, end with the JSON block."
    )
    text = await _stream_agent("vendor_recs", user_prompt, options, bus)
    parsed = extract_json(text) or {"shortlists": []}
    result = {"shortlists": parsed.get("shortlists", []) or []}
    await bus.emit(AuditEvent(type="vendor_recs", agent="vendor_recs", data=result))
    return result


async def run_regulatory_scan(
    screener: dict[str, str],
    contextual: dict[str, Any],
    bus: EventBus,
) -> dict[str, Any]:
    system = prompts.REGULATORY_SCAN_SYSTEM.format(
        industry=screener.get("industry", "unknown"),
        size=screener.get("size", "unknown"),
        priority_function=screener.get("priority_function", "unknown"),
        painful_workflow=(contextual.get("painful_workflow") or "not specified")[:500],
    )
    options = ClaudeAgentOptions(
        system_prompt=system,
        allowed_tools=[],
        model=MODEL_FAST,
        max_turns=1,
    )
    user_prompt = (
        "Identify 2-6 regulations that meaningfully constrain AI use for this firm, "
        "plus 2-5 discovery flags to raise on the expert call. End with the JSON block."
    )
    text = await _stream_agent("regulatory_scan", user_prompt, options, bus)
    parsed = extract_json(text) or {"applicable_regulations": [], "discovery_flags": []}
    result = {
        "applicable_regulations": parsed.get("applicable_regulations", []) or [],
        "discovery_flags": parsed.get("discovery_flags", []) or [],
    }
    await bus.emit(AuditEvent(type="regulatory_scan", agent="regulatory_scan", data=result))
    return result


# =============================================================================
# Combined report — fuses scraped agent output with user quiz answers
# =============================================================================

def _merge_scraped_and_quiz(
    scraped_answers: dict[str, dict[str, Any]],
    quiz_answers: dict[str, int],
) -> dict[str, dict[str, Any]]:
    """Merge rules:
    - User quiz answer is authoritative (level 1-4 overrides the agent prediction)
    - User "Don't know" (level 0) → fall back to scraped level, flag discovery_needed
    - If scraped is missing (edge case) → use user answer as-is

    Evidence/stem/dimension are preserved from the scraped record for citation.
    """
    merged: dict[str, dict[str, Any]] = {}
    all_qids = set(scraped_answers.keys()) | set(quiz_answers.keys())
    for qid in all_qids:
        scraped = scraped_answers.get(qid, {})
        user_level = quiz_answers.get(qid)

        base = {
            "dimension": scraped.get("dimension", ""),
            "stem": scraped.get("stem", ""),
            "evidence": scraped.get("evidence", []),
            "scraped_level": scraped.get("level"),
            "scraped_confidence": scraped.get("confidence"),
        }

        if user_level is None:
            # No quiz answer recorded — use scraped prediction
            merged[qid] = {
                **base,
                "level": scraped.get("level", 1),
                "confidence": scraped.get("confidence", 0.0),
                "discovery_needed": bool(scraped.get("discovery_needed")),
                "source": "scraped_only",
                "confirmed_by_user": False,
            }
        elif user_level == 0:
            # User selected "Don't know" — scraped fallback + discovery flag
            merged[qid] = {
                **base,
                "level": scraped.get("level", 1) or 1,
                "confidence": 0.3,
                "discovery_needed": True,
                "source": "user_dont_know",
                "confirmed_by_user": False,
            }
        else:
            # User answered — their answer wins
            merged[qid] = {
                **base,
                "level": user_level,
                "confidence": 1.0,  # user-confirmed
                "discovery_needed": False,
                "source": "user_quiz",
                "confirmed_by_user": True,
                "agreed_with_agent": scraped.get("level") == user_level,
            }
    return merged


async def run_combined_report(session_id: str, bus: EventBus) -> dict[str, Any]:
    """Chunk H — fuses scraped agent output with user quiz answers into a final report.

    Phases emitted for UI streaming:
    1. combined.merging       — deterministic merge of scraped + quiz
    2. combined.scoring       — re-run scoring math on merged answer set
    3. combined.synthesizing  — synthesizer + value_chain in parallel on combined scorecard
    4. combined.complete      — persist + return
    """
    await bus.emit(AuditEvent(type="combined.start", agent="combiner",
                              data={"session_id": session_id}))

    session = db.get_session(session_id)
    if not session:
        await bus.emit(AuditEvent(type="combined.error", agent="combiner",
                                  data={"error": f"Session {session_id} not found"}))
        raise ValueError(f"Session {session_id} not found")

    scraped_answers = session.get("scraped_answers") or {}
    quiz_answers = session.get("quiz_answers") or {}
    screener = session.get("screener") or {}

    if not scraped_answers:
        raise ValueError("Session has no scraped_answers — run audit first")
    if not quiz_answers:
        raise ValueError("Session has no quiz_answers — submit quiz first")

    # Phase 1: merge
    await bus.emit(AuditEvent(type="combined.phase", agent="combiner",
                              data={"phase": "merging scraped + quiz answers"}))
    merged_answers = _merge_scraped_and_quiz(scraped_answers, quiz_answers)

    confirmed = sum(1 for a in merged_answers.values() if a.get("confirmed_by_user"))
    discovery = sum(1 for a in merged_answers.values() if a.get("discovery_needed"))
    agreed = sum(1 for a in merged_answers.values() if a.get("agreed_with_agent"))
    await bus.emit(AuditEvent(type="combined.merged", agent="combiner", data={
        "total_questions": len(merged_answers),
        "user_confirmed": confirmed,
        "agreed_with_agent": agreed,
        "discovery_needed": discovery,
    }))

    # Phase 2: re-score
    await bus.emit(AuditEvent(type="combined.phase", agent="combiner",
                              data={"phase": "scoring merged answers"}))
    combined_scorecard = scoring.compute_report(
        merged_answers,
        priority_function=screener.get("priority_function", ""),
    )
    await bus.emit(AuditEvent(type="scorecard", agent="combiner",
                              data={**combined_scorecard, "source": "combined"}))

    # Phase 3: synthesizer + value_chain + vendor_recs + (optional) regulatory_scan in parallel
    run_regulatory = regulatory_applies(screener, combined_scorecard)
    contextual = session.get("contextual") or {}
    parallel_desc = "synthesizer + value_chain + vendor_recs"
    if run_regulatory:
        parallel_desc += " + regulatory_scan"
    await bus.emit(AuditEvent(type="combined.phase", agent="combiner",
                              data={"phase": f"{parallel_desc} (parallel)"}))

    tasks = [
        run_synthesizer(combined_scorecard, merged_answers, screener, bus),
        run_value_chain_strategist(combined_scorecard, screener, {}, bus),
        run_vendor_recs(combined_scorecard, screener, contextual, bus),
    ]
    if run_regulatory:
        tasks.append(run_regulatory_scan(screener, contextual, bus))

    results = await asyncio.gather(*tasks)
    combined_narrative = results[0]
    combined_value_chain_plays = results[1]
    combined_vendor_recs = results[2]
    combined_regulatory_scan = results[3] if run_regulatory else None

    # Phase 4: persist
    db.update_combined(
        session_id=session_id,
        combined_scorecard=combined_scorecard,
        combined_narrative=combined_narrative,
        combined_value_chain_plays=combined_value_chain_plays,
        combined_vendor_recs=combined_vendor_recs,
        combined_regulatory_scan=combined_regulatory_scan,
    )

    result = {
        "session_id": session_id,
        "source": "combined",
        "answers": merged_answers,
        "scorecard": combined_scorecard,
        "narrative": combined_narrative,
        "value_chain_plays": combined_value_chain_plays,
        "vendor_recs": combined_vendor_recs,
        "regulatory_scan": combined_regulatory_scan,
        "fusion_stats": {
            "total_questions": len(merged_answers),
            "user_confirmed": confirmed,
            "agreed_with_agent": agreed,
            "discovery_needed": discovery,
            "regulatory_applicable": run_regulatory,
        },
    }
    await bus.emit(AuditEvent(type="combined.complete", agent="combiner", data={
        "overall_score": combined_scorecard["overall_score"],
        "session_id": session_id,
    }))
    return result
