"""
Resume rewrite route — rewrites resume for a JD and returns PDF download.
"""
from __future__ import annotations

import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.services.resume_rewrite_service import resume_rewrite_service
from app.services.ollama_service import OllamaError
from app.utils.pdf_generator import generate_resume_pdf

router = APIRouter(prefix="/resume", tags=["Resume"])


class RewriteRequest(BaseModel):
    resume_text: str
    job_description: str
    target_role: str = ""


@router.post("/rewrite")
async def rewrite_resume(body: RewriteRequest):
    """Rewrite resume for a job description. Returns rewritten text."""
    if not body.resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text is required")
    if not body.job_description.strip():
        raise HTTPException(status_code=400, detail="job_description is required")

    try:
        rewritten = await resume_rewrite_service.rewrite(
            resume_text=body.resume_text,
            job_description=body.job_description,
        )
    except OllamaError as exc:
        status = 503 if exc.permanent else 504
        raise HTTPException(status_code=status, detail=str(exc))

    return {"success": True, "rewritten_resume": rewritten}


@router.post("/rewrite/pdf")
async def rewrite_resume_pdf(body: RewriteRequest):
    """Rewrite resume for a JD and return an ATS-friendly PDF."""
    if not body.resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text is required")
    if not body.job_description.strip():
        raise HTTPException(status_code=400, detail="job_description is required")

    try:
        rewritten = await resume_rewrite_service.rewrite(
            resume_text=body.resume_text,
            job_description=body.job_description,
        )
    except OllamaError as exc:
        status = 503 if exc.permanent else 504
        raise HTTPException(status_code=status, detail=str(exc))

    try:
        pdf_bytes = generate_resume_pdf(rewritten)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    # Derive filename from role or generic
    role_slug = re.sub(r"[^a-z0-9]+", "-", body.target_role.lower()).strip("-") if body.target_role else "resume"
    filename = f"{role_slug}-ats-optimized.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
