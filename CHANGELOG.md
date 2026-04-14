# Changelog

All notable changes to findata-proxy.

## [0.2.0] — 2026-04-14

### Added
- **SEC XBRL companyfacts integration** (`app/sec/xbrl.py`, `app/sec/concept_map.py`)
  - `/financials/income-statements/`, `/financials/balance-sheets/`, `/financials/cash-flow-statements/`, `/financials/` now pull from SEC EDGAR XBRL first, with yfinance as automatic fallback
  - 15+ years of authoritative historical fundamentals for US-listed companies (up from yfinance's 4-year ceiling)
  - Multi-candidate concept mapping: each Financial Datasets field maps to an ordered list of us-gaap concepts, so reporting-style differences between filers are handled transparently
  - Proper TTM aggregation via rolling 4-quarter sum for income and cash flow statements
  - Quarterly row deduplication via period-duration filtering (10-Qs include YTD rows at the same end date as the quarter-only row)
  - Annual row filtering by ~365-day duration (rejects YTD partials that sometimes leak into 10-K filings)
  - Computed fields: `free_cash_flow = ocf - capex`, `total_debt = short + long`, `working_capital = current_assets - current_liabilities`
- `_source` field in `/financials/*` responses so callers can tell whether XBRL or yfinance served the data
- `?source=yfinance` query param to force yfinance path (useful for debugging)

### Changed
- `app/routers/financials.py` refactored: new `_fetch_with_fallback()` helper centralizes the XBRL→yfinance routing
- README gains a "Data source: SEC XBRL companyfacts" section explaining the new architecture
- Coverage table upgrades `/financials/*` rows from PARTIAL → OK full

### Known gaps (unchanged)
- `/financials/segmented-revenues/` still stubbed (needs XBRL segment-axis parsing)
- `/insider-trades/` still returns Form 4 metadata only (per-transaction shares/price requires Form 4 XML parsing)
- `/financial-metrics/` historical still repeats the snapshot (needs a proper ratio time series; Tier-1 FMP upgrade is the pragmatic path)

### Migration notes for 0.1 users
- No breaking changes to response shapes. Existing callers (Dexter included) continue to work unchanged.
- First request per ticker is slower (fetches ~1-5MB of companyfacts JSON from SEC). Subsequent requests for the same ticker hit the 6-hour diskcache.
- Set `SEC_USER_AGENT` in `.env` to something identifying you + your email; SEC requires it.

## [0.1.0] — 2026-04-14

### Added
- Initial release: FastAPI server mirroring `api.financialdatasets.ai`
- yfinance-backed `/prices/*`, `/financials/*`, `/financial-metrics/*`, `/earnings`, `/news`, `/analyst-estimates/*`
- SEC EDGAR-backed `/filings/*`, `/insider-trades/*` (metadata)
- CoinGecko-backed `/crypto/*`
- diskcache with per-endpoint TTLs
- Docker + docker-compose
- `docs/PROVIDER_ANALYSIS.md` — cost/coverage analysis of paid alternatives for value-investing research
