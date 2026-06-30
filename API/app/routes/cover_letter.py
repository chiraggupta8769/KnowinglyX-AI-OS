from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.cover_letter_service import cover_letter_service
from app.services.ollama_service import OllamaError

router = APIRouter(
    prefix="/cover-letter",
    tags=["Cover Letter"]
)


class CoverLetterRequest(BaseModel):
    resume: dict
    job: dict


@router.post("/")
async def generate_cover_letter(request: CoverLetterRequest):
    try:
        letter = await cover_letter_service.generate(request.resume, request.job)
    except OllamaError as exc:
        status = 503 if exc.permanent else 504
        raise HTTPException(status_code=status, detail=str(exc))

    return {"success": True, "cover_letter": letter}
