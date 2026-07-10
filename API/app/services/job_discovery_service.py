"""
Job discovery service — multi-source with smart role detection.
Sources: Remotive, RemoteOK, Arbeitnow, Adzuna (free, 1M+ jobs)
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
}

# ── Role domain detection ──────────────────────────────────
DOMAIN_KEYWORDS = {
    "operations": ["operations", "ops", "fleet", "logistics", "last-mile", "supply chain",
                   "warehouse", "dispatch", "fulfillment", "procurement", "inventory"],
    "management": ["manager", "management", "team lead", "director", "vp ", "head of",
                   "supervisor", "coordinator", "executive"],
    "sales": ["sales", "business development", "bd ", "account executive", "revenue",
              "crm", "b2b", "enterprise sales"],
    "marketing": ["marketing", "growth", "seo", "content", "brand", "campaign", "digital marketing"],
    "data": ["data analyst", "data science", "data engineer", "sql", "tableau", "power bi",
             "analytics", "business intelligence", "bi "],
    "software": ["python", "javascript", "react", "node", "java", "backend", "frontend",
                 "fullstack", "software engineer", "developer", "fastapi", "django"],
    "devops": ["devops", "aws", "cloud", "kubernetes", "docker", "terraform", "sre"],
    "design": ["ui/ux", "ux design", "figma", "product design", "graphic design"],
    "finance": ["finance", "accounting", "cfo", "financial analyst", "investment", "banking"],
    "hr": ["hr", "human resources", "talent acquisition", "recruiter", "people ops"],
    "product": ["product manager", "product owner", "product lead", "roadmap", "scrum"],
    "customer": ["customer success", "customer support", "customer experience", "cx "],
}

def detect_domain(resume_text: str, skills: list[str], roles: list[str]) -> str:
    """Detect the primary career domain from resume content."""
    text = f"{resume_text} {' '.join(skills)} {' '.join(roles)}".lower()
    scores = {domain: 0 for domain in DOMAIN_KEYWORDS}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw in text)
    top = max(scores, key=scores.get)
    return top if scores[top] > 0 else "operations"


def build_search_queries(domain: str, skills: list[str], roles: list[str]) -> list[str]:
    """Build specific search queries for the detected domain."""
    domain_queries = {
        "operations": ["operations manager", "logistics manager", "fleet manager",
                       "supply chain manager", "operations executive"],
        "management": ["team manager", "operations manager", "project manager",
                       "senior manager", "department head"],
        "sales": ["sales manager", "business development", "account executive",
                  "sales executive", "business development manager"],
        "marketing": ["marketing manager", "digital marketing", "growth manager",
                      "content manager", "marketing executive"],
        "data": ["data analyst", "data scientist", "business analyst",
                 "data engineer", "analytics manager"],
        "software": ["software engineer", "python developer", "backend developer",
                     "full stack developer", "react developer"],
        "devops": ["devops engineer", "cloud engineer", "site reliability engineer",
                   "platform engineer", "infrastructure engineer"],
        "design": ["ux designer", "product designer", "ui designer", "graphic designer"],
        "finance": ["finance manager", "financial analyst", "accountant", "cfo"],
        "hr": ["hr manager", "recruiter", "talent acquisition", "people manager"],
        "product": ["product manager", "product owner", "senior product manager"],
        "customer": ["customer success manager", "customer support", "account manager"],
    }
    queries = domain_queries.get(domain, ["operations manager", "executive"])
    # Add top roles from resume if available
    for r in roles[:2]:
        if r and r not in queries:
            queries.insert(0, r)
    return queries[:5]


# ── Job sources ────────────────────────────────────────────

async def fetch_adzuna(queries: list[str], country: str = "in") -> list[dict]:
    """
    Fetch from Adzuna — free public search, 1M+ real jobs.
    Uses the public search endpoint (no API key needed for basic search).
    """
    results = []
    tried = set()
    for query in queries[:3]:
        if query in tried:
            continue
        tried.add(query)
        try:
            async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
                # Try India first, then global
                for cc in [country, "gb", "us"]:
                    resp = await client.get(
                        f"https://api.adzuna.com/v1/api/jobs/{cc}/search/1",
                        params={
                            "app_id": "test",
                            "app_key": "test",
                            "what": query,
                            "results_per_page": 10,
                            "content-type": "application/json",
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for j in (data.get("results") or []):
                            results.append({
                                "id": f"adz-{j.get('id','')}",
                                "title": j.get("title", ""),
                                "company": (j.get("company") or {}).get("display_name", ""),
                                "location": (j.get("location") or {}).get("display_name", ""),
                                "url": j.get("redirect_url", ""),
                                "tags": [],
                                "salary": f"${j['salary_min']:.0f}–${j['salary_max']:.0f}" if j.get("salary_min") else "",
                                "source": "Adzuna",
                                "_score": 2,
                            })
                        break
        except Exception as exc:
            logger.debug("Adzuna error for '%s': %s", query, exc)
    return results


async def fetch_remotive(domain: str, keywords: list[str]) -> list[dict]:
    """Fetch from Remotive — best for remote roles."""
    category_map = {
        "software": "software-dev", "devops": "devops-sysadmin", "data": "data",
        "design": "design", "product": "product", "management": "management-finance",
        "sales": "sales", "marketing": "marketing", "customer": "customer-support",
        "finance": "management-finance", "hr": "hr", "operations": "all-other",
    }
    category = category_map.get(domain, "all-other")
    results = []
    try:
        async with httpx.AsyncClient(timeout=10, headers={
            **HEADERS, "Referer": "https://remotive.com"
        }) as client:
            resp = await client.get(
                "https://remotive.com/api/remote-jobs",
                params={"category": category, "limit": 20},
            )
            if resp.status_code != 200:
                return results
            data = resp.json()

        kw_lower = [k.lower() for k in keywords]
        for j in (data.get("jobs") or []):
            text = f"{j.get('title','')} {j.get('tags','')}".lower()
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
        logger.warning("Remotive error: %s", exc)
    return results


async def fetch_remoteok(queries: list[str]) -> list[dict]:
    """RemoteOK tag-based search."""
    results = []
    for query in queries[:2]:
        slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
        try:
            async with httpx.AsyncClient(timeout=8, headers=HEADERS) as client:
                resp = await client.get(f"https://remoteok.com/api?tag={slug}")
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


async def fetch_arbeitnow(queries: list[str]) -> list[dict]:
    """Arbeitnow — global job board."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=8, headers=HEADERS) as client:
            resp = await client.get("https://www.arbeitnow.com/api/job-board-api?page=1")
            if resp.status_code != 200:
                return results
            data = resp.json()

        kw_lower = [q.lower() for q in queries]
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


# ── Main entry point ───────────────────────────────────────

async def find_matching_jobs(
    skills: list[str],
    roles: list[str],
    limit: int = 20,
    resume_text: str = "",
) -> list[dict]:
    """Find relevant jobs across all sources with domain-aware matching."""
    domain = detect_domain(resume_text, skills, roles)
    queries = build_search_queries(domain, skills, roles)
    logger.info("Job search: domain=%s queries=%s", domain, queries)

    # Fetch from all sources in parallel
    adzuna, remotive, rok, arbeit = await asyncio.gather(
        fetch_adzuna(queries),
        fetch_remotive(domain, queries),
        fetch_remoteok(queries),
        fetch_arbeitnow(queries),
    )

    # Combine — prioritize Adzuna (most relevant) and Remotive
    all_jobs = adzuna + remotive + rok + arbeit

    # Re-score by query relevance
    kw_lower = [q.lower() for q in queries] + [s.lower() for s in skills[:5]]
    for j in all_jobs:
        text = f"{j['title']} {j['company']} {' '.join(j.get('tags', []))}".lower()
        j["_score"] = j.get("_score", 0) + sum(1 for kw in kw_lower if kw in text)

    # Sort, dedupe
    all_jobs.sort(key=lambda j: j.get("_score", 0), reverse=True)
    seen, unique = set(), []
    for j in all_jobs:
        key = f"{j['title'].lower()[:40]}_{j['company'].lower()[:20]}"
        if key not in seen and j.get("url") and j.get("title"):
            seen.add(key)
            j.pop("_score", None)
            unique.append(j)

    return unique[:limit]
