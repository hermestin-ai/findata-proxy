"""10-K / 10-Q item structure + basic text extraction from EDGAR filings."""
from __future__ import annotations

import re
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup

from ..cache import cached
from ..config import SEC_HEADERS
from .edgar import ticker_to_cik, list_filings, _accession_no_dashes

TIMEOUT = 25

# Canonical item structure returned by /filings/items/types/
ITEM_TYPES: dict[str, list[dict[str, str]]] = {
    "10-K": [
        {"name": "Item-1", "title": "Business", "description": "Overview of the company's business."},
        {"name": "Item-1A", "title": "Risk Factors", "description": "Material risks that could affect results."},
        {"name": "Item-1B", "title": "Unresolved Staff Comments", "description": "Outstanding SEC staff comments."},
        {"name": "Item-2", "title": "Properties", "description": "Material physical properties."},
        {"name": "Item-3", "title": "Legal Proceedings", "description": "Material pending legal proceedings."},
        {"name": "Item-4", "title": "Mine Safety Disclosures", "description": "Mine safety disclosures (if applicable)."},
        {"name": "Item-5", "title": "Market for Registrant's Common Equity", "description": "Market info and dividends."},
        {"name": "Item-6", "title": "Selected Financial Data", "description": "Selected historical financial data."},
        {"name": "Item-7", "title": "MD&A", "description": "Management's discussion and analysis of financial condition and results."},
        {"name": "Item-7A", "title": "Quantitative and Qualitative Disclosures About Market Risk", "description": "Market risk disclosures."},
        {"name": "Item-8", "title": "Financial Statements", "description": "Audited financial statements and supplementary data."},
        {"name": "Item-9", "title": "Changes in and Disagreements with Accountants", "description": "Accountant change disclosures."},
        {"name": "Item-9A", "title": "Controls and Procedures", "description": "Disclosure controls and ICFR."},
        {"name": "Item-10", "title": "Directors, Executive Officers and Corporate Governance", "description": "Governance disclosures."},
        {"name": "Item-11", "title": "Executive Compensation", "description": "Executive compensation disclosures."},
        {"name": "Item-12", "title": "Security Ownership of Certain Beneficial Owners", "description": "Beneficial ownership."},
        {"name": "Item-13", "title": "Certain Relationships and Related Transactions", "description": "Related-party transactions."},
        {"name": "Item-14", "title": "Principal Accountant Fees and Services", "description": "Auditor fees."},
        {"name": "Item-15", "title": "Exhibits and Financial Statement Schedules", "description": "Exhibits list."},
    ],
    "10-Q": [
        {"name": "Part-1,Item-1", "title": "Financial Statements", "description": "Unaudited financial statements."},
        {"name": "Part-1,Item-2", "title": "MD&A", "description": "Management's discussion and analysis."},
        {"name": "Part-1,Item-3", "title": "Quantitative and Qualitative Disclosures About Market Risk", "description": "Market risk disclosures."},
        {"name": "Part-1,Item-4", "title": "Controls and Procedures", "description": "Disclosure controls and ICFR."},
        {"name": "Part-2,Item-1", "title": "Legal Proceedings", "description": "Legal proceedings."},
        {"name": "Part-2,Item-1A", "title": "Risk Factors", "description": "Updated risk factors."},
        {"name": "Part-2,Item-2", "title": "Unregistered Sales of Equity Securities", "description": "Equity sales and buybacks."},
        {"name": "Part-2,Item-3", "title": "Defaults Upon Senior Securities", "description": "Defaults disclosures."},
        {"name": "Part-2,Item-4", "title": "Mine Safety Disclosures", "description": "Mine safety disclosures."},
        {"name": "Part-2,Item-5", "title": "Other Information", "description": "Other material information."},
        {"name": "Part-2,Item-6", "title": "Exhibits", "description": "Exhibit index."},
    ],
}


# ---- Helpers ---------------------------------------------------------------

def _find_filing_by_accession(cik: str, accession: str) -> Optional[dict[str, Any]]:
    from .edgar import get_submissions

    sub = get_submissions(cik)
    if sub.get("_error"):
        return None
    recent = (sub.get("filings") or {}).get("recent") or {}
    accs = recent.get("accessionNumber") or []
    for i, a in enumerate(accs):
        if a == accession:
            return {
                "form": (recent.get("form") or [])[i] if i < len(recent.get("form", [])) else None,
                "primaryDocument": (recent.get("primaryDocument") or [])[i] if i < len(recent.get("primaryDocument", [])) else None,
                "filingDate": (recent.get("filingDate") or [])[i] if i < len(recent.get("filingDate", [])) else None,
                "reportDate": (recent.get("reportDate") or [])[i] if i < len(recent.get("reportDate", [])) else None,
            }
    return None


@cached("sec_doc_text", ttl=86400)
def fetch_filing_text(cik: str, accession: str, primary_doc: str) -> str:
    acc_nodash = _accession_no_dashes(accession)
    cik_int = str(int(cik))
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{primary_doc}"
    try:
        r = requests.get(url, headers=SEC_HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        # drop tables for readability? keep for now but strip scripts/styles
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text("\n")
        # collapse whitespace
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()
    except Exception as e:
        return f"[error fetching filing: {e}]"


# ---- Item extraction -------------------------------------------------------

def _item_patterns(item_name: str) -> list[re.Pattern]:
    """Build regex patterns to locate start of an item heading in filing text."""
    # e.g. "Item-1A" -> "Item 1A" / "ITEM 1A."
    clean = item_name.replace("Part-1,", "").replace("Part-2,", "")
    clean = clean.replace("Item-", "")
    # allow optional period and dot
    esc = re.escape(clean)
    return [
        re.compile(rf"(?im)^\s*Item\s+{esc}\b[.\s:]", re.MULTILINE),
        re.compile(rf"(?im)\bItem\s+{esc}\b[.\s:]"),
    ]


def _next_item_marker(text: str, start: int) -> int:
    """Find the next Item heading after `start`."""
    m = re.search(r"(?im)^\s*Item\s+\d+[A-Z]?\b", text[start:])
    if not m:
        return len(text)
    return start + m.start()


def extract_items(
    ticker: str,
    accession_number: str,
    items: list[str],
) -> list[dict[str, Any]]:
    cik = ticker_to_cik(ticker)
    if not cik:
        return [{"name": it, "content": "", "error": "unknown ticker"} for it in items]

    meta = _find_filing_by_accession(cik, accession_number)
    if not meta or not meta.get("primaryDocument"):
        return [{"name": it, "content": "", "error": "filing not found"} for it in items]

    text = fetch_filing_text(cik, accession_number, meta["primaryDocument"])
    if not text or text.startswith("[error"):
        return [{"name": it, "content": "", "error": text} for it in items]

    results: list[dict[str, Any]] = []
    for name in items:
        content = ""
        for pat in _item_patterns(name):
            m = pat.search(text)
            if m:
                start = m.end()
                end = _next_item_marker(text, start)
                content = text[start:end].strip()
                # cap to reasonable size
                if len(content) > 200_000:
                    content = content[:200_000] + "\n...[truncated]"
                break
        results.append({"name": name, "content": content})
    return results
