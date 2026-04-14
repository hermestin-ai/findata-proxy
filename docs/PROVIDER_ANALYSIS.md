# Data Provider Analysis for Fundamental Value Investing Research

This document analyzes alternatives to the Financial Datasets API (~$200/mo) that Dexter uses by default, focused on fundamental value-investing research use cases (Buffett/Graham style: 10-K reading, DCF, multi-year fundamentals, insider activity, management quality signals).

## TL;DR

For a solo researcher doing fundamental value investing, **this proxy (SEC EDGAR + yfinance + CoinGecko)** covers ~85% of Dexter's needs at **$0/month**. The remaining 15% (segmented revenues, perfect historical key-ratio series, screener quality) can be solved by adding **FMP Basic ($19/mo)** or **EODHD ($19.99/mo)**, giving full coverage at ~10% of Financial Datasets' price.

## Coverage Summary (findata-proxy v0.1)

| Endpoint                          | Source         | Status | Value-investing utility |
|-----------------------------------|----------------|--------|-------------------------|
| `/prices/*`                       | yfinance       | ✅ Full | Delayed quotes fine for long-term investing |
| `/financials/income-statements`   | yfinance       | ✅ Full | 4 years annual + 4 quarters; field names map ~90% |
| `/financials/balance-sheets`      | yfinance       | ✅ Full | Same |
| `/financials/cash-flow-statements`| yfinance       | ✅ Full | FCF computable |
| `/financials/` (combined)         | yfinance       | ✅ Full | |
| `/financial-metrics/snapshot`     | yfinance.info  | ✅ Full | P/E, P/B, ROE, ROA, margins, EV/EBITDA |
| `/financial-metrics/` historical  | derived        | 🟡 Partial | Only snapshot repeated — no real time series |
| `/filings/`                       | SEC EDGAR      | ✅ Full | 10-K, 10-Q, 8-K metadata, accession #s, URLs |
| `/filings/items/`                 | SEC EDGAR      | 🟡 Partial | Text extraction works for most 10-Ks; regex-based, not XBRL |
| `/insider-trades/`                | SEC EDGAR      | 🟡 Partial | Form 4 metadata only; per-transaction shares/price need XML parsing |
| `/earnings`                       | yfinance       | ✅ Full | Surprise calc partial |
| `/news`                           | yfinance       | ✅ Full | Yahoo Finance aggregated |
| `/analyst-estimates/`             | yfinance       | ✅ Full | Consensus EPS, revenue, analyst count |
| `/financials/segmented-revenues/` | — (none)       | 🔴 Gap | Requires XBRL footnote parsing; known limitation |
| `/financials/search/screener/`    | yfinance (slow)| 🟡 Partial | Works on S&P 500 top 100; not the full market |
| `/crypto/*`                       | CoinGecko      | ✅ Full | |

## Provider Landscape for Value Investing

### Free / Near-Free

| Provider         | Monthly $ | Fundamentals Depth | SEC Filings | Insider | Screener | Rate Limit |
|------------------|-----------|--------------------|-------------|---------|----------|------------|
| **SEC EDGAR**    | $0        | ✅ Full (XBRL)      | ✅ Source    | ✅ Form 4| ❌        | 10 req/s   |
| **yfinance**     | $0        | 🟡 4 years typical  | ❌          | ❌       | ❌        | unofficial |
| **Alpha Vantage**| $0 free   | 🟡 Limited history  | ❌          | ❌       | ❌        | 25/day free|
| **FMP**          | $0 free   | 🟡 5 yr, US only    | 🟡 partial  | ✅ paid  | 🟡        | 250/day    |
| **EODHD**        | $0 free   | 🟡 20 req/day free  | ❌          | ❌       | ✅ paid   | low        |

### Paid Value-Investing-Oriented

| Provider                 | $/month | Why a value investor might choose it |
|--------------------------|---------|--------------------------------------|
| **Financial Datasets**   | $200    | What Dexter defaults to. Convenient, but expensive. |
| **FMP Basic**            | $19     | 30+ years of fundamentals, insider trades, earnings estimates, SEC filings API, screener. Best $/value for fundamentals. |
| **EODHD All-in-One**     | $80     | Fundamentals + filings + screener + 100K+ tickers global. |
| **EODHD Basic**          | $20     | 20 yrs fundamentals, global coverage. |
| **Stockanalysis.com API**| $30     | 25 yrs of statements, value-investing tilt, excellent coverage. |
| **SimplyWall.st API**    | contact | Narrative + fundamentals; expensive. |
| **Polygon.io Starter**   | $29     | Prices + some fundamentals; more trading-focused. |
| **Intrinio**             | $200+   | Institutional; overkill for solo. |

## Recommendation Ladder

### Tier 0 — Solo researcher, learning the agent ($0/mo)
Use **findata-proxy** as-is. Accept:
- Only 4 years of fundamentals (yfinance limit)
- No segmented revenues
- Screener limited to S&P 500 top 100
- Insider trades = metadata only

This is genuinely enough for 80% of Dexter's value-investing workflow. You still get real 10-K text, real earnings data, real P/E and ROE, and real insider activity timing (just not dollar amounts without opening the XML).

### Tier 1 — Serious research, $19/mo
Add **FMP Basic** as a secondary provider for:
- 30+ years of historical fundamentals (critical for Buffett-style long-horizon analysis)
- Structured insider transaction data (shares + prices + values)
- Full historical key ratios series
- Working screener across the whole US market

**Implementation**: extend `findata-proxy` with `app/providers/fmp.py`, prefer FMP for endpoints where yfinance is weak, keep SEC EDGAR as the source-of-truth for filings.

### Tier 2 — Multi-strategy or global ($30–80/mo)
**EODHD All-in-One** ($80) or **Stockanalysis.com** ($30) if you need:
- Non-US markets (EODHD covers 100K+ tickers globally)
- 25+ year fundamentals backtest-grade data
- Production-grade reliability + SLA

### Tier 3 — Prefer "the original"
Pay Financial Datasets $200/mo only if:
- You specifically need segmented revenue breakdowns across thousands of companies
- You want turnkey schema compatibility and don't want to maintain an adapter layer
- Your time is worth >> $180/mo saved

## SEC EDGAR Deep-Dive (the sleeper giant)

SEC EDGAR is the **actual source** of what most commercial providers resell. For fundamentals investing it's:
- **Free, unlimited, authoritative.**
- Requires `User-Agent` header with contact email. That's it.
- `/submissions/CIK{cik}.json` — every filing ever made by a company
- `/api/xbrl/companyfacts/CIK{cik}.json` — EVERY reported line item across ALL filings (this is the gold mine)
- XBRL gives you the entire income statement / balance sheet / cash flow at line-item granularity, back to ~2009, including amendments and restatements

**Upgrade path for this proxy**: implement a `sec/xbrl.py` module that calls `companyfacts` and maps XBRL concepts (`us-gaap:Revenues`, `us-gaap:NetIncomeLoss`, etc.) to FD's field names. That single module would eliminate yfinance's 4-year historical limit and give us 15+ years of pristine SEC-sourced data for free. **This is the highest-leverage improvement on the roadmap.**

## Segmented Revenues — The Known Gap

Segment reporting (Apple: iPhone vs. Services vs. Mac...) lives in 10-K footnote text and XBRL segment dimensions. There's no free clean API. Options:
1. Parse XBRL segment axes (doable but complex — ~1 week of dev)
2. LLM-extract from 10-K filing items (Dexter can already do this via `read_filings`!) — cheaper and already in the toolkit
3. Subscribe to FMP or stockanalysis.com for a clean feed

The LLM-extraction path is actually elegant: when the agent needs segments, it calls `read_filings` on the latest 10-K's Note 12 (typically) and extracts structured data. No new endpoint needed.

## Recommendation for Your Use Case

Based on your stated goal (**building a financial researcher for fundamental value investing thesis**):

1. **Start with findata-proxy ($0)** — it's already built and working. Point Dexter at `http://localhost:8000` via `FINANCIAL_DATASETS_BASE_URL`.
2. **Next sprint (v0.2): add SEC XBRL companyfacts** for true 15-year fundamentals. This unlocks real Buffett-style analysis (margin trends, ROIC over two decades, FCF consistency) for free.
3. **If/when you hit limits**, add FMP Basic at $19/mo — that's a 90% cost reduction vs. Financial Datasets with near-parity coverage for value investing.
4. **Keep Financial Datasets as an option** in the proxy's provider fallback chain — if the user sets the real `FINANCIAL_DATASETS_API_KEY`, route through them for endpoints where ours lags. Best of both worlds.

## Cost Math

| Stack | Monthly | Annual |
|-------|---------|--------|
| Dexter default (FD only) | $200 | $2,400 |
| findata-proxy alone | $0 | $0 |
| findata-proxy + FMP Basic | $19 | $228 |
| findata-proxy + FMP + EODHD | $39 | $468 |

**Savings at Tier 1: $2,172/year** (~91% cheaper) with minimal coverage loss for value investing.
