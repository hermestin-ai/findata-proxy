"""/financials/* and /financial-metrics/* routers."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..providers import yf as yfp

router = APIRouter(tags=["financials"])


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
):
    rows = yfp.income_statements(ticker, period=period, limit=max(limit, 20))
    rows = _apply_date_filters(rows, report_period_gt, report_period_gte, report_period_lt, report_period_lte)
    return {"income_statements": rows[:limit]}


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
):
    rows = yfp.balance_sheets(ticker, period=period, limit=max(limit, 20))
    rows = _apply_date_filters(rows, report_period_gt, report_period_gte, report_period_lt, report_period_lte)
    return {"balance_sheets": rows[:limit]}


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
):
    rows = yfp.cash_flow_statements(ticker, period=period, limit=max(limit, 20))
    rows = _apply_date_filters(rows, report_period_gt, report_period_gte, report_period_lt, report_period_lte)
    return {"cash_flow_statements": rows[:limit]}


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
):
    inc = yfp.income_statements(ticker, period=period, limit=max(limit, 20))
    bal = yfp.balance_sheets(ticker, period=period, limit=max(limit, 20))
    cf = yfp.cash_flow_statements(ticker, period=period, limit=max(limit, 20))
    inc = _apply_date_filters(inc, report_period_gt, report_period_gte, report_period_lt, report_period_lte)
    bal = _apply_date_filters(bal, report_period_gt, report_period_gte, report_period_lt, report_period_lte)
    cf = _apply_date_filters(cf, report_period_gt, report_period_gte, report_period_lt, report_period_lte)

    # group by report_period
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
    return {"financials": out}


# ---- Financial metrics -----------------------------------------------------

@router.get("/financial-metrics/snapshot/")
@router.get("/financial-metrics/snapshot")
def metrics_snapshot(ticker: str = Query(...)):
    return {"snapshot": yfp.metrics_snapshot(ticker)}


@router.get("/financial-metrics/")
@router.get("/financial-metrics")
def metrics_historical(
    ticker: str = Query(...),
    period: str = Query("ttm"),
    limit: int = Query(4),
):
    # v1: wrap snapshot as a single-item list keyed by latest report_period.
    snap = yfp.metrics_snapshot(ticker)
    incs = yfp.income_statements(ticker, period="quarterly" if period != "annual" else "annual", limit=max(limit, 1))
    latest_rp = incs[0].get("report_period") if incs else None
    snap_out = dict(snap)
    snap_out["report_period"] = latest_rp
    snap_out["period"] = period
    return {"financial_metrics": [snap_out]}


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
        "note": "Segment revenue parsing is not implemented in findata-proxy v1 (requires XBRL footnote parsing). Known gap.",
    }
