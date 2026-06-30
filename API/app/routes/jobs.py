import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.job_service import job_service
from app.services.ollama_service import OllamaError

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)


class JobRequest(BaseModel):
    job_description: str


@router.post("/analyze")
async def analyze_job(request: JobRequest):
    try:
        ai_response = await job_service.analyze_job(request.job_description)
    except OllamaError as exc:
        status = 503 if exc.permanent else 504
        raise HTTPException(status_code=status, detail=str(exc))

    try:
        parsed = json.loads(ai_response)
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Model did not return valid JSON.",
            "raw_response": ai_response,
        }

    return {"success": True, "analysis": parsed}
