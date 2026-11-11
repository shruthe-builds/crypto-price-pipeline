import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsing import (  # noqa: E402
    LayoutError,
    apply_filters,
    build_record,
    detect_columns,
    parse_percent,
    parse_rank,
    parse_table,
    parse_usd,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_table.html")


@pytest.fixture
def html():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


def test_parse_usd():
    assert parse_usd("$64,511.32") == 64511.32
    assert parse_usd("$0.9993") == 0.9993
    assert parse_usd("$30,104,051,187\n466,000 BTC") == 30104051187
    assert parse_usd("0.12%") is None  # a % cell must not be read as money


def test_parse_percent_sign_comes_from_html():
    assert parse_percent("0.12%", '<span class="icon-Caret-down"></span>') == -0.12
    assert parse_percent("0.12%", '<span class="icon-Caret-up"></span>') == 0.12
    assert parse_percent("-2.5%") == -2.5
    assert parse_percent("0.00%", '<span class="icon-Caret-down">') == 0.0
    assert parse_percent("$5") is None


def test_parse_rank():
    assert parse_rank(" 7 ") == 7
    assert parse_rank("") is None


def test_detect_columns_uses_headers():
    headers = ["", "#", "Name", "Price", "1h %", "24h %", "7d %",
               "Market Cap", "Volume(24h)", "Circulating Supply", "Last 7 Days"]
    cols = detect_columns(headers)
    assert cols["change_24h"] == 5
    assert cols["market_cap"] == 7
    assert cols["volume_24h"] == 8  # 'Volume(24h)' must not be mistaken for 24h %


def test_detect_columns_missing_raises():
    with pytest.raises(LayoutError):
        detect_columns(["#", "Name", "Price"])


def test_parse_table_end_to_end(html):
    records = parse_table(html, top_n=10)
    assert [r["symbol"] for r in records] == ["BTC", "ETH", "USDT"]  # unranked index row skipped
    btc = records[0]
    assert btc["rank"] == 1
    assert btc["price_usd"] == 64511.32
    assert btc["change_1h_pct"] == -0.12
    assert btc["change_24h_pct"] == 1.25
    assert btc["change_7d_pct"] == -3.39
    assert btc["market_cap_usd"] == 1292971701751
    assert btc["volume_24h_usd"] == 30104051187  # volume, not market cap


def test_top_n_limits_rows(html):
    assert len(parse_table(html, top_n=2)) == 2


def test_misaligned_columns_are_rejected():
    columns = detect_columns(["", "#", "Name", "Price", "1h %", "24h %", "7d %",
                              "Market Cap", "Volume(24h)"])
    # price cell holds a percentage -> row must be dropped, not mislabelled
    texts = ["", "1", "Bitcoin\nBTC", "0.12%", "0.1%", "0.2%", "0.3%", "$1", "$2"]
    assert build_record(texts, [""] * len(texts), columns) is None


def test_no_table_raises():
    with pytest.raises(LayoutError):
        parse_table("<html><body>blocked</body></html>", 10)


def test_apply_filters(html):
    records = parse_table(html, 10)
    assert [r["symbol"] for r in apply_filters(records, min_price=100)] == ["BTC", "ETH"]
    assert [r["symbol"] for r in apply_filters(records, min_change_24h=1)] == ["BTC"]
    assert len(apply_filters(records)) == 3
