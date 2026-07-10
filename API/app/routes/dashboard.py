"""
Dashboard endpoint — returns a personalized career summary:
- Job match stats
- Recent matched jobs with fit scores
- Career gaps
- Recommended next actions
"""
from __future__ import annotations
import json
import logging
import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.job_discovery_service import find_matching_jobs
from app.services.ollama_service import ollama_service, OllamaError
from app.utils.json_tools import parse_llm_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class DashboardRequest(BaseModel):
    resume_text: str
    skills: list[str] = []
    roles: list[str] = []


@router.post("/feed")
async def get_dashboard_feed(body: DashboardRequest):
    """Return personalized job feed with fit scores + career insights."""
    if not body.resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text is required")

    # Fetch jobs and career insights in parallel
    jobs_task = find_matching_jobs(
        skills=body.skills,
        roles=body.roles,
        limit=15,
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

    # Score each job with a quick fit assessment
    scored_jobs = []
    for j in jobs[:10]:
        # Fast heuristic score: keyword overlap between resume and job title/tags
        resume_lower = body.resume_text.lower()
        job_text = f"{j['title']} {' '.join(j.get('tags', []))}".lower()
        words = [w for w in job_text.split() if len(w) > 3]
        matches = sum(1 for w in words if w in resume_lower)
        fit = min(95, 50 + (matches * 8))
        scored_jobs.append({**j, "fit_score": fit})

    scored_jobs.sort(key=lambda j: j["fit_score"], reverse=True)

    return {
        "success": True,
        "insight": insight,
        "jobs": scored_jobs,
        "total_jobs": len(jobs),
    }
