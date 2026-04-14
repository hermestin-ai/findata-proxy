"""Pydantic response models (kept minimal; most responses use dicts)."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel


class Health(BaseModel):
    status: str
    provider: str
    version: str


class ErrorResponse(BaseModel):
    error: str


class PriceSnapshot(BaseModel):
    ticker: str
    price: Optional[float] = None
    day_change: Optional[float] = None
    day_change_percent: Optional[float] = None
    time: Optional[str] = None
    market_cap: Optional[float] = None
    volume: Optional[float] = None


class Price(BaseModel):
    ticker: str
    open: Optional[float] = None
    close: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None
    time: Optional[str] = None


class ScreenerFilter(BaseModel):
    field: str
    operator: str
    value: Any


class ScreenerRequest(BaseModel):
    filters: list[ScreenerFilter] = []
    currency: str = "USD"
    limit: int = 25
    order_by: Optional[str] = None
