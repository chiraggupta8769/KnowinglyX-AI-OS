"""
Career Path Simulator — answers "where can I go from here?"
Shows 3 realistic career trajectories from the user's current profile.
"""
from app.services.ollama_service import ollama_service, OllamaError
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
from app.utils.json_tools import parse_llm_json

router = APIRouter(prefix="/career-path", tags=["Career Path"])


class PathRequest(BaseModel):
    resume_text: str
    ambition: str = "balanced"  # conservative | balanced | ambitious


@router.post("/simulate")
async def simulate_career_paths(body: PathRequest):
    if not body.resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text is required")

    prompt = f"""You are an expert career strategist with deep knowledge of Indian job markets.

Analyze this resume and generate 3 distinct career paths the person can realistically pursue.
Ambition level: {body.ambition}

Return ONLY valid JSON. No markdown. No explanation.

{{
  "current_role": "Their current/most recent role title",
  "current_level": "Their current seniority level",
  "paths": [
    {{
      "path_name": "Short label e.g. 'Operations Leader' or 'Startup COO' or 'Tech-Ops Hybrid'",
      "type": "vertical | pivot | entrepreneurial",
      "tagline": "One exciting sentence describing this path",
      "next_role": {{
        "title": "Most logical next role title",
        "timeline": "e.g. 6-12 months",
        "salary_jump": "e.g. +20-35% hike",
        "skills_to_add": ["skill1", "skill2"],
        "how_to_get_there": "2-3 concrete steps"
      }},
      "milestone_role": {{
        "title": "Role in 2-3 years",
        "timeline": "2-3 years",
        "salary_range": "e.g. ₹25-40L",
        "skills_to_add": ["skill1", "skill2"]
      }},
      "peak_role": {{
        "title": "Where this path leads in 5+ years",
        "timeline": "5+ years",
        "salary_range": "e.g. ₹50-80L",
        "impact": "What impact they'd have at this level"
      }},
      "companies_hiring": ["company type 1", "company type 2"],
      "difficulty": "Easy | Medium | Hard",
      "differentiation": "Why this path beats staying put"
    }}
  ],
  "skills_that_open_most_doors": ["skill1", "skill2", "skill3"],
  "one_move_this_week": "The single highest-leverage action to take right now"
}}

Resume:
{body.resume_text[:2500]}"""

    try:
        raw = await ollama_service.chat(prompt=prompt, model="qwen3:8b")
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        result = parse_llm_json(raw)
    except json.JSONDecodeError:
        return {"success": False, "error": "Model returned invalid JSON", "raw": raw[:300]}

    return {"success": True, "data": result}
