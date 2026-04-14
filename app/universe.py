"""Static reference data — top S&P 500 tickers by market cap (approximate snapshot)."""
from __future__ import annotations

# Approximate S&P 500 top ~100 by market cap. Used for /prices/snapshot/tickers/
# and screener universe. This is a static, lightweight list — not guaranteed current.
SP500_TOP_100: list[str] = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "BRK.B", "LLY", "AVGO",
    "TSLA", "JPM", "WMT", "V", "XOM", "UNH", "MA", "ORCL", "PG", "COST",
    "HD", "JNJ", "BAC", "NFLX", "ABBV", "CRM", "CVX", "KO", "MRK", "AMD",
    "PEP", "TMO", "ADBE", "LIN", "CSCO", "WFC", "ACN", "ABT", "MCD", "IBM",
    "GE", "NOW", "AXP", "DIS", "CAT", "MS", "PM", "QCOM", "TXN", "ISRG",
    "INTU", "GS", "T", "DHR", "VZ", "BKNG", "PFE", "SPGI", "CMCSA", "RTX",
    "UBER", "AMGN", "NEE", "LOW", "AMAT", "SYK", "HON", "TJX", "UNP", "ETN",
    "BLK", "PGR", "BSX", "SCHW", "COP", "ELV", "LMT", "VRTX", "C", "TMUS",
    "ANET", "ADP", "DE", "MDT", "KKR", "MU", "PLD", "GILD", "BMY", "CB",
    "REGN", "MMC", "ADI", "LRCX", "AMT", "KLAC", "FI", "SBUX", "MDLZ", "CI",
]
