"""/financials/* and /financial-metrics/* routers.

Data source strategy:
  1. Try SEC XBRL companyfacts (15+ yr history, authoritative) via app.sec.xbrl
  2. Fall back to yfinance (~4 yr) when XBRL returns None (non-US, private, etc.)

The XBRL path is opt-out via query param `source=yfinance` for debugging.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query

from ..providers import yf as yfp
from ..sec import xbrl

logger = logging.getLogger(__name__)

router = APIRouter(tags=["financials"])


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _apply_date_filters(
    rows: list[dict],
    gt: Optional[str],
    gte: Optional[str],
    lt: Optional[str],
    lte: Optional[str],
) -> list[dict]:
    def keep(r: dict) -> bool:
        rp = r.get("report_period")
        if not rp:
            return True
        if gt and not (rp > gt):
            return False
        if gte and not (rp >= gte):
            return False
        if lt and not (rp < lt):
            return False
        if lte and not (rp <= lte):
            return False
        return True

    return [r for r in rows if keep(r)]


def _fetch_with_fallback(
    ticker: str,
    statement_type: str,
    period: str,
    fetch_limit: int,
    source: str,
    yf_fallback,
) -> tuple[list[dict], str]:
    """Try XBRL first, fall back to yfinance. Returns (rows, source_used)."""
    if source != "yfinance":
        try:
            rows = xbrl.build_statement_rows(ticker, statement_type, period, limit=fetch_limit)
            if rows:
                return rows, "sec_xbrl"
        except Exception as e:
            logger.warning("XBRL fetch failed for %s/%s/%s: %s", ticker, statement_type, period, e)
    # Fallback
    return yf_fallback(ticker, period=period, limit=fetch_limit), "yfinance"


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@router.get("/financials/income-statements/")
@router.get("/financials/income-statements")
def income_statements(
    ticker: str = Query(...),
    period: str = Query("annual"),
    limit: int = Query(4),
    report_period_gt: Optional[str] = None,
    report_period_gte: Optional[str] = None,
    report_period_lt: Optional[str] = None,
    report_period_lte: Optional[str] = None,
    source: str = Query("auto", description="'auto' (XBRL→yfinance) or 'yfinance'"),
):
    rows, used = _fetch_with_fallback(
        ticker, "income", period, max(limit, 20), source, yfp.income_statements
    )
    rows = _apply_date_filters(rows, report_period_gt, report_period_gte, report_period_lt, report_period_lte)
    return {"income_statements": rows[:limit], "_source": used}


@router.get("/financials/balance-sheets/")
@router.get("/financials/balance-sheets")
def balance_sheets(
    ticker: str = Query(...),
    period: str = Query("annual"),
    limit: int = Query(4),
    report_period_gt: Optional[str] = None,
    report_period_gte: Optional[str] = None,
    report_period_lt: Optional[str] = None,
    report_period_lte: Optional[str] = None,
    source: str = Query("auto"),
):
    rows, used = _fetch_with_fallback(
        ticker, "balance", period, max(limit, 20), source, yfp.balance_sheets
    )
    rows = _apply_date_filters(rows, report_period_gt, report_period_gte, report_period_lt, report_period_lte)
    return {"balance_sheets": rows[:limit], "_source": used}


@router.get("/financials/cash-flow-statements/")
@router.get("/financials/cash-flow-statements")
def cash_flow_statements(
    ticker: str = Query(...),
    period: str = Query("annual"),
    limit: int = Query(4),
    report_period_gt: Optional[str] = None,
    report_period_gte: Optional[str] = None,
    report_period_lt: Optional[str] = None,
    report_period_lte: Optional[str] = None,
    source: str = Query("auto"),
):
    rows, used = _fetch_with_fallback(
        ticker, "cash_flow", period, max(limit, 20), source, yfp.cash_flow_statements
    )
    rows = _apply_date_filters(rows, report_period_gt, report_period_gte, report_period_lt, report_period_lte)
    return {"cash_flow_statements": rows[:limit], "_source": used}


@router.get("/financials/")
@router.get("/financials")
def combined_financials(
    ticker: str = Query(...),
    period: str = Query("annual"),
    limit: int = Query(4),
    report_period_gt: Optional[str] = None,
    report_period_gte: Optional[str] = None,
    report_period_lt: Optional[str] = None,
    report_period_lte: Optional[str] = None,
    source: str = Query("auto"),
):
    fetch_limit = max(limit, 20)
    inc, s_inc = _fetch_with_fallback(ticker, "income", period, fetch_limit, source, yfp.income_statements)
    bal, s_bal = _fetch_with_fallback(ticker, "balance", period, fetch_limit, source, yfp.balance_sheets)
    cf, s_cf = _fetch_with_fallback(ticker, "cash_flow", period, fetch_limit, source, yfp.cash_flow_statements)

    inc = _apply_date_filters(inc, report_period_gt, report_period_gte, report_period_lt, report_period_lte)
    bal = _apply_date_filters(bal, report_period_gt, report_period_gte, report_period_lt, report_period_lte)
    cf = _apply_date_filters(cf, report_period_gt, report_period_gte, report_period_lt, report_period_lte)

    by_period: dict[str, dict] = {}
    for row in inc:
        by_period.setdefault(row.get("report_period"), {})["income_statement"] = row
    for row in bal:
        by_period.setdefault(row.get("report_period"), {})["balance_sheet"] = row
    for row in cf:
        by_period.setdefault(row.get("report_period"), {})["cash_flow_statement"] = row

    ordered = sorted(by_period.items(), key=lambda kv: kv[0] or "", reverse=True)
    out = []
    for rp, bucket in ordered[:limit]:
        out.append({
            "report_period": rp,
            "period": period,
            "ticker": ticker.upper(),
            "income_statement": bucket.get("income_statement", {}),
            "balance_sheet": bucket.get("balance_sheet", {}),
            "cash_flow_statement": bucket.get("cash_flow_statement", {}),
        })

    return {
        "financials": out,
        "_source": {"income": s_inc, "balance": s_bal, "cash_flow": s_cf},
    }


# -----------------------------------------------------------------------------
# /financial-metrics/* — still yfinance (needs market-data mixing)
# -----------------------------------------------------------------------------
@router.get("/financial-metrics/snapshot/")
@router.get("/financial-metrics/snapshot")
def financial_metrics_snapshot(ticker: str = Query(...)):
    return {"snapshot": yfp.metrics_snapshot(ticker)}


@router.get("/financial-metrics/")
@router.get("/financial-metrics")
def financial_metrics(
    ticker: str = Query(...),
    period: str = Query("ttm"),
    limit: int = Query(4),
):
    snap = yfp.metrics_snapshot(ticker)
    return {"financial_metrics": [{**snap, "period": period}] * min(limit, 1)}


# ---- Segmented revenues (known gap / stub) ---------------------------------

@router.get("/financials/segmented-revenues/")
@router.get("/financials/segmented-revenues")
def segmented_revenues(
    ticker: str = Query(...),
    period: str = Query("annual"),
    limit: int = Query(4),
):
    return {
        "segmented_revenues": [],
        "note": "Segment revenue parsing is not implemented in findata-proxy (requires XBRL footnote / segment-axis parsing). Known gap.",
    }
