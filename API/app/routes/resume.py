from fastapi import APIRouter, UploadFile, File

from app.utils.pdf import extract_text_from_pdf
from app.services.resume_service import resume_service

router = APIRouter(
    prefix="/resume",
    tags=["Resume"]
)


@router.post("/analyze")
async def analyze_resume(file: UploadFile = File(...)):
    pdf_bytes = await file.read()

    resume_text = extract_text_from_pdf(pdf_bytes)

    analysis = resume_service.analyze_resume(resume_text)

    return {
        "success": True,
        "filename": file.filename,
        "characters": len(resume_text),
        "analysis": analysis
    }