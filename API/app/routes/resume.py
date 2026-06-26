import json

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.utils.pdf import extract_text_from_pdf
from app.services.resume_service import resume_service

router = APIRouter(
    prefix="/resume",
    tags=["Resume"]
)


@router.post("/analyze")
async def analyze_resume(file: UploadFile = File(...)):

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported."
        )

    pdf_bytes = await file.read()

    resume_text = extract_text_from_pdf(pdf_bytes)

    ai_response = resume_service.analyze_resume(resume_text)

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
        "filename": file.filename,
        "characters": len(resume_text),
        "analysis": parsed
    }