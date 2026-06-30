import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.match_service import match_service
from app.services.ollama_service import OllamaError

router = APIRouter(
    prefix="/match",
    tags=["Match Engine"]
)


class MatchRequest(BaseModel):
    resume: dict
    job: dict


@router.post("/")
async def match(request: MatchRequest):
    try:
        ai_response = await match_service.match(request.resume, request.job)
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
