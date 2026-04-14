"""
SEC EDGAR XBRL companyfacts client.

Fetches the complete reporting history for a company from
https://data.sec.gov/api/xbrl/companyfacts/CIK{10-digit-cik}.json
and transforms it into Financial Datasets–shaped statement rows.

Why this matters: yfinance only surfaces ~4 years of fundamentals.
XBRL companyfacts typically has 15+ years of pristine SEC-sourced data
for every public US company, for free, with no rate limit beyond a
polite User-Agent requirement.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable

import requests

from app.cache import cached
from app.config import SEC_USER_AGENT
from app.sec.concept_map import STATEMENT_CONFIGS
from app.sec.edgar import ticker_to_cik


BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# US-GAAP is the primary taxonomy for US filers. IFRS filers (foreign
# private issuers) use the "ifrs-full" taxonomy — we check both.
TAXONOMIES = ("us-gaap", "ifrs-full")


# -----------------------------------------------------------------------------
# Low-level fetcher
# -----------------------------------------------------------------------------
@cached("xbrl_companyfacts", ttl=6 * 60 * 60)  # 6h — updates on 8-K/10-Q
def _fetch_companyfacts(cik: str) -> dict[str, Any]:
    """Raw companyfacts JSON for a 10-digit CIK."""
    url = BASE_URL.format(cik=cik)
    headers = {
        "User-Agent": SEC_USER_AGENT,
        "Accept": "application/json",
        "Host": "data.sec.gov",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_companyfacts(ticker: str) -> dict[str, Any] | None:
    """Resolve ticker → CIK and fetch companyfacts. Returns None if no CIK found."""
    cik = ticker_to_cik(ticker)
    if not cik:
        return None
    try:
        return _fetch_companyfacts(cik)
    except requests.HTTPError as e:
        # Some tickers (e.g. ADRs) have CIKs but no XBRL facts — fall through gracefully.
        if e.response is not None and e.response.status_code == 404:
            return None
        raise


# -----------------------------------------------------------------------------
# Concept resolution
# -----------------------------------------------------------------------------
def _get_concept_entries(
    facts: dict[str, Any], concept: str
) -> list[dict[str, Any]]:
    """Return the entry list for a concept across us-gaap/ifrs-full, any USD-ish unit.

    Each entry looks like:
      {"start":"2023-10-01","end":"2024-09-28","val":391035000000,
       "accn":"0000320193-24-000123","fy":2024,"fp":"FY","form":"10-K",...}
    """
    for taxonomy in TAXONOMIES:
        concept_facts = facts.get("facts", {}).get(taxonomy, {}).get(concept)
        if not concept_facts:
            continue
        units = concept_facts.get("units", {})
        # Prefer USD, then USD/shares (for EPS), then anything
        for unit_key in ("USD", "USD/shares", "shares"):
            if unit_key in units:
                return units[unit_key]
        # Fallback: first unit available
        if units:
            return next(iter(units.values()))
    return []


def _resolve_concept_value(
    facts: dict[str, Any], concept_candidates: list[str], filter_fn
) -> float | None:
    """Try each candidate concept in order, return the first matching value."""
    for concept in concept_candidates:
        entries = _get_concept_entries(facts, concept)
        for e in entries:
            if filter_fn(e):
                val = e.get("val")
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    continue
                return float(val)
    return None


# -----------------------------------------------------------------------------
# Period key extraction
# -----------------------------------------------------------------------------
def _collect_period_keys(
    facts: dict[str, Any],
    concept_candidates: Iterable[str],
    value_type: str,
    period: str,
) -> list[tuple[str, str | None, str, str | None]]:
    """Discover all (end_date, start_date, form, fp) tuples for the given statement.

    We anchor on the first concept candidate that has data (usually Revenues
    for income, Assets for balance, CFO for cash flow). This gives us the
    canonical list of reporting periods the company has filed.

    For quarterly reports, 10-Qs include both the "three months ended" row
    AND year-to-date (6M / 9M) rows with the same end date — we filter by
    period duration (~90 days) to keep only the true quarter.

    Returns: sorted list of (end, start, form, fp) descending by end date.
    """
    from datetime import datetime

    seen: dict[tuple[str, str | None], tuple[str, str | None]] = {}

    def _duration_days(start: str | None, end: str) -> int | None:
        if not start or not end:
            return None
        try:
            s = datetime.strptime(start, "%Y-%m-%d")
            e = datetime.strptime(end, "%Y-%m-%d")
            return (e - s).days
        except ValueError:
            return None

    for concept in concept_candidates:
        entries = _get_concept_entries(facts, concept)
        for e in entries:
            form = e.get("form", "")
            fp = e.get("fp")  # "FY", "Q1", "Q2", "Q3"
            end = e.get("end")
            start = e.get("start")
            if not end:
                continue

            if period == "annual":
                # Only 10-K (or 20-F for foreign) rows with fp=FY
                if form not in ("10-K", "10-K/A", "20-F", "20-F/A"):
                    continue
                if fp != "FY":
                    continue
                # Annual duration should be ~365 days (filter out YTD partials)
                if value_type == "duration":
                    dur = _duration_days(start, end)
                    if dur is not None and not (330 <= dur <= 400):
                        continue
            elif period == "quarterly":
                # Single-quarter data: duration ~90 days. Accept 10-Q or 10-K Q4 cuts.
                if form not in ("10-Q", "10-Q/A", "10-K", "10-K/A"):
                    continue
                if value_type == "duration":
                    dur = _duration_days(start, end)
                    if dur is None or not (60 <= dur <= 110):
                        continue

            # instant values (balance sheet) don't have start
            if value_type == "instant":
                start = None

            key = (end, start)
            if key not in seen:
                seen[key] = (form, fp)

        if seen:
            # We found periods via this anchor concept — stop looking
            break

    result = [(end, start, form, fp) for (end, start), (form, fp) in seen.items()]
    # Sort descending by end date (most recent first)
    result.sort(key=lambda t: t[0], reverse=True)
    return result


def _make_filter(end: str, start: str | None, value_type: str):
    """Build a filter function that matches an XBRL entry to a specific period."""
    if value_type == "instant":
        # Balance sheet: match on end date only
        def _f(e):
            return e.get("end") == end and e.get("start") is None
        return _f
    else:
        # Income / cash flow: match on end AND start for exact period alignment
        def _f(e):
            return e.get("end") == end and e.get("start") == start
        return _f


# -----------------------------------------------------------------------------
# Public API: build statement rows
# -----------------------------------------------------------------------------
def build_statement_rows(
    ticker: str,
    statement_type: str,
    period: str,
    limit: int = 4,
) -> list[dict[str, Any]] | None:
    """Build FD-shaped statement rows for a ticker.

    Returns None if the company has no XBRL facts (e.g. private, foreign-only,
    or too old). Callers should fall back to yfinance in that case.

    Args:
      statement_type: "income" | "balance" | "cash_flow"
      period: "annual" | "quarterly" | "ttm"
    """
    config = STATEMENT_CONFIGS[statement_type]
    field_map: dict[str, list[str]] = config["map"]
    value_type: str = config["value_type"]
    post_compute: dict = config["post_compute"]

    facts = fetch_companyfacts(ticker)
    if facts is None:
        return None

    # TTM = aggregate the last 4 quarters (income/cash flow) or use latest (balance)
    if period == "ttm":
        if value_type == "instant":
            # Balance sheet TTM = latest balance sheet (point in time, doesn't aggregate)
            quarterly = build_statement_rows(ticker, statement_type, "quarterly", limit=1)
            if quarterly:
                for row in quarterly:
                    row["period"] = "ttm"
            return quarterly
        return _build_ttm_rows(ticker, facts, statement_type, limit)

    # Discover all reported periods
    anchor_concepts = next(iter(field_map.values()))  # first field's candidates
    period_keys = _collect_period_keys(facts, anchor_concepts, value_type, period)

    if not period_keys:
        return None

    period_keys = period_keys[: max(limit * 2, limit)]  # allow slight over-fetch for filtering

    rows: list[dict[str, Any]] = []
    ticker_upper = ticker.upper()

    for end, start, _form, _fp in period_keys[:limit]:
        row: dict[str, Any] = {
            "ticker": ticker_upper,
            "report_period": end,
            "period": period,
            "currency": "USD",
        }

        filter_fn = _make_filter(end, start, value_type)

        for fd_field, concepts in field_map.items():
            row[fd_field] = _resolve_concept_value(facts, concepts, filter_fn)

        # Apply computed fields
        for fd_field, compute_fn in post_compute.items():
            row[fd_field] = compute_fn(row)

        rows.append(row)

    return rows


# -----------------------------------------------------------------------------
# TTM aggregation
# -----------------------------------------------------------------------------
def _build_ttm_rows(
    ticker: str, facts: dict[str, Any], statement_type: str, limit: int
) -> list[dict[str, Any]] | None:
    """Sum trailing 4 quarters for each TTM endpoint."""
    config = STATEMENT_CONFIGS[statement_type]
    field_map: dict[str, list[str]] = config["map"]
    post_compute: dict = config["post_compute"]

    # Get quarterly rows (fetch extra to allow rolling-window aggregation)
    quarterly = build_statement_rows(ticker, statement_type, "quarterly", limit=limit + 4)
    if not quarterly:
        return None

    ttm_rows: list[dict[str, Any]] = []
    # Reverse to chronological order for rolling window
    quarterly_chrono = list(reversed(quarterly))

    for i in range(3, len(quarterly_chrono)):
        window = quarterly_chrono[i - 3 : i + 1]
        end_q = window[-1]

        row: dict[str, Any] = {
            "ticker": ticker.upper(),
            "report_period": end_q["report_period"],
            "period": "ttm",
            "currency": "USD",
        }

        for fd_field in field_map.keys():
            vals = [q.get(fd_field) for q in window if q.get(fd_field) is not None]
            if not vals:
                row[fd_field] = None
            else:
                # EPS fields average, all others sum
                if fd_field.startswith("earnings_per_share"):
                    row[fd_field] = sum(vals)  # TTM EPS = sum of quarterly EPS
                else:
                    row[fd_field] = sum(vals)

        # Re-compute derived fields from aggregated values
        for fd_field, compute_fn in post_compute.items():
            row[fd_field] = compute_fn(row)

        ttm_rows.append(row)

    # Most recent first, limit
    ttm_rows.reverse()
    return ttm_rows[:limit]
