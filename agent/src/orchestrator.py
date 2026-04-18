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

from . import loaders, prompts, scoring
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
        await bus.emit(AuditEvent(type="pipeline.start", agent="orchestrator", data={
            "company_name": company_name, "url": url,
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

        result = {
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
        }))
        return result
    except Exception as e:
        await bus.emit(AuditEvent(type="pipeline.error", agent="orchestrator",
                                  data={"error": str(e), "type": type(e).__name__}))
        raise
    finally:
        await bus.close()
