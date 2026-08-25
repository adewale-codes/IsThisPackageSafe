"""Phase 12: GET /stats - public, unauthenticated, aggregate-only usage
numbers. No auth because nothing here requires it - see stats.py's module
docstring for exactly what is and isn't tracked."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import StatsResponse
from app.services import stats

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    data = await stats.get_cached_stats()
    return StatsResponse(**data)
