"""CoinGecko free public API wrappers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import requests

from ..cache import cached

BASE = "https://api.coingecko.com/api/v3"
TIMEOUT = 15


# Common ticker (BTC-USD) → coingecko id. Fallback uses /search.
_TICKER_TO_ID: dict[str, str] = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum",
    "SOL-USD": "solana",
    "ADA-USD": "cardano",
    "BNB-USD": "binancecoin",
    "XRP-USD": "ripple",
    "DOGE-USD": "dogecoin",
    "AVAX-USD": "avalanche-2",
    "DOT-USD": "polkadot",
    "MATIC-USD": "matic-network",
    "LINK-USD": "chainlink",
    "LTC-USD": "litecoin",
    "TRX-USD": "tron",
    "SHIB-USD": "shiba-inu",
    "ATOM-USD": "cosmos",
    "UNI-USD": "uniswap",
    "XLM-USD": "stellar",
    "NEAR-USD": "near",
    "BCH-USD": "bitcoin-cash",
    "APT-USD": "aptos",
}


def _normalize(ticker: str) -> str:
    t = (ticker or "").upper().strip()
    if "-" not in t:
        t = f"{t}-USD"
    return t


@cached("cg_id", ttl=86400)
def ticker_to_id(ticker: str) -> Optional[str]:
    t = _normalize(ticker)
    if t in _TICKER_TO_ID:
        return _TICKER_TO_ID[t]
    sym = t.split("-")[0].lower()
    try:
        r = requests.get(f"{BASE}/search", params={"query": sym}, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        for c in data.get("coins", []):
            if (c.get("symbol") or "").lower() == sym:
                return c.get("id")
        coins = data.get("coins") or []
        if coins:
            return coins[0].get("id")
    except Exception:
        return None
    return None


@cached("cg_snapshot", ttl=60)
def price_snapshot(ticker: str) -> dict[str, Any]:
    cg_id = ticker_to_id(ticker)
    if not cg_id:
        return {"ticker": _normalize(ticker), "error": "Unknown crypto ticker"}
    try:
        r = requests.get(
            f"{BASE}/simple/price",
            params={
                "ids": cg_id,
                "vs_currencies": "usd",
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json().get(cg_id, {})
        return {
            "ticker": _normalize(ticker),
            "price": data.get("usd"),
            "day_change_percent": data.get("usd_24h_change"),
            "market_cap": data.get("usd_market_cap"),
            "volume": data.get("usd_24h_vol"),
            "time": datetime.fromtimestamp(data.get("last_updated_at", 0), tz=timezone.utc).isoformat() if data.get("last_updated_at") else datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"ticker": _normalize(ticker), "error": str(e)}


@cached("cg_ohlc", ttl=300)
def historical_prices(
    ticker: str,
    interval: str = "day",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict[str, Any]]:
    cg_id = ticker_to_id(ticker)
    if not cg_id:
        return []
    # compute days window
    days = 30
    try:
        if start_date and end_date:
            s = datetime.fromisoformat(start_date)
            e = datetime.fromisoformat(end_date)
            days = max(1, (e - s).days or 1)
        elif start_date:
            s = datetime.fromisoformat(start_date)
            days = max(1, (datetime.utcnow() - s).days or 1)
    except Exception:
        pass
    # CoinGecko /ohlc accepts: 1, 7, 14, 30, 90, 180, 365, max
    allowed = [1, 7, 14, 30, 90, 180, 365]
    chosen = next((a for a in allowed if a >= days), 365)
    try:
        r = requests.get(
            f"{BASE}/coins/{cg_id}/ohlc",
            params={"vs_currency": "usd", "days": chosen},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        rows: list[dict[str, Any]] = []
        for item in r.json():
            ts_ms, o, h, lo, c = item
            ts = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).isoformat()
            rows.append({
                "ticker": _normalize(ticker),
                "open": o,
                "high": h,
                "low": lo,
                "close": c,
                "volume": None,
                "time": ts,
            })
        return rows
    except Exception:
        return []


@cached("cg_tickers", ttl=3600)
def top_tickers(limit: int = 50) -> list[str]:
    try:
        r = requests.get(
            f"{BASE}/coins/markets",
            params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": limit, "page": 1},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        out: list[str] = []
        for c in r.json():
            sym = (c.get("symbol") or "").upper()
            if sym:
                out.append(f"{sym}-USD")
        return out
    except Exception:
        # fallback
        return list(_TICKER_TO_ID.keys())
