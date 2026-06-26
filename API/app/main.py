from fastapi import FastAPI

from app.routes.ai import router as ai_router
from app.routes.resume import router as resume_router

app = FastAPI(
    title="KnowinglyX AI OS",
    version="0.4.0",
    description="AI Career Operating System"
)


@app.get("/")
def root():
    return {
        "status": "running",
        "project": "KnowinglyX AI OS",
        "version": "0.4.0"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# Register Routes
app.include_router(ai_router)
app.include_router(resume_router)