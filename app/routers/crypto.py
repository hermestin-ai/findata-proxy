"""/crypto/* router — via CoinGecko."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..providers import coingecko as cg

router = APIRouter(prefix="/crypto/prices", tags=["crypto"])


@router.get("/snapshot/")
@router.get("/snapshot")
def snapshot(ticker: str = Query(...)):
    return {"snapshot": cg.price_snapshot(ticker)}


@router.get("/")
@router.get("")
def prices(
    ticker: str = Query(...),
    interval: str = Query("day"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
):
    rows = cg.historical_prices(ticker, interval=interval, start_date=start_date, end_date=end_date)
    if limit:
        rows = rows[-limit:]
    return {"ticker": ticker.upper(), "prices": rows}


@router.get("/tickers/")
@router.get("/tickers")
def tickers():
    return {"tickers": cg.top_tickers(50)}
