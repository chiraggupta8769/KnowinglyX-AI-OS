"""
Job discovery service — fetches real jobs from multiple free public APIs.
Sources: RemoteOK, Arbeitnow, Remotive
Smarter matching: role-based queries + relevance scoring.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; KnowinglyX/1.0)",
    "Accept": "application/json",
}


async def fetch_remoteok(keywords: list[str]) -> list[dict]:
    """Fetch from RemoteOK — search by tag slug."""
    results = []
    try:
        # Try each keyword as a RemoteOK tag
        for kw in keywords[:3]:
            slug = kw.lower().replace(" ", "-").replace(".", "")
            url = f"https://remoteok.com/api?tag={slug}"
            try:
                async with httpx.AsyncClient(timeout=8) as client:
                    resp = await client.get(url, headers=HEADERS)
                    if resp.status_code != 200:
                        continue
                    jobs_raw = resp.json()
                for j in jobs_raw:
                    if not isinstance(j, dict) or not j.get("position"):
                        continue
                    results.append({
                        "id": f"rok-{j.get('id','')}",
                        "title": j.get("position", ""),
                        "company": j.get("company", ""),
                        "location": "Remote",
                        "url": j.get("url", f"https://remoteok.com/l/{j.get('id','')}"),
                        "tags": (j.get("tags") or [])[:5],
                        "salary": j.get("salary", ""),
                        "source": "RemoteOK",
                    })
            except Exception:
                continue
    except Exception as exc:
        logger.warning("RemoteOK error: %s", exc)
    return results


async def fetch_remotive(keywords: list[str]) -> list[dict]:
    """Fetch from Remotive — free API, good tech job coverage."""
    results = []
    try:
        category_map = {
            "python": "software-dev", "javascript": "software-dev", "react": "software-dev",
            "node": "software-dev", "java": "software-dev", "typescript": "software-dev",
            "backend": "software-dev", "frontend": "software-dev", "fullstack": "software-dev",
            "full stack": "software-dev", "engineer": "software-dev", "developer": "software-dev",
            "devops": "devops-sysadmin", "cloud": "devops-sysadmin", "aws": "devops-sysadmin",
            "data": "data", "ml": "data", "machine learning": "data", "ai": "data",
            "design": "design", "ux": "design", "product": "product",
        }
        category = "software-dev"
        for kw in keywords:
            for k, v in category_map.items():
                if k in kw.lower():
                    category = v
                    break

        # Use httpx with proper headers — Remotive blocks default UA
        async with httpx.AsyncClient(
            timeout=10,
            headers={**HEADERS, "Accept": "application/json, text/plain, */*", "Referer": "https://remotive.com"},
        ) as client:
            resp = await client.get(
                "https://remotive.com/api/remote-jobs",
                params={"category": category, "limit": 25},
            )
            if resp.status_code != 200:
                logger.warning("Remotive returned %s", resp.status_code)
                return results
            data = resp.json()

        kw_lower = [k.lower() for k in keywords]
        for j in (data.get("jobs") or []):
            text = f"{j.get('title','')} {j.get('candidate_required_location','')} {j.get('tags','')}".lower()
            score = sum(1 for kw in kw_lower if kw in text)
            results.append({
                "id": f"rem-{j.get('id','')}",
                "title": j.get("title", ""),
                "company": j.get("company_name", ""),
                "location": j.get("candidate_required_location", "Remote") or "Remote",
                "url": j.get("url", ""),
                "tags": [t.strip() for t in (j.get("tags") or "").split(",") if t.strip()][:5],
                "salary": j.get("salary", ""),
                "source": "Remotive",
                "_score": score,
            })
    except Exception as exc:
        logger.warning("Remotive error: %s", exc)
    return results


async def fetch_arbeitnow(keywords: list[str]) -> list[dict]:
    """Fetch from Arbeitnow."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(
                "https://www.arbeitnow.com/api/job-board-api",
                params={"page": 1},
                headers=HEADERS,
            )
            if resp.status_code != 200:
                return results
            data = resp.json()

        kw_lower = [k.lower() for k in keywords]
        for j in (data.get("data") or []):
            text = f"{j.get('title','')} {' '.join(j.get('tags',[]))} {j.get('description','')}".lower()
            if any(kw in text for kw in kw_lower):
                results.append({
                    "id": f"arb-{j.get('slug','')}",
                    "title": j.get("title", ""),
                    "company": j.get("company_name", ""),
                    "location": j.get("location", "Remote") or "Remote",
                    "url": j.get("url", ""),
                    "tags": (j.get("tags") or [])[:5],
                    "salary": "",
                    "source": "Arbeitnow",
                })
    except Exception as exc:
        logger.warning("Arbeitnow error: %s", exc)
    return results


async def find_matching_jobs(skills: list[str], roles: list[str], limit: int = 20) -> list[dict]:
    """Search all sources in parallel, score and rank results."""
    # Build search keywords: roles first (more specific), then skills
    keywords = []
    for r in roles[:3]:
        keywords.append(r)
    for s in skills[:5]:
        if s.lower() not in [k.lower() for k in keywords]:
            keywords.append(s)

    if not keywords:
        keywords = ["software engineer", "developer"]

    # Fetch from all sources in parallel
    rok, remotive, arbeit = await asyncio.gather(
        fetch_remoteok(keywords),
        fetch_remotive(keywords),
        fetch_arbeitnow(keywords),
    )

    all_jobs = remotive + rok + arbeit  # Remotive first — better quality

    # Score all jobs by keyword relevance
    kw_lower = [k.lower() for k in keywords]
    for j in all_jobs:
        text = f"{j['title']} {j['company']} {' '.join(j.get('tags', []))}".lower()
        j["_score"] = j.get("_score", 0) + sum(1 for kw in kw_lower if kw in text)

    # Sort by relevance score, dedupe by title+company
    all_jobs.sort(key=lambda j: j.get("_score", 0), reverse=True)
    seen, unique = set(), []
    for j in all_jobs:
        key = f"{j['title'].lower().strip()}_{j['company'].lower().strip()}"
        if key not in seen and j.get("url"):
            seen.add(key)
            unique.append(j)

    # Clean up internal score field
    for j in unique:
        j.pop("_score", None)

    return unique[:limit]
