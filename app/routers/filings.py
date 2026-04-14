"""/filings/* router — via SEC EDGAR."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..sec import edgar
from ..sec.items import ITEM_TYPES, extract_items

router = APIRouter(prefix="/filings", tags=["filings"])


@router.get("/")
@router.get("")
def list_filings(
    ticker: str = Query(...),
    filing_type: Optional[str] = Query(None),
    limit: int = Query(10),
):
    rows = edgar.list_filings(ticker, filing_type=filing_type, limit=limit)
    return {"filings": rows}


@router.get("/items/types/")
@router.get("/items/types")
def item_types():
    return ITEM_TYPES


@router.get("/items/")
@router.get("/items")
def filing_items(
    ticker: str = Query(...),
    accession_number: str = Query(...),
    items: str = Query(..., description="Comma-separated list of item names"),
):
    wanted = [s.strip() for s in items.split(",") if s.strip()]
    return {"items": extract_items(ticker, accession_number, wanted)}
