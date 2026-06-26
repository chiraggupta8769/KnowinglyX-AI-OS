from fastapi import APIRouter, Query
from app.services.ollama_service import ollama_service

router = APIRouter(
    prefix="/ai",
    tags=["AI"]
)


@router.get("")
def chat(
    prompt: str = Query(...),
    model: str = Query(
        default="gemma3:4b",
        description="Ollama model to use"
    )
):
    response = ollama_service.chat(
        prompt=prompt,
        model=model
    )

    return {
        "success": True,
        "model": model,
        "prompt": prompt,
        "response": response
    }