# findata-proxy

[![python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org/)
[![fastapi](https://img.shields.io/badge/fastapi-0.110+-009688)](https://fastapi.tiangolo.com/)
[![license](https://img.shields.io/badge/license-MIT-green)](#license)

A drop-in, free replacement for [api.financialdatasets.ai](https://api.financialdatasets.ai).
findata-proxy is a FastAPI server that mirrors the Financial Datasets API surface using
**free** data sources: `yfinance`, SEC EDGAR, and CoinGecko.

## Why

The [Dexter](https://github.com/) financial research agent (and many others) depend
on api.financialdatasets.ai, which runs ~$200/month for moderate usage. findata-proxy
replicates the same request/response shapes using free data so you can point your
agent's `BASE_URL` at `http://localhost:8000` and keep working — for $0.

It will never be a perfect byte-for-byte replica: free data has gaps (see the coverage
table below). But it gets you 80-90% of the way there for research and backtesting.

## Data source: SEC XBRL companyfacts

For US-listed companies, `/financials/*` is backed by **SEC EDGAR XBRL companyfacts**
(`https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`). This is the same
primary source that every commercial data vendor resells. It gives you:

- **15+ years** of annual statements per ticker (no yfinance 4-year ceiling)
- Clean quarterly data, TTM aggregation, proper period alignment
- Authoritative values pulled directly from 10-K/10-Q XBRL filings

When a ticker is not available in XBRL (foreign private issuers without US filings,
deregistered companies, or temporary SEC outages) the server automatically falls
back to yfinance. You can force `?source=yfinance` on any `/financials/*` endpoint
for debugging. The response includes a `_source` field so you know where the data
came from.

Field coverage in XBRL mode: see `app/sec/concept_map.py` — each FD field maps
to an ordered list of XBRL candidate concepts so different issuers' reporting
styles are handled (e.g. `RevenueFromContractWithCustomerExcludingAssessedTax`
vs `Revenues` vs `SalesRevenueNet`).

## Coverage

| Endpoint                                   | Source       | Status |
| ------------------------------------------ | ------------ | ------ |
| `/prices/snapshot/`                        | yfinance     | OK     full |
| `/prices/` (historical)                    | yfinance     | OK     full |
| `/prices/snapshot/tickers/`                | static list  | OK     full (S&P 500 top 100) |
| `/financials/income-statements/`           | **SEC XBRL** → yfinance | **OK full** — 15+ yr history from SEC |
| `/financials/balance-sheets/`              | **SEC XBRL** → yfinance | **OK full** — 15+ yr history from SEC |
| `/financials/cash-flow-statements/`        | **SEC XBRL** → yfinance | **OK full** — 15+ yr history from SEC |
| `/financials/` (combined)                  | **SEC XBRL** → yfinance | **OK full** |
| `/financial-metrics/snapshot/`             | yfinance     | OK     full |
| `/financial-metrics/` (historical)         | yfinance     | PARTIAL — snapshot wrapped as 1-item list |
| `/filings/`                                | SEC EDGAR    | OK     full |
| `/filings/items/types/`                    | hardcoded    | OK     full |
| `/filings/items/`                          | SEC EDGAR    | PARTIAL — regex-based section extraction |
| `/insider-trades/`                         | SEC EDGAR    | PARTIAL — Form 4 metadata only, no txn detail |
| `/earnings`                                | yfinance     | OK     full |
| `/news`                                    | yfinance     | OK     full |
| `/analyst-estimates/`                      | yfinance     | PARTIAL |
| `/financials/segmented-revenues/`          | n/a          | STUB (known gap — requires XBRL footnote parsing) |
| `/financials/search/screener/filters/`     | hardcoded    | OK     full |
| `/financials/search/screener/` (POST)      | yfinance     | PARTIAL — iterates SP500_TOP_100, slow |
| `/crypto/prices/snapshot/`                 | CoinGecko    | OK     full |
| `/crypto/prices/`                          | CoinGecko    | OK     full |
| `/crypto/prices/tickers/`                  | CoinGecko    | OK     full |

Legend: OK = fully implemented, PARTIAL = works but with caveats, STUB = returns empty/placeholder.

## Quickstart

    pip install -r requirements.txt
    cp .env.example .env
    # Edit .env and set SEC_USER_AGENT to your name + email (required by SEC)
    uvicorn app.main:app --reload --port 8000

Then test:

    curl 'http://localhost:8000/'
    curl 'http://localhost:8000/prices/snapshot/?ticker=AAPL'
    curl 'http://localhost:8000/financials/income-statements/?ticker=AAPL&period=annual&limit=4'
    curl 'http://localhost:8000/filings/?ticker=AAPL&filing_type=10-K&limit=5'
    curl 'http://localhost:8000/crypto/prices/snapshot/?ticker=BTC-USD'

Interactive API docs: http://localhost:8000/docs

## Docker

    docker-compose up --build

Or:

    docker build -t findata-proxy .
    docker run -p 8000:8000 -e SEC_USER_AGENT="Your Name you@example.com" findata-proxy

## Using with Dexter

Dexter (TypeScript) calls Financial Datasets at a hardcoded base URL. To point it at
this proxy, either:

1. **Quick**: edit `dexter/src/tools/finance/api.ts` and set
   `BASE_URL = "http://localhost:8000"`.
2. **Better**: fork Dexter, read `process.env.FINDATA_BASE_URL` with a fallback to
   `api.financialdatasets.ai`, and submit a PR.

The proxy accepts any `x-api-key` header value (it's ignored). CORS is open by default
(`ALLOW_ORIGINS=*`) so Dexter running locally can hit it directly.

## Configuration (.env)

    PORT=8000
    SEC_USER_AGENT="Your Name you@example.com"   # REQUIRED by SEC EDGAR
    ALLOW_ORIGINS=*                              # CORS, comma-separated
    CACHE_DIR=.cache                             # diskcache location
    CACHE_TTL=3600                               # default TTL seconds

## Architecture

    app/
      main.py              FastAPI app, CORS, router mounting, health endpoint
      config.py            env loader
      cache.py             diskcache-backed @cached TTL decorator
      models.py            minimal Pydantic models
      universe.py          SP500 top-100 static ticker list
      providers/
        yf.py              yfinance wrappers (prices, statements, metrics, news, earnings)
        coingecko.py       CoinGecko wrappers (crypto prices)
      sec/
        edgar.py           ticker->CIK map, submissions/filings, Form 4 list
        items.py           10-K/10-Q item schema + regex text extraction
      routers/
        prices.py          /prices/*
        financials.py      /financials/*, /financial-metrics/*
        filings.py         /filings/*
        insider.py         /insider-trades/*
        earnings.py        /earnings
        news.py            /news
        estimates.py       /analyst-estimates/*
        screener.py        /financials/search/screener/*
        crypto.py          /crypto/prices/*
    tests/test_endpoints.py  offline smoke tests (no network required)

## Roadmap

- Parse Form 4 XML for full insider-transaction details (shares, price, txn code).
- Parse XBRL segment footnotes for `/financials/segmented-revenues/`.
- Back the screener with a pre-computed fundamentals snapshot (update nightly).
- Add more crypto ticker aliases; consider CoinCap as a fallback.
- Field-name fidelity: a config-driven mapping layer aligning yfinance line items
  with Financial Datasets' exact keys.
- Historical `/financial-metrics/` derived from quarterly statements + prices.
- Rate-limit friendliness: request throttling for SEC (10 req/s cap) and CoinGecko.

## Known Gaps

- Segmented revenues: not implemented.
- Insider transaction detail: not implemented (filing metadata only).
- Financial statement field names sometimes differ from Financial Datasets'
  canonical set; client code should treat missing fields as `null`.
- Screener is slow — it fetches yfinance info for each ticker in the universe.

## License

MIT. See LICENSE or the standard MIT text — this project is provided as-is with no
warranty. Please respect upstream data providers' terms of service:

- SEC EDGAR: set a valid User-Agent (name + email) and stay under 10 req/s.
- yfinance: unofficial API, may break; for personal use only.
- CoinGecko: free tier has rate limits; consider a Pro key for production.
