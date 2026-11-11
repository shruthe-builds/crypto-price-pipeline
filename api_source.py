"""Browser-free data source using CoinGecko's public API (no API key needed).

Used as a fallback when the CoinMarketCap page cannot be loaded, or on its own
with `--source api`. Returns records in exactly the same shape as
`parsing.parse_table`, so the rest of the tool does not care where data came from.
"""
from __future__ import annotations

from typing import Optional

import requests

API_URL = "https://api.coingecko.com/api/v3/coins/markets"
HEADERS = {"Accept": "application/json", "User-Agent": "crypto-price-tracker/1.0"}


class ApiError(RuntimeError):
    """Raised when the API cannot be reached or returns unusable data."""


def normalise(items: list[dict], top_n: int) -> list[dict]:
    """Convert CoinGecko JSON into tracker records, dropping incomplete rows."""
    records: list[dict] = []
    for item in items:
        record = {
            "rank": item.get("market_cap_rank"),
            "name": item.get("name"),
            "symbol": (item.get("symbol") or "").upper(),
            "price_usd": item.get("current_price"),
            "change_1h_pct": item.get("price_change_percentage_1h_in_currency"),
            "change_24h_pct": item.get("price_change_percentage_24h_in_currency"),
            "change_7d_pct": item.get("price_change_percentage_7d_in_currency"),
            "market_cap_usd": item.get("market_cap"),
            "volume_24h_usd": item.get("total_volume"),
        }
        if any(v is None or v == "" for v in record.values()):
            continue
        records.append(record)
        if len(records) == top_n:
            break
    return records


def fetch_records(top_n: int, timeout: int = 20) -> list[dict]:
    """Fetch the top `top_n` coins by market cap."""
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": min(max(top_n + 5, 10), 250),  # small buffer for dropped rows
        "page": 1,
        "price_change_percentage": "1h,24h,7d",
    }
    try:
        response = requests.get(API_URL, params=params, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        items = response.json()
    except requests.RequestException as exc:
        raise ApiError(f"Could not reach the CoinGecko API: {exc}") from exc
    except ValueError as exc:
        raise ApiError("CoinGecko returned something that is not JSON.") from exc

    if not isinstance(items, list):
        raise ApiError(f"Unexpected API response: {str(items)[:200]}")
    return normalise(items, top_n)
