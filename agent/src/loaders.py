"""Load framework.json and questions.json from repo root."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def load_framework() -> dict[str, Any]:
    with (REPO_ROOT / "framework.json").open() as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_questions() -> dict[str, Any]:
    with (REPO_ROOT / "questions.json").open() as f:
        return json.load(f)


def dimension_cells_text(dim_id: str) -> str:
    """Formatted rubric cells (L1-L4 with current_state + next_moves) for a dimension."""
    fw = load_framework()
    dim = next(d for d in fw["dimensions"] if d["id"] == dim_id)
    lines: list[str] = []
    for cell in dim["cells"]:
        lvl = cell["level"]
        lines.append(f"\n**{lvl} — {next(l['name'] for l in fw['levels'] if l['id'] == lvl)}**")
        lines.append(f"Current state: {cell['current_state']}")
        moves = cell.get("next_moves") or cell.get("sustain_extend") or []
        if moves:
            label = "Sustain & extend" if cell.get("sustain_extend") else "Next moves"
            lines.append(f"{label}:")
            for m in moves:
                lines.append(f"  - {m}")
    return "\n".join(lines)


def dimension_questions_text(dim_id: str) -> str:
    """Formatted list of the 4 scored questions in a dimension with their 4 level options."""
    qs = load_questions()
    out: list[str] = []
    for q in qs["scored"]:
        if q["dimension"] != dim_id:
            continue
        out.append(f"\n**{q['id']}.** {q['stem']}")
        for opt in q["options"]:
            flag = " [discovery_needed]" if opt.get("flag") == "discovery_needed" else ""
            out.append(f"  L{opt['level']}: {opt['text']}{flag}")
    return "\n".join(out)


def dimension_questions_list(dim_id: str) -> list[dict[str, Any]]:
    """Raw list of questions for a dimension (for merge/scoring)."""
    return [q for q in load_questions()["scored"] if q["dimension"] == dim_id]


def first_question_id(dim_id: str) -> str:
    qs = dimension_questions_list(dim_id)
    return qs[0]["id"] if qs else "Q?"


def dimension_name(dim_id: str) -> str:
    fw = load_framework()
    return next(d["name"] for d in fw["dimensions"] if d["id"] == dim_id)


def current_cell(dim_id: str, level: int) -> dict[str, Any]:
    fw = load_framework()
    dim = next(d for d in fw["dimensions"] if d["id"] == dim_id)
    level_str = f"L{level}"
    return next(c for c in dim["cells"] if c["level"] == level_str)
