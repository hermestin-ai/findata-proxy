"""Environment/config loader."""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

PORT: int = int(os.getenv("PORT", "8000"))
SEC_USER_AGENT: str = os.getenv("SEC_USER_AGENT", "Claude Code hermestin1@gmail.com").strip('"').strip("'")
ALLOW_ORIGINS: list[str] = [o.strip() for o in os.getenv("ALLOW_ORIGINS", "*").split(",") if o.strip()]
CACHE_DIR: str = os.getenv("CACHE_DIR", ".cache")
CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))

SEC_HEADERS: dict[str, str] = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov",
}

SEC_DATA_HEADERS: dict[str, str] = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov",
}
