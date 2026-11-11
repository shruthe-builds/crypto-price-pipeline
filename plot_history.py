"""Plot collected price history from the tracker's CSV."""
from __future__ import annotations

import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def main() -> None:
    p = argparse.ArgumentParser(description="Plot price history from the tracker CSV.")
    p.add_argument("--input", default="data/crypto_prices.csv")
    p.add_argument("--symbols", nargs="+", default=["BTC"], help="e.g. BTC ETH SOL")
    p.add_argument("--normalize", action="store_true",
                   help="show %% change since first reading (use this to compare coins)")
    p.add_argument("--output", default="price_history.png")
    args = p.parse_args()

    df = pd.read_csv(args.input, parse_dates=["timestamp_utc"])
    df = df[df["symbol"].isin(args.symbols)]
    if df.empty:
        raise SystemExit(f"No rows found for {args.symbols}")

    fig, ax = plt.subplots(figsize=(10, 5))
    for symbol, group in df.groupby("symbol"):
        group = group.sort_values("timestamp_utc")
        y = group["price_usd"]
        if args.normalize:
            y = (y / y.iloc[0] - 1) * 100
        ax.plot(group["timestamp_utc"], y, marker="o", label=symbol)

    ax.set_ylabel("% change since first reading" if args.normalize else "Price (USD)")
    ax.set_xlabel("Time (UTC)")
    ax.set_title("Cryptocurrency price history")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(args.output, dpi=150)
    print(f"Saved chart to {args.output}")


if __name__ == "__main__":
    main()
