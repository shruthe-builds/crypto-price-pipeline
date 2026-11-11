"""Pure parsing helpers for the CoinMarketCap homepage table.

Nothing in here touches a browser or the network, so all of it can be
unit-tested against saved HTML (see tests/).
"""
from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

_NUMBER = r"(\d[\d,]*(?:\.\d+)?|\.\d+)"

# field name -> test applied to the normalised header text
# (lower-case, whitespace removed, e.g. "Market Cap" -> "marketcap")
_HEADER_RULES = {
    "rank": lambda h: h == "#",
    "name": lambda h: h == "name",
    "price": lambda h: h == "price",
    "change_1h": lambda h: h.startswith("1h"),
    "change_24h": lambda h: h.startswith("24h"),
    "change_7d": lambda h: h.startswith("7d"),
    "market_cap": lambda h: h.startswith("marketcap"),
    "volume_24h": lambda h: h.startswith("volume"),
}


class LayoutError(RuntimeError):
    """Raised when the page does not look like the table we expect."""


# ---------------------------------------------------------------- cell parsers
def parse_rank(text: str) -> Optional[int]:
    text = text.strip()
    return int(text) if text.isdigit() else None


def parse_usd(text: str) -> Optional[float]:
    """First dollar amount in the text, e.g. '$1,675.20' -> 1675.2.

    Volume cells contain a second line (coin amount); only the $ line counts.
    Returns None if there is no '$' amount, which makes column mix-ups
    (a % cell read as a price) fail loudly instead of silently.
    """
    for line in text.splitlines():
        match = re.search(r"\$\s*" + _NUMBER, line)
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def parse_percent(text: str, html: str = "") -> Optional[float]:
    """'0.12%' -> 0.12, with the sign recovered.

    CoinMarketCap draws the up/down arrow as an icon, so the visible text has
    no minus sign. The direction lives in the cell's HTML (a 'caret-down' /
    'caret-up' class), which is why the raw HTML is passed in as well.
    """
    if "%" not in text:
        return None
    match = re.search(_NUMBER, text)
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    if value == 0:
        return 0.0
    stripped = text.strip()
    negative = stripped.startswith(("-", "\u2212", "\u25bc")) or bool(
        re.search(r"caret-down|arrow-down|icon-down", html.lower())
    )
    return -value if negative else value


# --------------------------------------------------------------- table parsing
def detect_columns(headers: list[str]) -> dict[str, int]:
    """Map field names to column indexes using the table's header text."""
    columns: dict[str, int] = {}
    for index, header in enumerate(headers):
        normalised = re.sub(r"\s+", "", header).lower()
        for field, rule in _HEADER_RULES.items():
            if field not in columns and rule(normalised):
                columns[field] = index
                break
    missing = [f for f in _HEADER_RULES if f not in columns]
    if missing:
        raise LayoutError(f"Could not find columns {missing} in headers {headers}")
    return columns


def build_record(texts: list[str], htmls: list[str], columns: dict[str, int]) -> Optional[dict]:
    """Turn one table row into a clean record, or None if it isn't a real coin row."""
    if max(columns.values()) >= len(texts):
        return None

    rank = parse_rank(texts[columns["rank"]])
    if rank is None:  # e.g. the "CoinMarketCap 20 Index" row has no rank
        return None

    lines = [l.strip() for l in texts[columns["name"]].split("\n") if l.strip()]
    if not lines:
        return None

    def pct(field: str) -> Optional[float]:
        i = columns[field]
        return parse_percent(texts[i], htmls[i])

    record = {
        "rank": rank,
        "name": lines[0],
        "symbol": lines[1] if len(lines) > 1 else "",
        "price_usd": parse_usd(texts[columns["price"]]),
        "change_1h_pct": pct("change_1h"),
        "change_24h_pct": pct("change_24h"),
        "change_7d_pct": pct("change_7d"),
        "market_cap_usd": parse_usd(texts[columns["market_cap"]]),
        "volume_24h_usd": parse_usd(texts[columns["volume_24h"]]),
    }
    if any(value is None for value in record.values()):
        return None
    return record


def parse_table(html: str, top_n: int) -> list[dict]:
    """Extract the top `top_n` real coins from the page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    last_error: Optional[Exception] = None

    for table in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True) for th in table.select("thead th")]
        try:
            columns = detect_columns(headers)
        except LayoutError as exc:
            last_error = exc
            continue

        records: list[dict] = []
        for tr in table.select("tbody tr"):
            tds = tr.find_all("td")
            texts = [td.get_text("\n", strip=True) for td in tds]
            htmls = [str(td) for td in tds]
            record = build_record(texts, htmls, columns)
            if record:
                records.append(record)
            if len(records) == top_n:
                break
        return records

    raise LayoutError(str(last_error) if last_error else "No <table> found on the page")


def apply_filters(
    records: list[dict],
    min_price: Optional[float] = None,
    min_change_24h: Optional[float] = None,
) -> list[dict]:
    """Keep coins priced >= min_price and with 24h change >= min_change_24h."""
    kept = []
    for rec in records:
        if min_price is not None and rec["price_usd"] < min_price:
            continue
        if min_change_24h is not None and rec["change_24h_pct"] < min_change_24h:
            continue
        kept.append(rec)
    return kept
