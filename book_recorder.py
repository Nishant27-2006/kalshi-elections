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

from momentum_filter import _ask_cents, _bid_cents

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


def snapshot_from_market(market: dict, ts: int) -> dict | None:
    """One row of the recording, or None if the book carries no quote.

    Reads ONLY the `_dollars` and `_fp` forms: the plain `yes_bid`,
    `yes_ask`, `open_interest` and `volume_24h` keys DO NOT EXIST on this
    payload and reading them returns None or 0 silently.
    """
    bid = _bid_cents(market)
    ask = _ask_cents(market)
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
