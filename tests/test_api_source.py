import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_source import normalise  # noqa: E402

SAMPLE = [
    {"market_cap_rank": 1, "name": "Bitcoin", "symbol": "btc", "current_price": 64511.32,
     "price_change_percentage_1h_in_currency": -0.12,
     "price_change_percentage_24h_in_currency": 1.25,
     "price_change_percentage_7d_in_currency": -3.39,
     "market_cap": 1292971701751, "total_volume": 30104051187},
    # incomplete row (missing 7d change) must be dropped, not saved half-empty
    {"market_cap_rank": 2, "name": "Ethereum", "symbol": "eth", "current_price": 1675.2,
     "price_change_percentage_1h_in_currency": 0.01,
     "price_change_percentage_24h_in_currency": -0.4,
     "price_change_percentage_7d_in_currency": None,
     "market_cap": 202170559708, "total_volume": 12000000000},
    {"market_cap_rank": 3, "name": "Tether", "symbol": "usdt", "current_price": 0.9993,
     "price_change_percentage_1h_in_currency": 0.0,
     "price_change_percentage_24h_in_currency": 0.0,
     "price_change_percentage_7d_in_currency": -0.01,
     "market_cap": 186446943386, "total_volume": 90000000000},
]


def test_normalise_shape_and_symbols_uppercased():
    records = normalise(SAMPLE, top_n=10)
    assert [r["symbol"] for r in records] == ["BTC", "USDT"]
    assert records[0]["change_1h_pct"] == -0.12
    assert set(records[0]) == {
        "rank", "name", "symbol", "price_usd", "change_1h_pct", "change_24h_pct",
        "change_7d_pct", "market_cap_usd", "volume_24h_usd",
    }


def test_normalise_respects_top_n():
    assert len(normalise(SAMPLE, top_n=1)) == 1
