"""/analyst-estimates/ router."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..providers import yf as yfp

router = APIRouter(prefix="/analyst-estimates", tags=["estimates"])


@router.get("/")
@router.get("")
def analyst_estimates(ticker: str = Query(...), period: str = Query("annual")):
    return {"analyst_estimates": yfp.analyst_estimates(ticker, period=period)}
