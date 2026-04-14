"""/earnings router."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..providers import yf as yfp

router = APIRouter(tags=["earnings"])


@router.get("/earnings")
@router.get("/earnings/")
def earnings(ticker: str = Query(...)):
    return {"earnings": yfp.earnings_snapshot(ticker)}
