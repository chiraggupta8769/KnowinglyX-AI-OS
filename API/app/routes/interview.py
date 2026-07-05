import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.interview_prep_service import interview_prep_service
from app.services.ollama_service import OllamaError
from app.utils.json_tools import parse_llm_json

router = APIRouter(prefix="/interview", tags=["Interview Prep"])


class InterviewPrepRequest(BaseModel):
    resume_text: str
    job_description: str


@router.post("/prep")
async def interview_prep(body: InterviewPrepRequest):
    if not body.resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text is required")
    if not body.job_description.strip():
        raise HTTPException(status_code=400, detail="job_description is required")

    try:
        raw = await interview_prep_service.generate(
            resume_text=body.resume_text,
            job_description=body.job_description,
        )
    except OllamaError as exc:
        status = 503 if exc.permanent else 504
        raise HTTPException(status_code=status, detail=str(exc))

    try:
        result = parse_llm_json(raw)
    except json.JSONDecodeError:
        return {"success": False, "error": "Model returned invalid JSON", "raw": raw}

    return {"success": True, "data": result}
