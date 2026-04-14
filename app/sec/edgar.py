"""SEC EDGAR helpers: ticker→CIK, submissions/filings, Form 4 list."""
from __future__ import annotations

from typing import Any, Optional

import requests

from ..cache import cached, cache_get, cache_set
from ..config import SEC_HEADERS, SEC_DATA_HEADERS

TIMEOUT = 20

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"


# ---- Ticker → CIK mapping --------------------------------------------------

@cached("sec_tickers_map", ttl=86400)
def _load_ticker_map() -> dict[str, str]:
    try:
        r = requests.get(COMPANY_TICKERS_URL, headers=SEC_HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        # data is {"0":{"cik_str":320193,"ticker":"AAPL","title":"Apple Inc."},...}
        out: dict[str, str] = {}
        for _k, v in data.items():
            t = str(v.get("ticker", "")).upper()
            cik = str(v.get("cik_str", ""))
            if t and cik:
                out[t] = cik.zfill(10)
        return out
    except Exception:
        return {}


def ticker_to_cik(ticker: str) -> Optional[str]:
    t = (ticker or "").upper().strip()
    if not t:
        return None
    mapping = _load_ticker_map()
    return mapping.get(t)


# ---- Submissions / Filings --------------------------------------------------

@cached("sec_submissions", ttl=3600)
def get_submissions(cik: str) -> dict[str, Any]:
    try:
        url = SUBMISSIONS_URL.format(cik=cik)
        r = requests.get(url, headers=SEC_DATA_HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": str(e)}


def _accession_no_dashes(acc: str) -> str:
    return (acc or "").replace("-", "")


def _filing_url(cik: str, accession: str, primary_doc: str | None) -> str:
    acc_nodash = _accession_no_dashes(accession)
    cik_int = str(int(cik))  # no leading zeros in archive path
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}"
    if primary_doc:
        return f"{base}/{primary_doc}"
    return f"{base}/"


def list_filings(
    ticker: str,
    filing_type: Optional[str] = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    cik = ticker_to_cik(ticker)
    if not cik:
        return []
    sub = get_submissions(cik)
    if sub.get("_error"):
        return []
    recent = (sub.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accs = recent.get("accessionNumber") or []
    primaries = recent.get("primaryDocument") or []
    periods = recent.get("reportDate") or []

    out: list[dict[str, Any]] = []
    target = filing_type.upper() if filing_type else None
    for i, form in enumerate(forms):
        if target and (form or "").upper() != target:
            continue
        acc = accs[i] if i < len(accs) else None
        out.append({
            "ticker": ticker.upper(),
            "cik": cik,
            "filing_type": form,
            "filing_date": dates[i] if i < len(dates) else None,
            "accession_number": acc,
            "period_of_report": periods[i] if i < len(periods) else None,
            "url": _filing_url(cik, acc, primaries[i] if i < len(primaries) else None) if acc else None,
        })
        if len(out) >= limit:
            break
    return out


def list_form4(ticker: str, limit: int = 10) -> list[dict[str, Any]]:
    """List recent Form 4 filings for an issuer ticker."""
    return list_filings(ticker, filing_type="4", limit=limit)
