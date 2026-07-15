"""
Job discovery — 5 sources, domain-aware, India-aware.
Sources: Remotive (search), Jobicy (free API), RemoteOK (tags), Arbeitnow, Remotive (category)
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
                   "delivery", "rider", "sla", "tat", "blinkit", "shadowfax", "zomato"],
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

# Jobicy tag mapping per domain
JOBICY_TAGS = {
    "operations":  ["operations", "management", "logistics"],
    "management":  ["management", "operations"],
    "sales":       ["sales", "business-development"],
    "marketing":   ["marketing", "growth"],
    "data":        ["data-analysis", "analytics"],
    "software":    ["python", "javascript", "backend"],
    "devops":      ["devops", "cloud"],
    "design":      ["design", "ux"],
    "finance":     ["finance"],
    "hr":          ["hr", "recruiting"],
    "product":     ["product-management"],
    "customer":    ["customer-support"],
}

# RemoteOK tags per domain
REMOTEOK_TAGS = {
    "operations": ["operations", "manager"],
    "management": ["manager", "executive"],
    "sales":      ["sales", "business-development"],
    "marketing":  ["marketing", "growth"],
    "data":       ["data", "analytics"],
    "software":   ["python", "javascript"],
    "devops":     ["devops", "cloud"],
    "design":     ["design"],
    "finance":    ["finance"],
    "hr":         ["hr"],
    "product":    ["product-manager"],
    "customer":   ["customer-support"],
}


def detect_domain(resume_text: str, skills: list[str], roles: list[str]) -> str:
    text = f"{resume_text} {' '.join(skills)} {' '.join(roles)}".lower()
    scores = {d: sum(1 for kw in kws if kw in text) for d, kws in DOMAIN_MAP.items()}
    top = max(scores, key=scores.get)
    return top if scores[top] > 0 else "operations"


def build_search_queries(domain: str, skills: list[str], roles: list[str]) -> list[str]:
    """Build human-readable search queries for this profile."""
    queries = list(dict.fromkeys(roles[:3] + skills[:3]))
    domain_defaults = {
        "operations": ["operations manager", "city operations", "logistics manager"],
        "management": ["team manager", "operations manager"],
        "sales": ["sales manager", "business development"],
        "marketing": ["marketing manager", "growth manager"],
        "data": ["data analyst", "business analyst"],
        "software": ["software engineer", "backend developer"],
        "devops": ["devops engineer", "cloud engineer"],
        "design": ["ux designer", "product designer"],
        "finance": ["finance manager", "financial analyst"],
        "hr": ["hr manager", "talent acquisition"],
        "product": ["product manager"],
        "customer": ["customer success manager"],
    }
    if not queries:
        queries = domain_defaults.get(domain, ["operations manager"])
    return queries[:4]


# ── Source fetchers ────────────────────────────────────────

async def fetch_remotive_search(queries: list[str]) -> list[dict]:
    """Remotive with search param — returns keyword-matched jobs across all categories."""
    results = []
    for q in queries[:2]:
        try:
            async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
                resp = await client.get(
                    "https://remotive.com/api/remote-jobs",
                    params={"search": q, "limit": 15},
                )
                if resp.status_code != 200:
                    continue
                for j in (resp.json().get("jobs") or []):
                    results.append({
                        "id": f"rem-s-{j.get('id','')}",
                        "title": j.get("title", ""),
                        "company": j.get("company_name", ""),
                        "location": j.get("candidate_required_location", "Remote") or "Remote",
                        "url": j.get("url", ""),
                        "tags": [t.strip() for t in (j.get("tags") or "").split(",") if t.strip()][:4],
                        "salary": j.get("salary", ""),
                        "source": "Remotive",
                        "_score": 2,
                    })
        except Exception as exc:
            logger.debug("Remotive search %s: %s", q, exc)
    return results


async def fetch_jobicy(domain: str) -> list[dict]:
    """Jobicy free API — good ops/management/sales coverage."""
    results = []
    tags = JOBICY_TAGS.get(domain, ["operations"])
    for tag in tags[:2]:
        try:
            async with httpx.AsyncClient(timeout=8, headers=HEADERS) as client:
                resp = await client.get(
                    "https://jobicy.com/api/v2/remote-jobs",
                    params={"count": 15, "tag": tag},
                )
                if resp.status_code != 200:
                    continue
                for j in (resp.json().get("jobs") or []):
                    results.append({
                        "id": f"jcy-{j.get('id','')}",
                        "title": j.get("jobTitle", ""),
                        "company": j.get("companyName", ""),
                        "location": j.get("jobGeo", "Remote") or "Remote",
                        "url": j.get("url", ""),
                        "tags": (j.get("jobType") or "").split(",")[:3],
                        "salary": j.get("annualSalaryMin", ""),
                        "source": "Jobicy",
                        "_score": 1,
                    })
        except Exception as exc:
            logger.debug("Jobicy %s: %s", tag, exc)
    return results


async def fetch_remotive_category(domain: str, keywords: list[str]) -> list[dict]:
    """Remotive by category — broader net."""
    results = []
    categories = REMOTIVE_CATEGORIES.get(domain, ["all-other"])[:2]
    kw_lower = [k.lower() for k in keywords]
    for cat in categories:
        try:
            async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
                resp = await client.get(
                    "https://remotive.com/api/remote-jobs",
                    params={"category": cat, "limit": 20},
                )
                if resp.status_code != 200:
                    continue
                for j in (resp.json().get("jobs") or []):
                    text = f"{j.get('title','')} {j.get('tags','')}".lower()
                    score = sum(1 for kw in kw_lower if kw in text)
                    results.append({
                        "id": f"rem-c-{j.get('id','')}",
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
            logger.debug("Remotive cat %s: %s", cat, exc)
    return results


async def fetch_remoteok(domain: str) -> list[dict]:
    """RemoteOK tag search."""
    results = []
    for tag in REMOTEOK_TAGS.get(domain, ["operations"])[:2]:
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


async def fetch_adzuna(domain: str, queries: list[str], app_id: str, app_key: str) -> list[dict]:
    """Adzuna India — free tier 2500/month. Activates when credentials are set."""
    results = []
    if not app_id or not app_key:
        return results

    domain_category_map = {
        "operations": "logistics-warehouse",
        "management": "admin-clerical",
        "sales": "sales",
        "marketing": "marketing",
        "data": "it-jobs",
        "software": "it-jobs",
        "hr": "hr-jobs",
        "finance": "accounting-finance-jobs",
        "customer": "customer-services",
    }
    category = domain_category_map.get(domain, "admin-clerical")

    for q in queries[:2]:
        try:
            async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
                resp = await client.get(
                    f"https://api.adzuna.com/v1/api/jobs/in/search/1",
                    params={
                        "app_id": app_id,
                        "app_key": app_key,
                        "what": q,
                        "where": "India",
                        "category": category,
                        "results_per_page": 15,
                        "content-type": "application/json",
                    },
                )
                if resp.status_code != 200:
                    logger.warning("Adzuna %s: HTTP %s", q, resp.status_code)
                    continue
                for j in (resp.json().get("results") or []):
                    salary = ""
                    if j.get("salary_min"):
                        salary = f"₹{j['salary_min']:,.0f}–₹{j.get('salary_max',j['salary_min']):,.0f}"
                    results.append({
                        "id": f"adz-{j.get('id','')}",
                        "title": j.get("title", ""),
                        "company": (j.get("company") or {}).get("display_name", ""),
                        "location": (j.get("location") or {}).get("display_name", "India"),
                        "url": j.get("redirect_url", ""),
                        "tags": [category],
                        "salary": salary,
                        "source": "Adzuna India",
                        "_score": 3,  # Highest priority — India-specific
                    })
        except Exception as exc:
            logger.warning("Adzuna %s: %s", q, exc)
    return results



    """Arbeitnow — global, good EU/international coverage."""
    results = []
    kw_lower = [k.lower() for k in keywords]
    try:
        async with httpx.AsyncClient(timeout=8, headers=HEADERS) as client:
            resp = await client.get("https://www.arbeitnow.com/api/job-board-api?page=1")
            if resp.status_code != 200:
                return results
            for j in (resp.json().get("data") or []):
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
        logger.warning("Arbeitnow: %s", exc)
    return results


# ── Main entry ─────────────────────────────────────────────

async def find_matching_jobs(
    skills: list[str],
    roles: list[str],
    limit: int = 20,
    resume_text: str = "",
) -> list[dict]:
    """5-source parallel fetch with domain-aware scoring."""
    domain = detect_domain(resume_text, skills, roles)
    queries = build_search_queries(domain, skills, roles)
    keywords = list(dict.fromkeys(roles[:3] + skills[:5]))
    if not keywords:
        keywords = ["operations", "manager"]

    logger.info("Job search: domain=%s queries=%s", domain, queries[:3])

    import os
    adzuna_id  = os.environ.get("ADZUNA_APP_ID", "")
    adzuna_key = os.environ.get("ADZUNA_APP_KEY", "")

    # 5+1 sources in parallel (Adzuna only fires when credentials are set)
    rem_search, jobicy, rem_cat, rok, arbeit, adzuna = await asyncio.gather(
        fetch_remotive_search(queries),
        fetch_jobicy(domain),
        fetch_remotive_category(domain, keywords),
        fetch_remoteok(domain),
        fetch_arbeitnow(domain, keywords),
        fetch_adzuna(domain, queries, adzuna_id, adzuna_key),
    )

    # Adzuna (India-specific) gets highest priority in the mix
    all_jobs = adzuna + rem_search + jobicy + rem_cat + rok + arbeit

    # Re-score by keyword overlap
    kw_lower = [k.lower() for k in keywords]
    for j in all_jobs:
        text = f"{j['title']} {j['company']} {' '.join(j.get('tags',[]))}".lower()
        j["_score"] = j.get("_score", 0) + sum(1 for kw in kw_lower if kw in text)

    all_jobs.sort(key=lambda j: j.get("_score", 0), reverse=True)

    # Dedupe by title+company
    seen, unique = set(), []
    for j in all_jobs:
        key = f"{j['title'].lower()[:40]}_{j['company'].lower()[:20]}"
        if key not in seen and j.get("url") and j.get("title"):
            seen.add(key)
            j.pop("_score", None)
            unique.append(j)

    # Fallback: if < 5 results, return top from search anyway
    if len(unique) < 5:
        for j in (rem_search + jobicy):
            key = f"{j['title'].lower()[:40]}_{j['company'].lower()[:20]}"
            if key not in seen and j.get("url"):
                seen.add(key)
                j.pop("_score", None)
                unique.append(j)
            if len(unique) >= limit:
                break

    return unique[:limit]
