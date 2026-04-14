"""/prices/* router."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..providers import yf as yfp
from ..universe import SP500_TOP_100

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/snapshot/")
@router.get("/snapshot")
def snapshot(ticker: str = Query(...)):
    return {"snapshot": yfp.price_snapshot(ticker)}


@router.get("/")
@router.get("")
def prices(
    ticker: str = Query(...),
    interval: str = Query("day"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
):
    rows = yfp.historical_prices(ticker, interval=interval, start_date=start_date, end_date=end_date)
    if limit:
        rows = rows[-limit:]
    return {"ticker": ticker.upper(), "prices": rows}


@router.get("/snapshot/tickers/")
@router.get("/snapshot/tickers")
def snapshot_tickers():
    return {"tickers": SP500_TOP_100}
