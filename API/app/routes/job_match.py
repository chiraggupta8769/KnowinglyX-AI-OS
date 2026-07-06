"""
Job matching + Apply Kit route.
- POST /jobs/match — find matching jobs for a resume
- POST /jobs/apply-kit — generate cover letter + resume summary for a specific job
"""
from __future__ import annotations

import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.job_discovery_service import find_matching_jobs
from app.services.ollama_service import ollama_service, OllamaError
from app.utils.json_tools import parse_llm_json

router = APIRouter(prefix="/jobs", tags=["Job Matching"])


class JobMatchRequest(BaseModel):
    resume_text: str
    target_roles: list[str] = []
    skills: list[str] = []
    limit: int = 15


class ApplyKitRequest(BaseModel):
    resume_text: str
    job_title: str
    company: str
    job_description: str = ""


@router.post("/match")
async def match_jobs(body: JobMatchRequest):
    """Find real matching jobs based on resume skills and target roles."""
    if not body.resume_text.strip() and not body.target_roles and not body.skills:
        raise HTTPException(status_code=400, detail="Provide resume_text or target_roles/skills")

    # Extract skills/roles from resume if not provided
    skills = body.skills
    roles = body.target_roles

    if body.resume_text and (not skills or not roles):
        prompt = f"""Extract from this resume the top skills and target job roles.
Return ONLY valid JSON. No markdown.
{{"skills": ["skill1", "skill2"], "roles": ["role1", "role2"]}}
Resume: {body.resume_text[:2000]}"""
        try:
            raw = await ollama_service.chat(prompt=prompt, model="llama-3.1-8b-instant")
            extracted = parse_llm_json(raw)
            skills = skills or extracted.get("skills", [])
            roles = roles or extracted.get("roles", [])
        except Exception:
            # Fall back to basic extraction
            pass

    jobs = await find_matching_jobs(
        skills=skills[:6],
        roles=roles[:4],
        limit=body.limit,
    )

    return {
        "success": True,
        "count": len(jobs),
        "skills_used": skills[:6],
        "roles_used": roles[:4],
        "jobs": jobs,
    }


@router.post("/apply-kit")
async def apply_kit(body: ApplyKitRequest):
    """Generate a tailored cover letter and application email for a specific job."""
    if not body.resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text is required")

    jd_context = f"\nJob Description:\n{body.job_description}" if body.job_description else ""

    prompt = f"""You are an expert career coach.

Generate a complete apply kit for this candidate applying to {body.job_title} at {body.company}.{jd_context}

Return ONLY valid JSON. No markdown.

{{
  "cover_letter": "Full professional cover letter ready to send",
  "email_subject": "Email subject line for the application",
  "email_body": "Short professional email to send with the application",
  "key_talking_points": ["3-4 points to emphasize in interview"],
  "tailoring_notes": "What was customized for this specific role"
}}

Resume:
{body.resume_text}"""

    try:
        raw = await ollama_service.chat(prompt=prompt, model="qwen3:8b")
    except OllamaError as exc:
        status = 503 if exc.permanent else 504
        raise HTTPException(status_code=status, detail=str(exc))

    try:
        result = parse_llm_json(raw)
    except Exception:
        return {"success": False, "error": "Model returned invalid JSON", "raw": raw}

    return {"success": True, "job_title": body.job_title, "company": body.company, "data": result}
