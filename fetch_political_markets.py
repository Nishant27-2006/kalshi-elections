"""
Discover and inspect political prediction markets on Kalshi.

Kalshi organizes markets as: series -> events -> markets.
A "series" is a recurring template (e.g. "which party wins MI-07"); an
"event" is one instance of it (e.g. the 2026 race); "markets" are the
tradeable contracts within it (e.g. Yes/No on each candidate).

This is read-only — no credentials required for these endpoints, though
being authenticated raises your rate limits.

Usage:
    python fetch_political_markets.py                    # list politics series
    python fetch_political_markets.py --series KXNJGOV    # events in a series
    python fetch_political_markets.py --event KXNJGOV-25  # markets in an event
    python fetch_political_markets.py --market <TICKER>   # one market + orderbook
    python fetch_political_markets.py --search "house"    # series whose title matches
"""

import argparse
import json

from dotenv import load_dotenv

from kalshi_client import KalshiClient

load_dotenv()


def list_politics_series(client: KalshiClient, search: str | None = None) -> None:
    """List series in the Politics category (elections, control of Congress,
    approval ratings, etc.) — this is the entry point for finding tickers
    for the races tracked in the vault (state presidential lines, Senate/Gov,
    and the battleground House districts like MI-07, NY-17, NJ-07, PA-08,
    CO-08)."""
    data = client.get_series_list(category="Politics")
    series = data.get("series", data if isinstance(data, list) else [])
    print(f"{len(series)} political series found.\n")
    for s in series:
        ticker = s.get("ticker", "?")
        title = s.get("title", "")
        if search and search.lower() not in title.lower() and search.lower() not in ticker.lower():
            continue
        print(f"  {ticker:20s} {title}")


def show_events(client: KalshiClient, series_ticker: str) -> None:
    data = client.get_events(series_ticker=series_ticker, status="open")
    events = data.get("events", [])
    print(f"{len(events)} open events in series {series_ticker}:\n")
    for e in events:
        print(f"  {e.get('event_ticker'):25s} {e.get('title')}")


def show_markets(client: KalshiClient, event_ticker: str) -> None:
    data = client.get_markets(event_ticker=event_ticker)
    markets = data.get("markets", [])
    print(f"{len(markets)} markets in event {event_ticker}:\n")
    for m in markets:
        yes_bid = m.get("yes_bid")
        yes_ask = m.get("yes_ask")
        print(f"  {m.get('ticker'):30s} {m.get('title', ''):45s} "
              f"yes_bid={yes_bid} yes_ask={yes_ask}")


def show_market_detail(client: KalshiClient, ticker: str) -> None:
    market = client.get_market(ticker)
    print(json.dumps(market, indent=2))
    print("\n-- Orderbook --")
    book = client.get_orderbook(ticker)
    print(json.dumps(book, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series", help="List open events in this series ticker")
    parser.add_argument("--event", help="List markets in this event ticker")
    parser.add_argument("--market", help="Show one market's detail + orderbook")
    parser.add_argument("--search", help="Filter the politics series list by title/ticker")
    args = parser.parse_args()

    client = KalshiClient.from_env()

    if args.market:
        show_market_detail(client, args.market)
    elif args.event:
        show_markets(client, args.event)
    elif args.series:
        show_events(client, args.series)
    else:
        list_politics_series(client, search=args.search)


if __name__ == "__main__":
    main()
