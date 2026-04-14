"""/insider-trades/* router — via SEC EDGAR Form 4 (metadata only in v1)."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..sec import edgar

router = APIRouter(prefix="/insider-trades", tags=["insider-trades"])


@router.get("/")
@router.get("")
def insider_trades(ticker: str = Query(...), limit: int = Query(10)):
    filings = edgar.list_form4(ticker, limit=limit)
    # Shape the response to resemble FD's insider_trades schema.
    # NOTE: Per-transaction detail requires parsing Form 4 XML (TODO).
    out = []
    for f in filings:
        out.append({
            "ticker": ticker.upper(),
            "issuer": ticker.upper(),
            "name": None,
            "title": None,
            "transaction_date": f.get("period_of_report") or f.get("filing_date"),
            "filing_date": f.get("filing_date"),
            "transaction_shares": None,
            "transaction_price_per_share": None,
            "transaction_value": None,
            "shares_owned_after_transaction": None,
            "security_title": None,
            "accession_number": f.get("accession_number"),
            "url": f.get("url"),
            "note": "Form 4 metadata only; full transaction fields require XML parsing (TODO).",
        })
    return {"insider_trades": out}
