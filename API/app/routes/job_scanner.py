import re
import json
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.ollama_service import ollama_service, OllamaError
from app.utils.json_tools import parse_llm_json

router = APIRouter(prefix="/job", tags=["Job Scanner"])


class JobScanRequest(BaseModel):
    job_url: str
    resume_text: str


async def fetch_job_text(url: str) -> str:
    """Fetch job posting text from a URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        text = resp.text

    # Strip HTML tags, collapse whitespace
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    # Cap at 4000 chars to fit in context
    return clean[:4000]


@router.post("/scan")
async def scan_job_url(body: JobScanRequest):
    """Fetch a job URL and score the resume against it."""
    if not body.resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text is required")

    try:
        job_text = await fetch_job_text(body.job_url)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not fetch job URL: {exc}")

    prompt = f"""You are an expert recruiter and ATS system.

Analyze how well this resume matches the job posting.

Return ONLY valid JSON. Do NOT wrap in markdown.

Schema:
{{
  "job_title": "Detected job title",
  "company": "Detected company name",
  "fit_score": 0,
  "recruiter_verdict": "hire | maybe | pass",
  "6_second_view": "What a recruiter notices in 6 seconds — top strength and biggest concern",
  "matched_keywords": [],
  "missing_keywords": [],
  "top_strengths": [],
  "critical_gaps": [],
  "recommended_action": "One concrete next step to improve this application"
}}

fit_score is 0-100. recruiter_verdict: hire=75+, maybe=50-74, pass=below 50.

RESUME:
{body.resume_text}

JOB POSTING:
{job_text}"""

    try:
        raw = await ollama_service.chat(prompt=prompt, model="qwen3:8b")
    except OllamaError as exc:
        status = 503 if exc.permanent else 504
        raise HTTPException(status_code=status, detail=str(exc))

    try:
        result = parse_llm_json(raw)
    except json.JSONDecodeError:
        return {"success": False, "error": "Model returned invalid JSON", "raw": raw}

    return {"success": True, "url": body.job_url, "data": result}
