# Cryptocurrency Price Tracker

A Python tool that collects the top cryptocurrencies from the public [CoinGecko API](https://www.coingecko.com/en/api) (no browser, no API key), cleans the values into proper numbers, and appends each snapshot to a CSV so you can build a price history and chart it. It can optionally scrape [CoinMarketCap](https://coinmarketcap.com/) with Selenium instead.

## Features
- **Works without a browser:** the default source is the CoinGecko API. Optional Selenium scraping of CoinMarketCap, with `--source auto` falling back to the API if the site is blocked or Chrome fails
- Collects rank, name, symbol, price, 1h / 24h / 7d change, market cap and 24h volume
- Reads column positions from the table **headers** instead of hard-coded indexes
- Recovers the **sign** of price changes (CoinMarketCap shows up/down as an icon, not text)
- Skips non-coin rows (e.g. index products with no rank) and rejects malformed rows instead of saving wrong data
- Stores real numbers (not strings like `"$64,511.32"`), timestamps in UTC
- Optional filters: minimum price, minimum 24h change
- Run once or on a schedule (`--runs` / `--interval`)
- `plot_history.py` charts the collected history
- Parsing logic is unit-tested against saved HTML (no browser or internet needed)

## Tech stack
Python 3.9+ · Selenium (headless Chrome) · BeautifulSoup4 · requests · pandas · matplotlib · pytest · GitHub Actions

## Setup
The default source needs no browser. Google Chrome is only needed for `--source browser` / `auto` (Selenium downloads the matching driver automatically).

```bash
git clone https://github.com/<shruthe-build>/crypto-price-tracker.git
cd crypto-price-tracker
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage
```bash
# one snapshot of the top 10 coins -> data/crypto_prices.csv
python tracker.py

# top 20, only coins above $1 that rose at least 2% in 24h
python tracker.py --top 20 --min-price 1 --min-change 2

# collect a snapshot every 5 minutes, 12 times (use --runs 0 to run until Ctrl+C)
python tracker.py --runs 12 --interval 300

# optional: scrape CoinMarketCap in Chrome instead of using the API
python tracker.py --source browser --show-browser
python tracker.py --source auto       # browser first, API fallback

# chart price history (needs at least 2 snapshots)
python plot_history.py --symbols BTC ETH --normalize --output price_history.png
```

## Output format (`data/crypto_prices.csv`)
| column | meaning |
|---|---|
| timestamp_utc | when the snapshot was taken |
| rank | CoinMarketCap rank |
| name, symbol | coin identity |
| price_usd | price in USD |
| change_1h_pct, change_24h_pct, change_7d_pct | % change (negative = down) |
| market_cap_usd | market capitalisation in USD |
| volume_24h_usd | 24h trading volume in USD |

## Troubleshooting
| Problem | Fix |
|---|---|
| `Could not start Chrome` | Install Google Chrome; check that a VPN/firewall/proxy isn't blocking Selenium's driver download. Or run with `--source api`. |
| Page opens but stays blank / bot-check page | CoinMarketCap blocks some automated browsers. Try `--show-browser`, or use `--source api`. |
| `ERR_CONNECTION_TIMED_OUT` in browser mode | CoinMarketCap is unreachable from your network. Use the default API source. |
| `Falling back to the CoinGecko API` | Expected in `auto` mode when the browser path fails; data is saved in the same format. |
| CoinGecko `429` / rate-limit error | Free API is rate limited; increase `--interval` (60+ seconds). |

## Tests
```bash
pytest -q
```
Tests use a small synthetic HTML fixture that mimics the table structure (`tests/fixtures/`) and sample API JSON, so no browser or internet is needed.

## Project structure
```
tracker.py          CLI + Selenium scraping + API fallback + CSV saving
parsing.py          pure HTML parsing/cleaning/filtering logic (unit-tested)
api_source.py       browser-free CoinGecko data source (unit-tested)
plot_history.py     price-history charts from the CSV
tests/              pytest suite + HTML fixture
.github/workflows/  CI that runs the tests on every push
```

## Limitations
- **Scraping is fragile.** If CoinMarketCap changes its page layout or blocks automated browsers, the browser path can fail. The tool fails loudly (a clear error, no bad rows saved) and, in `auto` mode, falls back to the API.
- The CoinGecko free tier has rate limits and its figures can differ slightly from CoinMarketCap's (different data providers).
- Respect the site's terms of use and don't scrape aggressively; keep `--interval` reasonable. For anything serious, use the official [CoinMarketCap API](https://coinmarketcap.com/api/) instead.
- Intended for learning and personal analysis. Not financial advice.

## Ideas for extension
- Add the official CoinMarketCap API (needs a free key) as another source
- Store history in SQLite instead of CSV
- Price-alert notifications
- Streamlit dashboard on top of the CSV

## License
MIT
