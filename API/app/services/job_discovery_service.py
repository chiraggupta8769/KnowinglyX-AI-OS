"""
Job discovery — multi-source with working sources + India-aware domain matching.
Sources: Remotive (management/ops/all), RemoteOK (tag-based), Arbeitnow (global)
"""
from __future__ import annotations
import asyncio
import logging
import re
from typing import Any
import httpx

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://remotive.com",
}

# ── Domain detection ───────────────────────────────────────
DOMAIN_MAP = {
    "operations": ["operations", "ops", "fleet", "logistics", "last-mile", "supply chain",
                   "warehouse", "dispatch", "fulfillment", "procurement", "inventory",
                   "cluster", "city head", "hyperlocal", "quick commerce", "dark store",
                   "delivery", "rider", "onboarding", "sla", "tat"],
    "management": ["manager", "management", "team lead", "director", "head of",
                   "supervisor", "coordinator", "executive", "vp ", "coo", "cxo"],
    "sales":      ["sales", "business development", "bd ", "account executive", "revenue", "b2b"],
    "marketing":  ["marketing", "growth", "seo", "content", "brand", "digital marketing"],
    "data":       ["data analyst", "data science", "sql", "tableau", "analytics", "bi "],
    "software":   ["python", "javascript", "react", "node", "java", "backend", "frontend",
                   "software engineer", "developer", "fastapi"],
    "devops":     ["devops", "aws", "cloud", "kubernetes", "docker", "terraform"],
    "design":     ["ui/ux", "figma", "product design", "graphic design"],
    "finance":    ["finance", "accounting", "cfo", "financial analyst", "banking"],
    "hr":         ["hr", "human resources", "talent acquisition", "recruiter"],
    "product":    ["product manager", "product owner", "roadmap", "scrum"],
    "customer":   ["customer success", "customer support", "cx "],
}

# Remotive category mapping
REMOTIVE_CATEGORIES = {
    "operations": ["all-other", "management-finance"],
    "management": ["management-finance", "all-other"],
    "sales":      ["sales"],
    "marketing":  ["marketing"],
    "data":       ["data"],
    "software":   ["software-dev"],
    "devops":     ["devops-sysadmin"],
    "design":     ["design"],
    "finance":    ["management-finance"],
    "hr":         ["hr"],
    "product":    ["product"],
    "customer":   ["customer-support"],
}

# RemoteOK tag mapping
REMOTEOK_TAGS = {
    "operations": ["operations", "manager", "ops"],
    "management": ["manager", "operations", "executive"],
    "sales":      ["sales", "business-development"],
    "marketing":  ["marketing", "growth"],
    "data":       ["data", "analytics"],
    "software":   ["python", "javascript", "react"],
    "devops":     ["devops", "cloud", "aws"],
    "design":     ["design", "ux"],
    "finance":    ["finance"],
    "hr":         ["hr", "recruiting"],
    "product":    ["product-manager"],
    "customer":   ["customer-support"],
}

# Arbeitnow keyword hints
ARBEITNOW_KEYWORDS = {
    "operations": ["operations", "logistics", "fleet", "supply chain", "warehouse", "delivery"],
    "management": ["manager", "director", "head", "executive", "lead"],
    "sales":      ["sales", "business development", "account"],
    "marketing":  ["marketing", "growth", "brand"],
    "data":       ["data", "analytics", "analyst"],
    "software":   ["python", "javascript", "developer", "engineer"],
    "devops":     ["devops", "cloud", "infrastructure"],
    "design":     ["design", "ux", "ui"],
    "finance":    ["finance", "accounting"],
    "hr":         ["hr", "human resources", "talent"],
    "product":    ["product manager", "product owner"],
    "customer":   ["customer success", "support"],
}


def detect_domain(resume_text: str, skills: list[str], roles: list[str]) -> str:
    text = f"{resume_text} {' '.join(skills)} {' '.join(roles)}".lower()
    scores = {d: sum(1 for kw in kws if kw in text) for d, kws in DOMAIN_MAP.items()}
    top = max(scores, key=scores.get)
    return top if scores[top] > 0 else "operations"


async def fetch_remotive_multi(domain: str, keywords: list[str]) -> list[dict]:
    """Fetch from multiple Remotive categories for the domain."""
    results = []
    categories = REMOTIVE_CATEGORIES.get(domain, ["all-other", "management-finance"])
    kw_lower = [k.lower() for k in keywords]

    for cat in categories[:2]:
        try:
            async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
                resp = await client.get(
                    "https://remotive.com/api/remote-jobs",
                    params={"category": cat, "limit": 25},
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
            for j in (data.get("jobs") or []):
                text = f"{j.get('title','')} {j.get('tags','')} {j.get('description','')[:200]}".lower()
                score = sum(1 for kw in kw_lower if kw in text)
                results.append({
                    "id": f"rem-{j.get('id','')}",
                    "title": j.get("title", ""),
                    "company": j.get("company_name", ""),
                    "location": j.get("candidate_required_location", "Remote") or "Remote",
                    "url": j.get("url", ""),
                    "tags": [t.strip() for t in (j.get("tags") or "").split(",") if t.strip()][:4],
                    "salary": j.get("salary", ""),
                    "source": "Remotive",
                    "_score": score,
                })
        except Exception as exc:
            logger.warning("Remotive %s error: %s", cat, exc)
    return results


async def fetch_remoteok_tags(domain: str) -> list[dict]:
    """Fetch from RemoteOK using domain-specific tags."""
    results = []
    tags = REMOTEOK_TAGS.get(domain, ["operations", "manager"])
    for tag in tags[:2]:
        try:
            async with httpx.AsyncClient(timeout=8, headers=HEADERS) as client:
                resp = await client.get(f"https://remoteok.com/api?tag={tag}")
                if resp.status_code != 200:
                    continue
                for j in resp.json():
                    if not isinstance(j, dict) or not j.get("position"):
                        continue
                    results.append({
                        "id": f"rok-{j.get('id','')}",
                        "title": j.get("position", ""),
                        "company": j.get("company", ""),
                        "location": "Remote",
                        "url": j.get("url", ""),
                        "tags": (j.get("tags") or [])[:4],
                        "salary": j.get("salary", ""),
                        "source": "RemoteOK",
                        "_score": 1,
                    })
        except Exception:
            continue
    return results


async def fetch_arbeitnow(domain: str) -> list[dict]:
    """Fetch from Arbeitnow and filter by domain keywords."""
    results = []
    kw_lower = ARBEITNOW_KEYWORDS.get(domain, ["operations", "manager"])
    try:
        async with httpx.AsyncClient(timeout=8, headers=HEADERS) as client:
            resp = await client.get("https://www.arbeitnow.com/api/job-board-api?page=1")
            if resp.status_code != 200:
                return results
            data = resp.json()
        for j in (data.get("data") or []):
            text = f"{j.get('title','')} {' '.join(j.get('tags',[]))}".lower()
            score = sum(1 for kw in kw_lower if kw in text)
            if score > 0:
                results.append({
                    "id": f"arb-{j.get('slug','')}",
                    "title": j.get("title", ""),
                    "company": j.get("company_name", ""),
                    "location": j.get("location", "Remote") or "Remote",
                    "url": j.get("url", ""),
                    "tags": (j.get("tags") or [])[:4],
                    "salary": "",
                    "source": "Arbeitnow",
                    "_score": score,
                })
    except Exception as exc:
        logger.warning("Arbeitnow error: %s", exc)
    return results


async def find_matching_jobs(
    skills: list[str],
    roles: list[str],
    limit: int = 20,
    resume_text: str = "",
) -> list[dict]:
    domain = detect_domain(resume_text, skills, roles)
    keywords = list(dict.fromkeys(roles[:3] + skills[:5]))  # ordered dedupe
    if not keywords:
        keywords = ["operations", "manager"]
    logger.info("Job search: domain=%s keywords=%s", domain, keywords[:5])

    remotive, rok, arbeit = await asyncio.gather(
        fetch_remotive_multi(domain, keywords),
        fetch_remoteok_tags(domain),
        fetch_arbeitnow(domain),
    )

    all_jobs = remotive + rok + arbeit
    kw_lower = [k.lower() for k in keywords]

    # Re-score
    for j in all_jobs:
        text = f"{j['title']} {j['company']} {' '.join(j.get('tags',[]))}".lower()
        j["_score"] = j.get("_score", 0) + sum(1 for kw in kw_lower if kw in text)

    all_jobs.sort(key=lambda j: j.get("_score", 0), reverse=True)

    # Dedupe
    seen, unique = set(), []
    for j in all_jobs:
        key = f"{j['title'].lower()[:40]}_{j['company'].lower()[:20]}"
        if key not in seen and j.get("url") and j.get("title"):
            seen.add(key)
            j.pop("_score", None)
            unique.append(j)

    # If still empty, return top Remotive jobs regardless of score
    if not unique:
        for j in remotive[:limit]:
            j.pop("_score", None)
            unique.append(j)

    return unique[:limit]
