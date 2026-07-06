from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import logging

from app.routes.ai import router as ai_router
from app.routes.resume import router as resume_router
from app.routes.jobs import router as jobs_router
from app.routes.match import router as match_router
from app.routes.cover_letter import router as cover_letter_router
from app.routes.career import router as career_router
from app.routes.agent import router as agent_router
from app.routes.resume_rewrite import router as resume_rewrite_router
from app.routes.interview import router as interview_router
from app.routes.job_scanner import router as job_scanner_router
from app.routes.job_match import router as job_match_router

# Boot tool registry (registers file_create, file_read, exec_code)
import app.tools  # noqa: F401

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="KnowinglyX AI OS",
    version="2.0.0",
    description="AI Career Operating System + Dev Agent",
)

# Static Files
app.mount("/static", StaticFiles(directory="app/templates"), name="static")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s: %s", request.url, exc)
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error", "detail": str(exc)},
    )


@app.get("/", include_in_schema=False)
def home():
    return FileResponse("app/templates/index.html")


@app.get("/health")
def health():
    return {"status": "healthy", "version": "2.0.0"}


app.include_router(ai_router)
app.include_router(resume_router)
app.include_router(jobs_router)
app.include_router(match_router)
app.include_router(cover_letter_router)
app.include_router(career_router)
app.include_router(agent_router)
app.include_router(resume_rewrite_router)
app.include_router(interview_router)
app.include_router(job_scanner_router)
app.include_router(job_match_router)
