import json

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.job_service import job_service

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)


class JobRequest(BaseModel):
    job_description: str


@router.post("/analyze")
def analyze_job(request: JobRequest):

    ai_response = job_service.analyze_job(
        request.job_description
    )

    try:
        parsed = json.loads(ai_response)
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Model did not return valid JSON.",
            "raw_response": ai_response
        }

    return {
        "success": True,
        "analysis": parsed
    }