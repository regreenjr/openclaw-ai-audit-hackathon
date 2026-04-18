"""Supabase persistence for audit sessions.

Single-table model (public.audit_sessions):
  created → scraped → quizzed → reported

All methods are safe to call without Supabase configured — they no-op and
log a warning. Lets us develop/demo even if the DB is down.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

try:
    from supabase import Client, create_client  # type: ignore
except ImportError:
    Client = None  # type: ignore
    create_client = None  # type: ignore

log = logging.getLogger(__name__)
TABLE = "audit_sessions"


_client_singleton: Optional["Client"] = None


def get_client() -> Optional["Client"]:
    """Return a cached Supabase client, or None if not configured."""
    global _client_singleton
    if _client_singleton is not None:
        return _client_singleton
    if create_client is None:
        log.warning("supabase package not installed — persistence disabled")
        return None
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        log.warning("SUPABASE_URL / SUPABASE_KEY not set — persistence disabled")
        return None
    _client_singleton = create_client(url, key)
    return _client_singleton


def is_enabled() -> bool:
    return get_client() is not None


def create_session(
    company_url: str,
    company_name: str,
    screener: dict[str, Any],
    contextual: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """Insert a new session row, return its id."""
    c = get_client()
    if c is None:
        return None
    try:
        row = {
            "company_url": company_url,
            "company_name": company_name,
            "screener": screener,
            "contextual": contextual or {},
            "status": "created",
        }
        res = c.table(TABLE).insert(row).execute()
        session_id = res.data[0]["id"]
        log.info(f"db.create_session id={session_id}")
        return session_id
    except Exception as e:
        log.error(f"db.create_session failed: {e}")
        return None


def update_scraped(
    session_id: str,
    evidence: dict[str, Any],
    answers: dict[str, dict[str, Any]],
    scorecard: dict[str, Any],
    narrative: dict[str, Any],
    value_chain_plays: list[dict[str, Any]],
) -> None:
    c = get_client()
    if c is None or not session_id:
        return
    try:
        c.table(TABLE).update({
            "scraped_evidence": evidence,
            "scraped_answers": answers,
            "scraped_scorecard": scorecard,
            "scraped_narrative": narrative,
            "scraped_value_chain_plays": value_chain_plays,
            "status": "scraped",
        }).eq("id", session_id).execute()
        log.info(f"db.update_scraped id={session_id}")
    except Exception as e:
        log.error(f"db.update_scraped failed: {e}")


def update_quiz(session_id: str, quiz_answers: dict[str, int]) -> bool:
    c = get_client()
    if c is None or not session_id:
        return False
    try:
        from datetime import datetime, timezone
        c.table(TABLE).update({
            "quiz_answers": quiz_answers,
            "quiz_submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": "quizzed",
        }).eq("id", session_id).execute()
        log.info(f"db.update_quiz id={session_id} answers={len(quiz_answers)}")
        return True
    except Exception as e:
        log.error(f"db.update_quiz failed: {e}")
        return False


def update_combined(
    session_id: str,
    combined_scorecard: dict[str, Any],
    combined_narrative: dict[str, Any],
    combined_value_chain_plays: list[dict[str, Any]],
    combined_vendor_recs: Optional[dict[str, Any]] = None,
    combined_regulatory_scan: Optional[dict[str, Any]] = None,
) -> None:
    c = get_client()
    if c is None or not session_id:
        return
    try:
        from datetime import datetime, timezone
        payload: dict[str, Any] = {
            "combined_scorecard": combined_scorecard,
            "combined_narrative": combined_narrative,
            "combined_value_chain_plays": combined_value_chain_plays,
            "combined_report_at": datetime.now(timezone.utc).isoformat(),
            "status": "reported",
        }
        # Optional columns — skip if Supabase doesn't have them yet (migration pending)
        if combined_vendor_recs is not None:
            payload["combined_vendor_recs"] = combined_vendor_recs
        if combined_regulatory_scan is not None:
            payload["combined_regulatory_scan"] = combined_regulatory_scan
        c.table(TABLE).update(payload).eq("id", session_id).execute()
        log.info(f"db.update_combined id={session_id}")
    except Exception as e:
        log.error(f"db.update_combined failed: {e}")


def get_session(session_id: str) -> Optional[dict[str, Any]]:
    c = get_client()
    if c is None or not session_id:
        return None
    try:
        res = c.table(TABLE).select("*").eq("id", session_id).maybe_single().execute()
        return res.data if res and res.data else None
    except Exception as e:
        log.error(f"db.get_session failed: {e}")
        return None
