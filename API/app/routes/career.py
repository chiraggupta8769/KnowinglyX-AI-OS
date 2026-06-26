from fastapi import APIRouter

print("=" * 60)
print("🚀 CAREER.PY LOADED")
print("=" * 60)

router = APIRouter(
    prefix="/career",
    tags=["Career Agent"]
)


@router.post("/analyze")
async def career_analyze():
    print("🔥 /career/analyze HIT")

    return {
        "success": True,
        "message": "Career Route Working"
    }