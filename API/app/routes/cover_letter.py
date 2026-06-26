from fastapi import APIRouter
from pydantic import BaseModel

from app.services.cover_letter_service import cover_letter_service

router = APIRouter(
    prefix="/cover-letter",
    tags=["Cover Letter"]
)


class CoverLetterRequest(BaseModel):
    resume: dict
    job: dict


@router.post("/")
def generate_cover_letter(request: CoverLetterRequest):

    letter = cover_letter_service.generate(
        request.resume,
        request.job
    )

    return {
        "success": True,
        "cover_letter": letter
    }