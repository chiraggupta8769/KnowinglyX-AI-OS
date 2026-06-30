from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.career_service import career_service, CareerServiceError
from app.services.ollama_service import OllamaError

router = APIRouter(
    prefix="/career",
    tags=["Career Agent"]
)


class CareerAnalyzeRequest(BaseModel):
    resume_text: str
    job_description: str


@router.post("/analyze")
async def career_analyze(body: CareerAnalyzeRequest):
    try:
        result = await career_service.analyze(
            resume_text=body.resume_text,
            job_description=body.job_description,
        )
        return {"success": True, "data": result}

    except CareerServiceError as exc:
        raise HTTPException(
            status_code=422,
            detail={"stage": exc.stage, "error": exc.message},
        )
    except OllamaError as exc:
        status = 503 if exc.permanent else 504
        raise HTTPException(status_code=status, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
