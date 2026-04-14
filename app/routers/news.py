"""/news router."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..providers import yf as yfp

router = APIRouter(tags=["news"])


@router.get("/news")
@router.get("/news/")
def news(ticker: Optional[str] = Query(None), limit: int = Query(10)):
    t = ticker or "SPY"
    return {"news": yfp.news(t, limit=limit)}
