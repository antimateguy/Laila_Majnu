from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    # Pre-warm target. Provider and circuit-breaker state join this in Phase 7.
    return {"status": "ok"}
