"""
Ghost job detection — Tier 1 heuristic, zero LLM, instant.
Badges: 🟢 Fresh | 🟡 Stale | 🔴 Flagged
"""
from __future__ import annotations
import re
from datetime import datetime, timezone

GHOST_BLOCKLIST = [
    "not accepting applications", "position filled", "this position has been filled",
    "no longer accepting", "closed", "expired", "position closed",
]

SUSPICIOUS_PATTERNS = [
    r"(\d+)-\d+ years required",          # very wide experience bands (e.g. 0-15 years)
    r"immediate joiners? (only|preferred)", # high-churn signal
    r"freshers? (can apply|are welcome)",   # sometimes filler posts
]


def ghost_score(job: dict) -> dict:
    """
    Return ghost assessment for a job.
    Output: {label, color, reason, fresh: bool}
    """
    title = job.get("title", "")
    company = job.get("company", "")
    description = (job.get("description") or "").lower()
    posted_at = job.get("posted_at") or job.get("date") or ""
    source = job.get("source", "")

    # Tier 1a — blocklist
    for phrase in GHOST_BLOCKLIST:
        if phrase in description:
            return {"label": "Likely closed", "color": "red", "reason": "Job description indicates position may be filled", "fresh": False}

    # Tier 1b — posting age
    age_days = _parse_age_days(posted_at)
    if age_days is not None:
        if age_days > 60:
            return {"label": "Stale (60+ days)", "color": "red", "reason": f"Posted {age_days} days ago — may no longer be active", "fresh": False}
        if age_days > 30:
            return {"label": "Stale (30+ days)", "color": "yellow", "reason": f"Posted {age_days} days ago — verify it's still open", "fresh": False}
        if age_days <= 7:
            return {"label": "Fresh", "color": "green", "reason": f"Posted {age_days} days ago", "fresh": True}
        return {"label": "Recent", "color": "green", "reason": f"Posted {age_days} days ago", "fresh": True}

    # Tier 1c — no date, unknown freshness
    return {"label": "Date unknown", "color": "gray", "reason": "No posting date available", "fresh": None}


def _parse_age_days(posted_at: str) -> int | None:
    """Try to parse a date string and return days since posting."""
    if not posted_at:
        return None
    try:
        # ISO format
        dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - dt).days
    except Exception:
        pass
    try:
        # Unix timestamp
        dt = datetime.fromtimestamp(int(posted_at), tz=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - dt).days
    except Exception:
        pass
    return None
