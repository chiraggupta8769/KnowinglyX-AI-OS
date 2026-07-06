"""
Job discovery service — fetches real jobs from free public APIs.
Sources: RemoteOK (remote jobs), Arbeitnow (global jobs)
No API key required.
"""
from __future__ import annotations

import asyncio
import logging
import json
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

REMOTEOK_URL = "https://remoteok.com/api"
ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; KnowinglyX/1.0; career-os)",
    "Accept": "application/json",
}


async def fetch_remoteok(keywords: list[str], limit: int = 20) -> list[dict]:
    """Fetch remote jobs from RemoteOK."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(REMOTEOK_URL, headers=HEADERS)
            resp.raise_for_status()
            jobs_raw = resp.json()

        # First item is a notice, skip it
        jobs = [j for j in jobs_raw if isinstance(j, dict) and j.get("position")]

        # Filter by keywords
        kw_lower = [k.lower() for k in keywords]
        matched = []
        for j in jobs:
            text = f"{j.get('position','')} {j.get('tags',[])} {j.get('description','')}".lower()
            if any(kw in text for kw in kw_lower):
                matched.append({
                    "id": str(j.get("id", "")),
                    "title": j.get("position", ""),
                    "company": j.get("company", ""),
                    "location": "Remote",
                    "url": j.get("url", f"https://remoteok.com/remote-jobs/{j.get('id','')}"),
                    "tags": j.get("tags", [])[:6],
                    "salary": j.get("salary", ""),
                    "posted_at": j.get("date", ""),
                    "source": "RemoteOK",
                })
            if len(matched) >= limit:
                break
        return matched
    except Exception as exc:
        logger.warning("RemoteOK fetch failed: %s", exc)
        return []


async def fetch_arbeitnow(keywords: list[str], limit: int = 20) -> list[dict]:
    """Fetch jobs from Arbeitnow."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                ARBEITNOW_URL,
                params={"page": 1},
                headers=HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()

        jobs = data.get("data", [])
        kw_lower = [k.lower() for k in keywords]
        matched = []
        for j in jobs:
            text = f"{j.get('title','')} {j.get('tags',[])} {j.get('description','')}".lower()
            if any(kw in text for kw in kw_lower):
                matched.append({
                    "id": j.get("slug", ""),
                    "title": j.get("title", ""),
                    "company": j.get("company_name", ""),
                    "location": j.get("location", "Remote") or "Remote",
                    "url": j.get("url", ""),
                    "tags": j.get("tags", [])[:6],
                    "salary": "",
                    "posted_at": j.get("created_at", ""),
                    "source": "Arbeitnow",
                })
            if len(matched) >= limit:
                break
        return matched
    except Exception as exc:
        logger.warning("Arbeitnow fetch failed: %s", exc)
        return []


async def find_matching_jobs(skills: list[str], roles: list[str], limit: int = 20) -> list[dict]:
    """Search both sources in parallel, dedupe, return top matches."""
    keywords = (roles + skills)[:8]  # Cap to avoid overly broad queries

    remote_jobs, arbeit_jobs = await asyncio.gather(
        fetch_remoteok(keywords, limit),
        fetch_arbeitnow(keywords, limit),
    )

    all_jobs = remote_jobs + arbeit_jobs

    # Dedupe by title+company
    seen = set()
    unique = []
    for j in all_jobs:
        key = f"{j['title'].lower()}_{j['company'].lower()}"
        if key not in seen:
            seen.add(key)
            unique.append(j)

    return unique[:limit]
