import json

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.match_service import match_service

router = APIRouter(
    prefix="/match",
    tags=["Match Engine"]
)


class MatchRequest(BaseModel):
    resume: dict
    job: dict


@router.post("/")
def match(request: MatchRequest):

    ai_response = match_service.match(
        request.resume,
        request.job
    )

    try:
        parsed = json.loads(ai_response)
    except json.JSONDecodeError:
        return {
            "success": False,
            "raw_response": ai_response
        }

    return {
        "success": True,
        "analysis": parsed
    }