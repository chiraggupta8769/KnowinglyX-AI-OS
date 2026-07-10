"""
LinkedIn outreach + salary intelligence routes.
"""
from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.ollama_service import ollama_service, OllamaError
from app.utils.json_tools import parse_llm_json

router = APIRouter(prefix="/tools", tags=["Career Tools"])


class OutreachRequest(BaseModel):
    resume_text: str
    job_title: str = ""
    company: str = ""
    recruiter_name: str = ""
    context: str = "cold_outreach"  # cold_outreach | referral_ask | follow_up


class SalaryRequest(BaseModel):
    resume_text: str
    target_role: str = ""
    location: str = ""


@router.post("/linkedin-outreach")
async def linkedin_outreach(body: OutreachRequest):
    """Generate 3 variants of LinkedIn outreach messages."""
    if not body.resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text is required")

    name_line = f"Recruiter name: {body.recruiter_name}" if body.recruiter_name else "No recruiter name provided — use generic opener"
    role_line = f"Target role: {body.job_title} at {body.company}" if body.job_title else "General job search outreach"

    prompt = f"""You are an expert LinkedIn outreach coach.

Generate 3 LinkedIn message variants for this candidate. Context: {body.context}.
{name_line}
{role_line}

Return ONLY valid JSON. No markdown.
{{
  "messages": [
    {{
      "label": "Direct & Confident",
      "length": "short",
      "message": "The full message text"
    }},
    {{
      "label": "Value-Led",
      "length": "medium",
      "message": "The full message text"
    }},
    {{
      "label": "Story-Based",
      "length": "medium",
      "message": "The full message text"
    }}
  ],
  "tips": ["tip1", "tip2", "tip3"]
}}

Rules:
- Each message under 300 characters (LinkedIn limit for connection requests)
- No generic openers like "Hope this finds you well"
- Lead with value or a specific hook
- Natural, human tone — not corporate speak

Candidate resume:
{body.resume_text[:1500]}"""

    try:
        raw = await ollama_service.chat(prompt=prompt, model="llama-3.1-8b-instant")
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        result = parse_llm_json(raw)
    except json.JSONDecodeError:
        return {"success": False, "error": "Model returned invalid JSON", "raw": raw}

    return {"success": True, "data": result}


@router.post("/salary-intel")
async def salary_intel(body: SalaryRequest):
    """Return salary intelligence for the candidate's profile."""
    if not body.resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text is required")

    location_hint = f"Location: {body.location}" if body.location else "Location: India (provide INR and USD)"
    role_hint = f"Target role: {body.target_role}" if body.target_role else "Infer the best-fit role from the resume"

    prompt = f"""You are a compensation expert with deep knowledge of job market salaries.

Analyze this candidate's resume and provide salary intelligence.
{location_hint}
{role_hint}

Return ONLY valid JSON. No markdown.
{{
  "current_market_value": "What they can earn right now",
  "salary_range_inr": "e.g. ₹8L – ₹14L per year",
  "salary_range_usd": "e.g. $18,000 – $32,000 per year",
  "target_role": "Best-fit role title for this profile",
  "experience_band": "Junior | Mid | Senior | Lead | Executive",
  "negotiation_floor": "Minimum they should accept",
  "negotiation_target": "What to aim for in negotiation",
  "negotiation_ceiling": "Stretch target if company is well-funded",
  "top_paying_sectors": ["sector1", "sector2", "sector3"],
  "negotiation_tips": ["tip1", "tip2", "tip3"],
  "skills_that_increase_pay": ["skill1", "skill2", "skill3"]
}}

Resume:
{body.resume_text[:1500]}"""

    try:
        raw = await ollama_service.chat(prompt=prompt, model="llama-3.1-8b-instant")
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        result = parse_llm_json(raw)
    except json.JSONDecodeError:
        return {"success": False, "error": "Model returned invalid JSON", "raw": raw}

    return {"success": True, "data": result}
