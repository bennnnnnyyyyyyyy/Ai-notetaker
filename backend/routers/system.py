from fastapi import APIRouter

from backend.diagnostics import get_readiness

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/readiness")
async def readiness():
    """Report local capture prerequisites without starting a capture."""
    return await get_readiness()
