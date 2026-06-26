from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes.ai import router as ai_router
from app.routes.resume import router as resume_router
from app.routes.jobs import router as jobs_router
from app.routes.match import router as match_router
from app.routes.cover_letter import router as cover_letter_router
from app.routes.career import router as career_router

app = FastAPI(
    title="KnowinglyX AI OS",
    version="1.0.0",
    description="AI Career Operating System"
)

# Static Files (future use)
app.mount("/static", StaticFiles(directory="app/templates"), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse("app/templates/index.html")


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


app.include_router(ai_router)
app.include_router(resume_router)
app.include_router(jobs_router)
app.include_router(match_router)
app.include_router(cover_letter_router)
app.include_router(career_router)