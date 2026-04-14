"""FastAPI app entrypoint — findata-proxy."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .config import ALLOW_ORIGINS
from .routers import (
    crypto,
    earnings,
    estimates,
    filings,
    financials,
    insider,
    news,
    prices,
    screener,
)

logger = logging.getLogger("findata-proxy")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(
    title="findata-proxy",
    version=__version__,
    description="FastAPI proxy that mirrors api.financialdatasets.ai using free data sources "
    "(yfinance, SEC EDGAR, CoinGecko).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS if ALLOW_ORIGINS else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    return {"status": "ok", "provider": "findata-proxy", "version": __version__}


@app.get("/health")
def health2():
    return {"status": "ok", "provider": "findata-proxy", "version": __version__}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=200, content={"error": str(exc)})


# Routers
app.include_router(prices.router)
app.include_router(financials.router)
app.include_router(filings.router)
app.include_router(insider.router)
app.include_router(earnings.router)
app.include_router(news.router)
app.include_router(estimates.router)
app.include_router(screener.router)
app.include_router(crypto.router)


@app.on_event("startup")
async def _startup():
    # Warm the SEC ticker map lazily — ignore errors.
    try:
        from .sec.edgar import _load_ticker_map

        _load_ticker_map()
    except Exception:
        pass
    logger.info("findata-proxy v%s started", __version__)
