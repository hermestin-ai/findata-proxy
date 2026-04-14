"""/financials/search/screener/* router — simple yfinance-backed screener."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..models import ScreenerRequest
from ..providers import yf as yfp
from ..universe import SP500_TOP_100

router = APIRouter(prefix="/financials/search/screener", tags=["screener"])


# Supported filter fields — map screener field → metrics_snapshot key
_FIELD_MAP: dict[str, str] = {
    "market_cap": "market_cap",
    "price_to_earnings_ratio": "price_to_earnings_ratio",
    "price_to_book_ratio": "price_to_book_ratio",
    "price_to_sales_ratio": "price_to_sales_ratio",
    "enterprise_value_to_ebitda_ratio": "enterprise_value_to_ebitda_ratio",
    "peg_ratio": "peg_ratio",
    "gross_margin": "gross_margin",
    "operating_margin": "operating_margin",
    "net_margin": "net_margin",
    "return_on_equity": "return_on_equity",
    "return_on_assets": "return_on_assets",
    "current_ratio": "current_ratio",
    "debt_to_equity": "debt_to_equity",
    "earnings_per_share": "earnings_per_share",
    "dividend_yield": "dividend_yield",
    "revenue_growth": "revenue_growth",
    "earnings_growth": "earnings_growth",
    "beta": "beta",
}

_FILTERS_SCHEMA: list[dict[str, Any]] = [
    {"field": f, "type": "number", "operators": ["gt", "gte", "lt", "lte", "eq"]}
    for f in _FIELD_MAP.keys()
]


@router.get("/filters/")
@router.get("/filters")
def screener_filters():
    return {"filters": _FILTERS_SCHEMA}


def _cmp(val: Any, op: str, target: Any) -> bool:
    if val is None:
        return False
    try:
        v = float(val)
        t = float(target)
    except Exception:
        return False
    op = (op or "gte").lower()
    if op in ("gt", ">"):
        return v > t
    if op in ("gte", ">="):
        return v >= t
    if op in ("lt", "<"):
        return v < t
    if op in ("lte", "<="):
        return v <= t
    if op in ("eq", "=="):
        return v == t
    return False


@router.post("/")
@router.post("")
def run_screener(req: ScreenerRequest):
    # NOTE: slow — iterates SP500_TOP_100 and fetches yfinance info for each.
    # TODO: back this with bulk data or a pre-computed fundamentals cache.
    results: list[dict[str, Any]] = []
    universe = SP500_TOP_100
    limit = max(1, min(int(req.limit or 25), 100))

    for ticker in universe:
        snap = yfp.metrics_snapshot(ticker)
        if snap.get("error"):
            continue
        info = yfp.get_info(ticker)
        passed = True
        for f in req.filters or []:
            key = _FIELD_MAP.get(f.field)
            if not key:
                passed = False
                break
            if not _cmp(snap.get(key), f.operator, f.value):
                passed = False
                break
        if not passed:
            continue
        row: dict[str, Any] = {
            "ticker": ticker,
            "name": info.get("shortName") or info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }
        # echo filtered fields
        for f in req.filters or []:
            key = _FIELD_MAP.get(f.field)
            if key:
                row[f.field] = snap.get(key)
        results.append(row)
        if len(results) >= limit:
            break
    return {"results": results, "currency": req.currency or "USD"}
