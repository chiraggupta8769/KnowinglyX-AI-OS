"""
Non-tech job scoring — algorithmic, zero LLM, microseconds per job.
6 factors: skills 40%, level 25%, industry 15%, seniority 10%, location 5%, salary 5%
Works for operations, logistics, sales, healthcare, any domain.
"""
from __future__ import annotations
import re

# ── Seniority ladder ───────────────────────────────────────
SENIORITY_LEVELS = {
    "intern": 0, "trainee": 0, "fresher": 0,
    "junior": 1, "associate": 1, "executive": 2,
    "manager": 3, "lead": 3, "team lead": 3,
    "senior": 3, "sr.": 3,
    "cluster manager": 3, "city manager": 3,
    "cluster head": 4, "city head": 4, "regional head": 4,
    "area manager": 3, "zonal manager": 4, "zone head": 4,
    "deputy manager": 3, "assistant manager": 3,
    "senior manager": 4, "sr. manager": 4,
    "director": 5, "head": 4, "vp": 5, "vice president": 5,
    "coo": 6, "chief operating": 6, "cxo": 6, "ceo": 6,
}

INDUSTRY_KEYWORDS = {
    "operations": ["operations", "ops", "fleet", "logistics", "last.mile", "supply chain",
                   "warehouse", "dark store", "quick commerce", "hyperlocal", "delivery",
                   "dispatch", "fulfilment", "fulfillment", "rider", "courier",
                   "ecommerce", "e-commerce", "d2c", "b2c"],
    "management": ["management", "team management", "people management", "leadership"],
    "sales": ["sales", "business development", "revenue", "crm", "b2b", "account"],
    "marketing": ["marketing", "growth", "digital", "brand", "content", "seo"],
    "data": ["data", "analytics", "sql", "bi", "tableau"],
    "software": ["software", "engineering", "backend", "frontend", "python", "java"],
    "hr": ["hr", "talent", "recruitment", "hiring", "people"],
    "finance": ["finance", "accounting", "audit", "p&l", "budget"],
    "customer": ["customer success", "cx", "support", "nps", "csat"],
}


def _seniority_score(candidate_level: str, job_title: str) -> float:
    """Score 0-1 based on seniority match."""
    candidate_l = candidate_level.lower()
    job_l = job_title.lower()

    cand_seniority = 0
    job_seniority = 0

    for kw, lvl in SENIORITY_LEVELS.items():
        if kw in candidate_l:
            cand_seniority = max(cand_seniority, lvl)
        if kw in job_l:
            job_seniority = max(job_seniority, lvl)

    if cand_seniority == 0 and job_seniority == 0:
        return 0.6  # neutral

    diff = abs(cand_seniority - job_seniority)
    if diff == 0: return 1.0
    if diff == 1: return 0.8
    if diff == 2: return 0.5
    return 0.2


def _skills_score(candidate_skills: list[str], job_text: str) -> float:
    """Score based on skill keyword overlap."""
    if not candidate_skills:
        return 0.5
    job_l = job_text.lower()
    matches = sum(1 for skill in candidate_skills if skill.lower() in job_l)
    ratio = matches / len(candidate_skills)
    # Boost for strong matches
    if ratio >= 0.5: return min(1.0, ratio + 0.15)
    return ratio


def _industry_score(candidate_domain: str, job_text: str) -> float:
    """Score based on industry/domain alignment."""
    keywords = INDUSTRY_KEYWORDS.get(candidate_domain, [])
    if not keywords:
        return 0.5
    job_l = job_text.lower()
    hits = sum(1 for kw in keywords if kw in job_l)
    if hits == 0: return 0.2
    if hits == 1: return 0.6
    if hits == 2: return 0.8
    return 1.0


def _location_score(candidate_location: str, job_location: str) -> float:
    """Score based on location match."""
    if not candidate_location or not job_location:
        return 0.5
    job_l = job_location.lower()
    cand_l = candidate_location.lower()
    if "remote" in job_l: return 0.9
    if any(city in job_l for city in cand_l.split()):
        return 1.0
    # India-wide match
    india_cities = ["india", "pan india", "pan-india", "anywhere in india"]
    if any(c in job_l for c in india_cities): return 0.85
    return 0.4


def _salary_score(candidate_salary_min: int, job_salary: str) -> float:
    """Score based on salary alignment (0 if data missing)."""
    if not job_salary or not candidate_salary_min:
        return 0.5  # neutral when data absent
    # Extract numbers from salary string
    numbers = re.findall(r'\d+', job_salary.replace(",", ""))
    if not numbers:
        return 0.5
    job_min = int(numbers[0])
    if job_min >= candidate_salary_min:
        return 1.0
    if job_min >= candidate_salary_min * 0.8:
        return 0.7
    return 0.3


def score_job(
    job: dict,
    candidate_skills: list[str],
    candidate_domain: str,
    candidate_title: str = "",
    candidate_location: str = "",
    candidate_salary_min: int = 0,
) -> int:
    """
    Return 0-100 fit score for a job.
    Weights: skills 40%, level 25%, industry 15%, seniority 10%, location 5%, salary 5%
    """
    job_text = f"{job.get('title','')} {' '.join(job.get('tags',[]))} {job.get('description','')}"

    skills_s   = _skills_score(candidate_skills, job_text)
    level_s    = _seniority_score(candidate_title, job.get('title', ''))
    industry_s = _industry_score(candidate_domain, job_text)
    seniority_s = level_s  # same signal, different weight split
    location_s = _location_score(candidate_location, job.get('location', ''))
    salary_s   = _salary_score(candidate_salary_min, job.get('salary', ''))

    weighted = (
        skills_s   * 0.40 +
        level_s    * 0.25 +
        industry_s * 0.15 +
        seniority_s * 0.10 +
        location_s * 0.05 +
        salary_s   * 0.05
    )
    return min(99, max(10, round(weighted * 100)))
