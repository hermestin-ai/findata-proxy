"""Basic smoke tests — do not require network access."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["provider"] == "findata-proxy"


def test_filing_items_types():
    r = client.get("/filings/items/types/")
    assert r.status_code == 200
    data = r.json()
    assert "10-K" in data
    assert "10-Q" in data
    assert any(i["name"] == "Item-1A" for i in data["10-K"])


def test_screener_filters_schema():
    r = client.get("/financials/search/screener/filters/")
    assert r.status_code == 200
    data = r.json()
    fields = {f["field"] for f in data["filters"]}
    assert "market_cap" in fields
    assert "price_to_earnings_ratio" in fields


def test_prices_snapshot_tickers():
    r = client.get("/prices/snapshot/tickers/")
    assert r.status_code == 200
    tickers = r.json()["tickers"]
    assert "AAPL" in tickers
    assert len(tickers) >= 50


def test_segmented_revenues_stub():
    r = client.get("/financials/segmented-revenues/?ticker=AAPL")
    assert r.status_code == 200
    data = r.json()
    assert data["segmented_revenues"] == []
    assert "note" in data
