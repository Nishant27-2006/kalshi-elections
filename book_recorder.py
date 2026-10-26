"""Record order-book snapshots so the fast markets become backtestable.

Kalshi's candle history is thin and WORST where liquidity is best: measured
2026-08-19, KXALIENS (long-dated) has 555 hourly candles over 30 days while
KXBTCD (a daily ladder) has ZERO at every window. The markets with the most
tradeable flow leave the least history, so any backtest built only on
available candles is biased toward slow, thin, long-dated contracts.

The only fix is to start recording now. This script has no execution path and
places no orders.

    python book_recorder.py --series KXBTCD --series KXMLBGAME --interval 60
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from find_momentum import _all_open_markets
from kalshi_client import KalshiClient

SNAPSHOT_FIELDS: tuple[str, ...] = (
    "ts", "series", "ticker", "event_ticker",
    "yes_bid_c", "yes_ask_c", "spread_c", "oi", "v24",
)


def _fp(value) -> float:
    """A `_fp` string field as a float. These ship as STRINGS."""
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _dollars_to_cents(value) -> float | None:
    """A `_dollars` string field as CENTS, or None if unquoted."""
    if value is None:
        return None
    try:
        return float(value) * 100.0
    except (TypeError, ValueError):
        return None


def snapshot_from_market(market: dict, ts: int) -> dict | None:
    """One row of the recording, or None if the book carries no quote.

    Reads ONLY the `yes_bid_dollars` / `yes_ask_dollars` and `_fp` forms
    DIRECTLY -- not through momentum_filter's `_ask_cents` / `_bid_cents`,
    which check the plain `yes_bid` / `yes_ask` keys FIRST. Those plain keys
    do not exist on this payload today, but if they ever did and disagreed
    with the `_dollars` forms, going through the dual-shape helpers would let
    the plain keys win and could produce a negative spread that later raises
    an uncaught ValueError deep in ru_per_contract, aborting a whole replay.
    """
    bid = _dollars_to_cents(market.get("yes_bid_dollars"))
    ask = _dollars_to_cents(market.get("yes_ask_dollars"))
    if bid is None and ask is None:
        return None
    ticker = market.get("ticker") or ""
    return {
        "ts": ts,
        "series": ticker.split("-", 1)[0],
        "ticker": ticker,
        "event_ticker": market.get("event_ticker") or "",
        "yes_bid_c": bid,
        "yes_ask_c": ask,
        "spread_c": (ask - bid) if (bid is not None and ask is not None) else None,
        "oi": _fp(market.get("open_interest_fp")),
        "v24": _fp(market.get("volume_24h_fp")),
    }


def append_snapshots(path: Path, snapshots: list[dict]) -> int:
    """Append rows as JSONL. Never rewrites, so a long recording is safe to
    interrupt at any moment."""
    if not snapshots:
        return 0
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for snap in snapshots:
            fh.write(json.dumps(snap) + "\n")
    return len(snapshots)


def record_once(client, series_list: list[str], path: Path, ts: int) -> int:
    """One sweep over the watchlist. Returns rows written.

    A series that errors is skipped and ANNOUNCED -- it must not abort the
    pass, or one dead ticker costs the whole recording window.
    """
    rows: list[dict] = []
    for series in series_list:
        try:
            markets = _all_open_markets(client, series)
        except Exception as exc:                      # noqa: BLE001
            print(f"  skip {series}: {type(exc).__name__}")
            continue
        for market in markets or []:
            snap = snapshot_from_market(market, ts)
            if snap is not None:
                rows.append(snap)
    return append_snapshots(path, rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--series", action="append", required=True,
                    help="series ticker to record; repeatable")
    ap.add_argument("--out", default="state/book_recording.jsonl")
    ap.add_argument("--interval", type=int, default=60,
                    help="seconds between sweeps")
    ap.add_argument("--sweeps", type=int, default=0,
                    help="number of sweeps; 0 means run until interrupted")
    args = ap.parse_args()

    client = KalshiClient.from_env()
    path = Path(args.out)
    swept = 0
    try:
        while args.sweeps == 0 or swept < args.sweeps:
            ts = int(time.time())
            n = record_once(client, args.series, path, ts)
            swept += 1
            print(f"[{ts}] sweep {swept}: {n} rows -> {path}")
            if args.sweeps and swept >= args.sweeps:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\nstopped after {swept} sweeps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
