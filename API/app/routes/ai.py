from fastapi import APIRouter, Query, HTTPException
from app.services.ollama_service import ollama_service, OllamaError

router = APIRouter(
    prefix="/ai",
    tags=["AI"]
)


@router.get("")
async def chat(
    prompt: str = Query(...),
    model: str = Query(default="gemma3:4b", description="Ollama model to use"),
):
    try:
        response = await ollama_service.chat(prompt=prompt, model=model)
    except OllamaError as exc:
        status = 503 if exc.permanent else 504
        raise HTTPException(status_code=status, detail=str(exc))

    return {
        "success": True,
        "model": model,
        "prompt": prompt,
        "response": response,
    }
