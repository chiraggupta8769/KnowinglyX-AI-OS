"""
Dashboard endpoint — personalized career feed with algorithmic scoring + ghost detection.
"""
from __future__ import annotations
import json
import logging
import asyncio
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.job_discovery_service import find_matching_jobs, detect_domain
from app.services.ollama_service import ollama_service, OllamaError
from app.utils.json_tools import parse_llm_json
from app.utils.job_scorer import score_job
from app.utils.ghost_detector import ghost_score

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class DashboardRequest(BaseModel):
    resume_text: str
    skills: list[str] = []
    roles: list[str] = []


def _extract_location(resume_text: str) -> str:
    """Quick heuristic to pull city from resume text."""
    cities = ["jaipur", "delhi", "mumbai", "bangalore", "bengaluru", "hyderabad",
              "pune", "chennai", "gurgaon", "gurugram", "noida", "kolkata",
              "ahmedabad", "chandigarh", "lucknow", "indore", "bhopal"]
    text_l = resume_text.lower()
    for city in cities:
        if city in text_l:
            return city.title()
    return ""


def _extract_title(resume_text: str, roles: list[str]) -> str:
    if roles:
        return roles[0]
    # Try to extract from first few lines
    for line in resume_text.split("\n")[:10]:
        line = line.strip()
        if 5 < len(line) < 60 and not "@" in line and not re.match(r"[\d+]", line):
            if any(kw in line.lower() for kw in ["manager", "head", "lead", "executive", "engineer", "analyst"]):
                return line
    return ""


@router.post("/feed")
async def get_dashboard_feed(body: DashboardRequest):
    """Return personalized job feed with algorithmic fit scores + ghost badges."""
    if not body.resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text is required")

    domain = detect_domain(body.resume_text, body.skills, body.roles)
    location = _extract_location(body.resume_text)
    title = _extract_title(body.resume_text, body.roles)

    # Fetch jobs and career insights in parallel
    jobs_task = find_matching_jobs(
        skills=body.skills,
        roles=body.roles,
        limit=20,
        resume_text=body.resume_text,
    )

    insight_prompt = f"""Analyze this resume and return a career intelligence summary.
Return ONLY valid JSON. No markdown.
{{
  "headline": "One sentence describing this candidate's strongest positioning",
  "top_strength": "Their #1 marketable skill right now",
  "biggest_gap": "The one thing holding them back",
  "salary_range": "Estimated market salary range for their profile",
  "market_demand": "high | medium | low",
  "next_action": "The single most impactful career move they should make this week",
  "target_roles": ["role1", "role2", "role3"]
}}
Resume: {body.resume_text[:2000]}"""

    try:
        jobs, insight_raw = await asyncio.gather(
            jobs_task,
            ollama_service.chat(prompt=insight_prompt, model="llama-3.1-8b-instant"),
        )
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        insight = parse_llm_json(insight_raw)
    except Exception:
        insight = {}

    # Score each job algorithmically + ghost detection
    scored_jobs = []
    for j in jobs:
        fit = score_job(
            job=j,
            candidate_skills=body.skills,
            candidate_domain=domain,
            candidate_title=title,
            candidate_location=location,
        )
        ghost = ghost_score(j)
        scored_jobs.append({**j, "fit_score": fit, "ghost": ghost})

    scored_jobs.sort(key=lambda j: j["fit_score"], reverse=True)

    return {
        "success": True,
        "insight": insight,
        "jobs": scored_jobs,
        "total_jobs": len(jobs),
        "domain": domain,
    }
