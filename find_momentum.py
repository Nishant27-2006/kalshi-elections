"""
Scan political markets for recent price momentum.

"Momentum" here = measurable price movement over a recent window, computed
from real candlestick data — not a prediction of what will happen, a
readout of what already is. Combines with the vault's political-knowledge
frameworks to explain WHY a mover is moving, where explainable.

Strategy (Kalshi's /markets endpoint has no volume-sort or category filter,
so we build a candidate list explicitly):
  1. Pull open markets from known high-salience series (chamber control,
     the vault's battleground-district watchlist, and a title-search sweep
     of the Elections category for "senate"/"governor"/"primary"/"control").
  2. For each open market with nonzero volume, pull 1-hour candles over the
     last N hours and 1-minute candles over the last hour.
  3. Flag movers by absolute price delta, weighted by volume (a big move on
     no volume is noise).

Usage:
    python find_momentum.py                 # scan the default candidate set
    python find_momentum.py --hours 24       # look back further for trend
    python find_momentum.py --min-volume 50  # require this much recent volume
"""

import argparse
import time

from dotenv import load_dotenv

from kalshi_client import KalshiClient
from watchlist import WATCHLIST

load_dotenv()


def discover_candidate_series(client: KalshiClient) -> list[str]:
    """Build a list of series tickers worth scanning: the watchlist's
    confirmed real tickers, plus a title sweep for other high-salience
    election series."""
    tickers = set()
    for info in WATCHLIST.values():
        s = info.get("series")
        if s and " / " not in s:  # skip the "A / B" dual-ticker placeholders
            tickers.add(s)

    # Broader sweep: pull the Elections category and keyword-filter titles
    # for the kind of races that carry real trading volume.
    data = client.get_series_list(category="Elections")
    all_series = data.get("series", [])
    keywords = ["senate", "governor", "control of", "primary", "president",
                "generic ballot", "midterm"]
    for s in all_series:
        title = s.get("title", "").lower()
        if any(k in title for k in keywords):
            tickers.add(s.get("ticker"))

    return sorted(t for t in tickers if t)


def scan_series(client: KalshiClient, series_ticker: str, hours_back: int,
                 min_volume: float) -> list[dict]:
    """Return momentum records for open markets in this series."""
    results = []
    try:
        markets_data = client.get_markets(series_ticker=series_ticker, status="open", limit=50)
    except Exception as e:
        return [{"series": series_ticker, "error": str(e)}]

    markets = markets_data.get("markets", [])
    now = int(time.time())
    start_ts = now - hours_back * 3600

    for m in markets:
        ticker = m.get("ticker")
        if not ticker:
            continue
        try:
            candles_data = client.get_market_candlesticks(
                series_ticker=series_ticker, ticker=ticker,
                start_ts=start_ts, end_ts=now, period_interval=60,
            )
        except Exception as e:
            results.append({"series": series_ticker, "ticker": ticker, "error": str(e)})
            continue

        candles = candles_data.get("candlesticks", [])
        priced = [c for c in candles if c.get("price", {}).get("close_dollars") is not None]
        if len(priced) < 2:
            continue

        first_price = float(priced[0]["price"]["close_dollars"])
        last_price = float(priced[-1]["price"]["close_dollars"])
        delta = last_price - first_price
        total_volume = sum(float(c.get("volume_fp") or 0) for c in candles)

        if total_volume < min_volume:
            continue

        # last-hour-specific delta (most recent candle vs the one before it)
        recent_delta = None
        if len(priced) >= 2:
            recent_delta = float(priced[-1]["price"]["close_dollars"]) - float(priced[-2]["price"]["close_dollars"])

        results.append({
            "series": series_ticker,
            "ticker": ticker,
            "title": m.get("title") or m.get("yes_sub_title") or "",
            "first_price": first_price,
            "last_price": last_price,
            "delta": delta,
            "recent_hour_delta": recent_delta,
            "volume": total_volume,
            "yes_bid": m.get("yes_bid"),
            "yes_ask": m.get("yes_ask"),
        })

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=12, help="Lookback window in hours")
    parser.add_argument("--min-volume", type=float, default=10.0, help="Minimum contracts traded in window")
    args = parser.parse_args()

    client = KalshiClient.from_env()

    print("Discovering candidate series...")
    series_list = discover_candidate_series(client)
    print(f"{len(series_list)} candidate series to scan.\n")

    all_results = []
    for st in series_list:
        recs = scan_series(client, st, args.hours, args.min_volume)
        for r in recs:
            if "error" not in r:
                all_results.append(r)

    all_results.sort(key=lambda r: abs(r.get("delta", 0)), reverse=True)

    print(f"=== Top movers, last {args.hours}h (min volume {args.min_volume}) ===\n")
    if not all_results:
        print("No markets cleared the volume threshold in this window.")
        print("Try --min-volume 0 to see everything, or --hours 48 for a longer look-back.")
        return

    for r in all_results[:25]:
        direction = "UP" if r["delta"] > 0 else "DOWN" if r["delta"] < 0 else "flat"
        print(f"{r['ticker']:22s} {direction:5s} {r['delta']:+.3f}  "
              f"({r['first_price']:.2f}->{r['last_price']:.2f})  "
              f"vol={r['volume']:.0f}  {r['title'][:50]}")


if __name__ == "__main__":
    main()
