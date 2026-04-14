"""yfinance provider wrappers — return JSON-safe dicts."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Optional

import yfinance as yf

from ..cache import cached


# ---- JSON sanitization helpers --------------------------------------------

def _safe(v: Any) -> Any:
    """Convert pandas/numpy/NaN values to JSON-safe Python types."""
    if v is None:
        return None
    # pandas Timestamp / datetime
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:
            pass
    # numpy/pandas NaN
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except Exception:
        pass
    try:
        import numpy as np  # local import

        if isinstance(v, (np.floating,)):
            f = float(v)
            return None if math.isnan(f) else f
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.bool_,)):
            return bool(v)
    except Exception:
        pass
    if isinstance(v, (int, float, str, bool)):
        try:
            if isinstance(v, float) and math.isnan(v):
                return None
        except Exception:
            pass
        return v
    # pandas Timestamp string fallback
    try:
        return str(v)
    except Exception:
        return None


def _num(v: Any) -> Optional[float]:
    s = _safe(v)
    if s is None:
        return None
    try:
        f = float(s)
        if math.isnan(f):
            return None
        return f
    except Exception:
        return None


def _date_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    if hasattr(v, "strftime"):
        try:
            return v.strftime("%Y-%m-%d")
        except Exception:
            pass
    try:
        return str(v)[:10]
    except Exception:
        return None


# ---- Interval mapping ------------------------------------------------------

_INTERVAL_MAP = {
    "minute": "1m",
    "5minute": "5m",
    "15minute": "15m",
    "30minute": "30m",
    "hour": "1h",
    "day": "1d",
    "week": "1wk",
    "month": "1mo",
    "year": "3mo",  # yfinance has no yearly; use 3mo as per spec
}


def map_interval(interval: str) -> str:
    return _INTERVAL_MAP.get((interval or "day").lower(), "1d")


# ---- Ticker wrapper --------------------------------------------------------

@cached("yf_info", ttl=900)
def get_info(ticker: str) -> dict[str, Any]:
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        # normalize to JSON-safe
        return {k: _safe(v) for k, v in info.items()}
    except Exception as e:
        return {"_error": str(e)}


@cached("yf_fast", ttl=60)
def get_fast_info(ticker: str) -> dict[str, Any]:
    try:
        t = yf.Ticker(ticker)
        fi = t.fast_info
        out: dict[str, Any] = {}
        # fast_info is a mapping-like object
        for key in ("last_price", "previous_close", "open", "day_high", "day_low",
                     "last_volume", "market_cap", "currency", "exchange"):
            try:
                out[key] = _safe(getattr(fi, key, None))
            except Exception:
                out[key] = None
        return out
    except Exception as e:
        return {"_error": str(e)}


def price_snapshot(ticker: str) -> dict[str, Any]:
    fi = get_fast_info(ticker)
    info = get_info(ticker)
    last = _num(fi.get("last_price"))
    prev = _num(fi.get("previous_close"))
    day_change = None
    day_change_pct = None
    if last is not None and prev is not None:
        day_change = last - prev
        day_change_pct = (day_change / prev * 100.0) if prev else None
    mcap = _num(fi.get("market_cap")) or _num(info.get("marketCap"))
    vol = _num(fi.get("last_volume")) or _num(info.get("volume"))
    return {
        "ticker": ticker.upper(),
        "price": last,
        "day_change": day_change,
        "day_change_percent": day_change_pct,
        "time": datetime.now(timezone.utc).isoformat(),
        "market_cap": mcap,
        "volume": vol,
    }


@cached("yf_hist", ttl=300)
def historical_prices(
    ticker: str,
    interval: str = "day",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict[str, Any]]:
    yf_interval = map_interval(interval)
    try:
        t = yf.Ticker(ticker)
        kwargs: dict[str, Any] = {"interval": yf_interval, "auto_adjust": False}
        if start_date:
            kwargs["start"] = start_date
        if end_date:
            kwargs["end"] = end_date
        if not start_date and not end_date:
            kwargs["period"] = "1y"
        df = t.history(**kwargs)
        if df is None or df.empty:
            return []
        rows: list[dict[str, Any]] = []
        for idx, row in df.iterrows():
            ts = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
            rows.append({
                "ticker": ticker.upper(),
                "open": _num(row.get("Open")),
                "close": _num(row.get("Close")),
                "high": _num(row.get("High")),
                "low": _num(row.get("Low")),
                "volume": _num(row.get("Volume")),
                "time": ts,
            })
        return rows
    except Exception:
        return []


# ---- Financial statements --------------------------------------------------

# yfinance row-label → canonical field name. Extensive best-effort mapping.
_INCOME_MAP = {
    "Total Revenue": "revenue",
    "Revenue": "revenue",
    "Operating Revenue": "revenue",
    "Cost Of Revenue": "cost_of_revenue",
    "Cost of Revenue": "cost_of_revenue",
    "Gross Profit": "gross_profit",
    "Operating Expense": "operating_expenses",
    "Total Operating Expenses": "operating_expenses",
    "Operating Income": "operating_income",
    "Net Income": "net_income",
    "Net Income Common Stockholders": "net_income_common_shareholders",
    "Net Income From Continuing Operations": "net_income_continuing_operations",
    "Basic EPS": "earnings_per_share",
    "Diluted EPS": "earnings_per_share_diluted",
    "EBITDA": "ebitda",
    "EBIT": "ebit",
    "Interest Expense": "interest_expense",
    "Tax Provision": "income_tax_expense",
    "Research And Development": "research_and_development",
    "Selling General And Administration": "selling_general_and_administrative_expenses",
    "Basic Average Shares": "weighted_average_shares",
    "Diluted Average Shares": "weighted_average_shares_diluted",
}

_BALANCE_MAP = {
    "Total Assets": "total_assets",
    "Total Liabilities Net Minority Interest": "total_liabilities",
    "Total Liabilities": "total_liabilities",
    "Stockholders Equity": "shareholders_equity",
    "Total Equity Gross Minority Interest": "total_equity",
    "Common Stock Equity": "total_equity",
    "Cash And Cash Equivalents": "cash_and_equivalents",
    "Cash Cash Equivalents And Short Term Investments": "cash_and_equivalents",
    "Total Debt": "total_debt",
    "Long Term Debt": "long_term_debt",
    "Current Debt": "short_term_debt",
    "Current Assets": "current_assets",
    "Current Liabilities": "current_liabilities",
    "Inventory": "inventory",
    "Accounts Receivable": "accounts_receivable",
    "Goodwill": "goodwill",
    "Retained Earnings": "retained_earnings",
    "Working Capital": "working_capital",
    "Net Tangible Assets": "net_tangible_assets",
    "Share Issued": "shares_outstanding",
    "Ordinary Shares Number": "shares_outstanding",
}

_CASHFLOW_MAP = {
    "Operating Cash Flow": "net_cash_flow_from_operations",
    "Cash Flow From Continuing Operating Activities": "net_cash_flow_from_operations",
    "Investing Cash Flow": "net_cash_flow_from_investing",
    "Financing Cash Flow": "net_cash_flow_from_financing",
    "Capital Expenditure": "capital_expenditure",
    "Free Cash Flow": "free_cash_flow",
    "Issuance Of Debt": "issuance_of_debt",
    "Repayment Of Debt": "repayment_of_debt",
    "Cash Dividends Paid": "dividends_paid",
    "Repurchase Of Capital Stock": "share_buybacks",
    "Net Income From Continuing Operations": "net_income",
    "Depreciation And Amortization": "depreciation_and_amortization",
    "Change In Working Capital": "change_in_working_capital",
}


def _df_to_statements(df, mapping: dict[str, str], ticker: str, period_label: str) -> list[dict[str, Any]]:
    if df is None or getattr(df, "empty", True):
        return []
    out: list[dict[str, Any]] = []
    # columns are dates; rows are line items
    for col in df.columns:
        rp = _date_str(col)
        record: dict[str, Any] = {
            "ticker": ticker.upper(),
            "report_period": rp,
            "period": period_label,
            "currency": "USD",
        }
        for row_label, field in mapping.items():
            if row_label in df.index:
                record[field] = _num(df.at[row_label, col])
        out.append(record)
    # sort desc by report_period
    out.sort(key=lambda r: r.get("report_period") or "", reverse=True)
    return out


def _sum_last_n(statements: list[dict[str, Any]], n: int = 4) -> dict[str, Any]:
    """TTM: sum numeric fields across last n quarters."""
    if not statements:
        return {}
    subset = statements[:n]
    agg: dict[str, Any] = {}
    # copy non-numeric metadata from latest
    latest = subset[0]
    agg["ticker"] = latest.get("ticker")
    agg["report_period"] = latest.get("report_period")
    agg["period"] = "ttm"
    agg["currency"] = latest.get("currency", "USD")
    # numeric keys
    numeric_keys: set[str] = set()
    for s in subset:
        for k, v in s.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                numeric_keys.add(k)
    for k in numeric_keys:
        vals = [s.get(k) for s in subset if isinstance(s.get(k), (int, float))]
        if vals:
            # average EPS-like fields; sum flow fields. Heuristic: avg if field contains 'per_share' or 'eps' or 'ratio' or 'margin'
            if any(tok in k for tok in ("per_share", "eps", "ratio", "margin")):
                agg[k] = sum(vals) / len(vals)
            else:
                agg[k] = sum(vals)
    return agg


@cached("yf_income", ttl=3600)
def income_statements(ticker: str, period: str = "annual", limit: int = 4) -> list[dict[str, Any]]:
    try:
        t = yf.Ticker(ticker)
        if period == "quarterly":
            df = t.quarterly_income_stmt
            stmts = _df_to_statements(df, _INCOME_MAP, ticker, "quarterly")
        elif period == "ttm":
            df = t.quarterly_income_stmt
            quarterly = _df_to_statements(df, _INCOME_MAP, ticker, "quarterly")
            ttm = _sum_last_n(quarterly, 4)
            stmts = [ttm] if ttm else []
        else:
            df = t.income_stmt
            stmts = _df_to_statements(df, _INCOME_MAP, ticker, "annual")
        return stmts[: max(1, limit)]
    except Exception:
        return []


@cached("yf_balance", ttl=3600)
def balance_sheets(ticker: str, period: str = "annual", limit: int = 4) -> list[dict[str, Any]]:
    try:
        t = yf.Ticker(ticker)
        if period == "quarterly":
            df = t.quarterly_balance_sheet
            stmts = _df_to_statements(df, _BALANCE_MAP, ticker, "quarterly")
        elif period == "ttm":
            # balance sheet is a snapshot; return latest quarter flagged as ttm
            df = t.quarterly_balance_sheet
            q = _df_to_statements(df, _BALANCE_MAP, ticker, "quarterly")
            if q:
                latest = dict(q[0])
                latest["period"] = "ttm"
                stmts = [latest]
            else:
                stmts = []
        else:
            df = t.balance_sheet
            stmts = _df_to_statements(df, _BALANCE_MAP, ticker, "annual")
        return stmts[: max(1, limit)]
    except Exception:
        return []


@cached("yf_cashflow", ttl=3600)
def cash_flow_statements(ticker: str, period: str = "annual", limit: int = 4) -> list[dict[str, Any]]:
    try:
        t = yf.Ticker(ticker)
        if period == "quarterly":
            df = t.quarterly_cashflow
            stmts = _df_to_statements(df, _CASHFLOW_MAP, ticker, "quarterly")
        elif period == "ttm":
            df = t.quarterly_cashflow
            quarterly = _df_to_statements(df, _CASHFLOW_MAP, ticker, "quarterly")
            ttm = _sum_last_n(quarterly, 4)
            stmts = [ttm] if ttm else []
        else:
            df = t.cashflow
            stmts = _df_to_statements(df, _CASHFLOW_MAP, ticker, "annual")
        return stmts[: max(1, limit)]
    except Exception:
        return []


# ---- Financial metrics (from .info) ----------------------------------------

def metrics_snapshot(ticker: str) -> dict[str, Any]:
    info = get_info(ticker)
    if info.get("_error"):
        return {"ticker": ticker.upper(), "error": info["_error"]}

    def g(key: str) -> Optional[float]:
        return _num(info.get(key))

    return {
        "ticker": ticker.upper(),
        "market_cap": g("marketCap"),
        "enterprise_value": g("enterpriseValue"),
        "price_to_earnings_ratio": g("trailingPE"),
        "forward_price_to_earnings_ratio": g("forwardPE"),
        "price_to_book_ratio": g("priceToBook"),
        "price_to_sales_ratio": g("priceToSalesTrailing12Months"),
        "enterprise_value_to_ebitda_ratio": g("enterpriseToEbitda"),
        "enterprise_value_to_revenue_ratio": g("enterpriseToRevenue"),
        "peg_ratio": g("pegRatio") or g("trailingPegRatio"),
        "gross_margin": g("grossMargins"),
        "operating_margin": g("operatingMargins"),
        "net_margin": g("profitMargins"),
        "return_on_equity": g("returnOnEquity"),
        "return_on_assets": g("returnOnAssets"),
        "current_ratio": g("currentRatio"),
        "quick_ratio": g("quickRatio"),
        "debt_to_equity": g("debtToEquity"),
        "earnings_per_share": g("trailingEps"),
        "forward_earnings_per_share": g("forwardEps"),
        "book_value_per_share": g("bookValue"),
        "free_cash_flow_per_share": None,  # computed below if possible
        "revenue_growth": g("revenueGrowth"),
        "earnings_growth": g("earningsGrowth"),
        "earnings_quarterly_growth": g("earningsQuarterlyGrowth"),
        "revenue_per_share": g("revenuePerShare"),
        "dividend_yield": g("dividendYield"),
        "payout_ratio": g("payoutRatio"),
        "beta": g("beta"),
        "fifty_two_week_high": g("fiftyTwoWeekHigh"),
        "fifty_two_week_low": g("fiftyTwoWeekLow"),
        "shares_outstanding": g("sharesOutstanding"),
        "float_shares": g("floatShares"),
        "currency": info.get("currency") or "USD",
        "time": datetime.now(timezone.utc).isoformat(),
    }


# ---- News -----------------------------------------------------------------

@cached("yf_news", ttl=300)
def news(ticker: str, limit: int = 10) -> list[dict[str, Any]]:
    try:
        t = yf.Ticker(ticker)
        items = t.news or []
        out: list[dict[str, Any]] = []
        for it in items[:limit]:
            # newer yfinance wraps under 'content'
            c = it.get("content") if isinstance(it, dict) else None
            if c:
                provider = c.get("provider", {}) or {}
                url = (c.get("canonicalUrl", {}) or {}).get("url") or (c.get("clickThroughUrl", {}) or {}).get("url")
                out.append({
                    "ticker": ticker.upper(),
                    "title": c.get("title"),
                    "author": provider.get("displayName"),
                    "source": provider.get("displayName"),
                    "date": c.get("pubDate") or c.get("displayTime"),
                    "url": url,
                })
            else:
                out.append({
                    "ticker": ticker.upper(),
                    "title": it.get("title"),
                    "author": it.get("publisher"),
                    "source": it.get("publisher"),
                    "date": _safe(it.get("providerPublishTime")),
                    "url": it.get("link"),
                })
        return out
    except Exception:
        return []


# ---- Earnings --------------------------------------------------------------

def earnings_snapshot(ticker: str) -> dict[str, Any]:
    out: dict[str, Any] = {"ticker": ticker.upper()}
    try:
        t = yf.Ticker(ticker)
        info = get_info(ticker)
        # latest quarterly income
        quarterly = income_statements(ticker, period="quarterly", limit=1)
        latest = quarterly[0] if quarterly else {}
        out["report_period"] = latest.get("report_period")
        out["revenue"] = latest.get("revenue")
        out["net_income"] = latest.get("net_income")
        out["eps"] = latest.get("earnings_per_share") or _num(info.get("trailingEps"))
        out["eps_estimate"] = _num(info.get("earningsQuarterlyGrowth"))  # rough
        # earnings_dates may have estimates
        try:
            ed = t.earnings_dates
            if ed is not None and not ed.empty:
                row = ed.iloc[0]
                eps_est = _num(row.get("EPS Estimate"))
                eps_rep = _num(row.get("Reported EPS"))
                surprise = _num(row.get("Surprise(%)"))
                if eps_est is not None:
                    out["eps_estimate"] = eps_est
                if eps_rep is not None and out.get("eps") is None:
                    out["eps"] = eps_rep
                if surprise is not None:
                    out["eps_surprise"] = surprise
        except Exception:
            pass
        out.setdefault("eps_surprise", None)
        out.setdefault("revenue_estimate", None)
        out.setdefault("revenue_surprise", None)
        return out
    except Exception as e:
        return {"ticker": ticker.upper(), "error": str(e)}


# ---- Analyst estimates -----------------------------------------------------

def analyst_estimates(ticker: str, period: str = "annual") -> list[dict[str, Any]]:
    try:
        t = yf.Ticker(ticker)
        out: list[dict[str, Any]] = []
        eps_est = getattr(t, "earnings_estimate", None)
        rev_est = getattr(t, "revenue_estimate", None)

        def _extract(df) -> dict[str, dict[str, Any]]:
            res: dict[str, dict[str, Any]] = {}
            if df is None or getattr(df, "empty", True):
                return res
            for idx, row in df.iterrows():
                key = str(idx)
                res[key] = {c: _num(row.get(c)) for c in df.columns}
            return res

        eps_map = _extract(eps_est)
        rev_map = _extract(rev_est)
        # keys typically: 0q,+1q,0y,+1y — restrict to annual (0y/+1y) or quarterly
        keys = list(eps_map.keys()) or list(rev_map.keys())
        if period == "annual":
            keys = [k for k in keys if "y" in k.lower()]
        elif period == "quarterly":
            keys = [k for k in keys if "q" in k.lower()]
        for k in keys:
            eps_row = eps_map.get(k, {})
            rev_row = rev_map.get(k, {})
            out.append({
                "ticker": ticker.upper(),
                "period": period,
                "fiscal_year": k,
                "eps_estimate": eps_row.get("avg"),
                "eps_estimate_low": eps_row.get("low"),
                "eps_estimate_high": eps_row.get("high"),
                "revenue_estimate": rev_row.get("avg"),
                "revenue_estimate_low": rev_row.get("low"),
                "revenue_estimate_high": rev_row.get("high"),
                "num_analysts": eps_row.get("numberOfAnalysts") or rev_row.get("numberOfAnalysts"),
            })
        return out
    except Exception:
        return []
