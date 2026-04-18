"""Deterministic scoring math — mirrors CLAUDE.md rules.

- Per-dimension score = mean(level) across 4 questions, rounded to 0.1
- Overall = mean of 5 dimension scores
- Target = min(current + 1, 4)
- Top 5 gaps = largest (target - current) per question,
  tiebreak by alignment with priority_function
"""

from __future__ import annotations

from typing import Any

DIMENSIONS = ["D1", "D2", "D3", "D4", "D5"]
QUESTIONS_PER_DIMENSION = 4


def dimension_score(answers: dict[str, dict]) -> dict[str, float]:
    """Mean level per dimension, rounded to 0.1."""
    by_dim: dict[str, list[int]] = {d: [] for d in DIMENSIONS}
    for qid, a in answers.items():
        dim = a.get("dimension")
        level = int(a.get("level", 1))
        if dim in by_dim:
            by_dim[dim].append(level)
    return {
        d: round(sum(levels) / len(levels), 1) if levels else 1.0
        for d, levels in by_dim.items()
    }


def overall_score(dim_scores: dict[str, float]) -> float:
    return round(sum(dim_scores.values()) / len(dim_scores), 1)


def target_levels(dim_scores: dict[str, float]) -> dict[str, int]:
    """Default target = min(ceil(current) + 1, 4). Floor to int first, then +1."""
    return {d: min(int(round(s)) + 1, 4) for d, s in dim_scores.items()}


def top_gaps(
    answers: dict[str, dict],
    targets: dict[str, int],
    priority_function: str = "",
    limit: int = 5,
) -> list[dict]:
    """Rank questions by (target - current), tiebreak by alignment with priority_function."""
    priority_tokens = {
        tok for tok in priority_function.lower().split() if len(tok) > 3
    }

    def alignment_bonus(question_text: str) -> float:
        if not priority_tokens:
            return 0.0
        qtoks = set(question_text.lower().split())
        overlap = len(priority_tokens & qtoks)
        return 0.01 * overlap

    scored: list[dict] = []
    for qid, a in answers.items():
        dim = a.get("dimension")
        current = int(a.get("level", 1))
        target = targets.get(dim, min(current + 1, 4))
        gap = max(target - current, 0)
        scored.append({
            "qid": qid,
            "dimension": dim,
            "current": current,
            "target": target,
            "gap": gap,
            "stem": a.get("stem", ""),
            "evidence": a.get("evidence", []),
            "discovery_needed": bool(a.get("discovery_needed")),
            "_rank_key": gap + alignment_bonus(a.get("stem", "")),
        })

    scored.sort(key=lambda x: x["_rank_key"], reverse=True)
    for s in scored:
        s.pop("_rank_key", None)
    return [s for s in scored if s["gap"] > 0][:limit]


def compute_report(
    answers: dict[str, dict],
    priority_function: str = "",
) -> dict[str, Any]:
    """Full scorecard: per-dim, overall, targets, top 5 gaps."""
    dims = dimension_score(answers)
    overall = overall_score(dims)
    targets = target_levels(dims)
    gaps = top_gaps(answers, targets, priority_function)
    return {
        "dimension_scores": dims,
        "overall_score": overall,
        "target_levels": targets,
        "top_gaps": gaps,
    }
