"""Cryptocurrency price tracker.

Fetches the top coins from the public CoinGecko API by default (no browser,
no API key). Optionally scrapes coinmarketcap.com with Selenium instead
(--source browser) or tries the browser first and falls back to the API
(--source auto). Values are cleaned into numbers and appended to a CSV so
price history builds up over time.
"""
from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from api_source import ApiError, fetch_records
from parsing import LayoutError, apply_filters, parse_table

# Selenium is only needed for --source browser / auto. The default API source
# works without it, so a missing install must not crash the program.
try:
    from selenium import webdriver
    from selenium.common.exceptions import (
        StaleElementReferenceException,
        TimeoutException,
        WebDriverException,
    )
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    SELENIUM_AVAILABLE = True
except ImportError:  # pragma: no cover
    SELENIUM_AVAILABLE = False
    webdriver = None

    class WebDriverException(Exception):
        """Placeholder so error handling still works without selenium."""

    class TimeoutException(WebDriverException):
        pass

    class StaleElementReferenceException(WebDriverException):
        pass

URL = "https://coinmarketcap.com/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
BLOCK_MARKERS = ("just a moment", "attention required", "access denied", "verify you are human")


class BrowserError(RuntimeError):
    """Chrome could not start or the page could not be loaded."""


def make_driver(headless: bool) -> "webdriver.Chrome":
    if not SELENIUM_AVAILABLE:
        raise BrowserError(
            "Selenium is not installed, so browser mode is unavailable. "
            "Run: pip install selenium   (or use the default API source)."
        )
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=en-US")
    # Sites often block the default headless user-agent / automation flags.
    options.add_argument(f"--user-agent={USER_AGENT}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # Don't wait for every ad/tracker to finish; the table is what matters.
    options.page_load_strategy = "eager"
    try:
        # Selenium >= 4.6 downloads a matching chromedriver automatically
        # (this step itself needs internet access to googlechromelabs / chrome-for-testing).
        driver = webdriver.Chrome(options=options)
    except WebDriverException as exc:
        raise BrowserError(
            "Could not start Chrome. Make sure Google Chrome is installed and that "
            "Selenium can download its driver (firewall/VPN/proxy can block this). "
            f"Details: {str(exc).splitlines()[0]}"
        ) from exc
    driver.set_page_load_timeout(60)
    return driver


def _dismiss_popups(driver: webdriver.Chrome) -> None:
    """Best-effort click on cookie banners that can cover the page."""
    for xpath in (
        "//button[contains(., 'Accept')]",
        "//button[contains(., 'Got it')]",
        "//button[contains(., 'I agree')]",
    ):
        try:
            for button in driver.find_elements(By.XPATH, xpath)[:1]:
                button.click()
                return
        except WebDriverException:
            continue


def fetch_html(driver: webdriver.Chrome, timeout: int = 45) -> str:
    """Load the page and wait until prices are actually rendered."""
    try:
        driver.get(URL)
    except TimeoutException:
        pass  # page may still be usable; the wait below decides
    except WebDriverException as exc:
        raise BrowserError(
            f"The browser could not open {URL} ({str(exc).splitlines()[0]}). "
            "Check proxy/VPN/firewall settings."
        ) from exc

    _dismiss_popups(driver)

    def prices_rendered(d) -> bool:
        try:
            # Rows are lazy-rendered; nudging the scroll makes them appear.
            d.execute_script("window.scrollTo(0, 400);")
            return "$" in d.find_element(By.CSS_SELECTOR, "table tbody").text
        except (StaleElementReferenceException, WebDriverException):
            return False

    try:
        WebDriverWait(driver, timeout).until(prices_rendered)
    except TimeoutException:
        title = (driver.title or "").lower()
        if any(marker in title for marker in BLOCK_MARKERS):
            raise BrowserError(
                f"CoinMarketCap served a bot-check page ('{driver.title}'). "
                "Try --show-browser, or use --source api."
            )
        raise
    return driver.page_source


def get_records(args: argparse.Namespace, driver: Optional[webdriver.Chrome]) -> list[dict]:
    if args.source == "api":
        return fetch_records(args.top)
    return parse_table(fetch_html(driver), args.top)


def save_records(records: list[dict], path: str) -> None:
    """Append records to the CSV (header written only for a new file)."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    df = pd.DataFrame(records)
    df.to_csv(path, mode="a", header=not os.path.exists(path), index=False)


def show_table(records: list[dict]) -> None:
    df = pd.DataFrame(records)[
        ["rank", "name", "symbol", "price_usd", "change_24h_pct", "market_cap_usd"]
    ]
    df["price_usd"] = df["price_usd"].map("${:,.4f}".format)
    df["change_24h_pct"] = df["change_24h_pct"].map("{:+.2f}%".format)
    df["market_cap_usd"] = df["market_cap_usd"].map("${:,.0f}".format)
    print("\n" + df.to_string(index=False) + "\n")


def run_once(driver: Optional[webdriver.Chrome], args: argparse.Namespace) -> Optional[webdriver.Chrome]:
    """One snapshot. Returns the driver (None if the browser had to be dropped)."""
    try:
        records = get_records(args, driver)
    except (BrowserError, TimeoutException, LayoutError, WebDriverException) as exc:
        if args.source != "auto":
            raise
        print(f"[WARN] Browser scrape failed ({type(exc).__name__}: {exc})")
        print("[INFO] Falling back to the CoinGecko API ...")
        records = fetch_records(args.top)

    if not records:
        print("[ERROR] No valid coin rows were returned. Page layout or API may have changed.")
        return driver

    changes = [
        r[k] for r in records for k in ("change_1h_pct", "change_24h_pct", "change_7d_pct")
    ]
    if args.source != "api" and len(records) >= 8 and all(c >= 0 for c in changes):
        print("[WARN] No negative changes found. If the market isn't rallying, "
              "sign detection may have broken - inspect the page HTML.")

    records = apply_filters(records, args.min_price, args.min_change)
    if not records:
        print("[INFO] No coins passed the filters.")
        return driver

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    records = [{"timestamp_utc": timestamp, **rec} for rec in records]

    show_table(records)
    save_records(records, args.output)
    print(f"[INFO] Saved {len(records)} rows to {args.output}")
    return driver


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Track top cryptocurrency prices.")
    p.add_argument("--top", type=int, default=10, help="number of coins to collect (default 10)")
    p.add_argument("--output", default="data/crypto_prices.csv", help="CSV file to append to")
    p.add_argument("--min-price", type=float, default=None, help="only keep coins priced >= this (USD)")
    p.add_argument("--min-change", type=float, default=None, help="only keep coins with 24h change >= this (%%)")
    p.add_argument("--source", choices=["api", "auto", "browser"], default="api",
                   help="api = CoinGecko API, no Chrome needed (default); "
                        "browser = scrape CoinMarketCap with Chrome; "
                        "auto = try the browser first, fall back to the API")
    p.add_argument("--show-browser", action="store_true", help="run Chrome with a visible window")
    p.add_argument("--runs", type=int, default=1, help="number of snapshots; 0 = run until Ctrl+C")
    p.add_argument("--interval", type=int, default=300, help="seconds between snapshots (default 300)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    driver: Optional[webdriver.Chrome] = None
    try:
        if args.source != "api":
            try:
                driver = make_driver(headless=not args.show_browser)
            except BrowserError as exc:
                if args.source == "browser":
                    raise SystemExit(f"[ERROR] {exc}")
                print(f"[WARN] {exc}\n[INFO] Continuing with the CoinGecko API instead.")
                args.source = "api"

        count = 0
        while True:
            count += 1
            try:
                run_once(driver, args)
            except (BrowserError, LayoutError, TimeoutException, ApiError) as exc:
                print(f"[ERROR] {type(exc).__name__}: {exc}")
            if args.runs and count >= args.runs:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")
    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    main()
