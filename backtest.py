"""
Backtest the momentum-entry + risk-gate layer on REAL Kalshi price history.

WHAT THIS TESTS (honestly):
  - the momentum detection rule (does a price/volume spike predict follow-through?)
  - the deterministic risk gate and position sizing (the same code live trading uses)
  - realistic entry pricing (pays the ask / crosses the spread, not the mid)

WHAT THIS DOES NOT TEST:
  - LLM judgment quality. Google News RSS only serves recent items, so there
    is no historical news archive to replay. Inventing past "LLM judgments"
    with hindsight would produce a flattering, meaningless curve. Instead the
    backtest substitutes an explicit MECHANICAL rule (momentum-following) and
    reports its results as-is. Treat this as a test of the plumbing and of the
    momentum premise -- not proof the full agent is profitable.

Usage:
    python backtest.py                     # default market set, 7d hourly
    python backtest.py --days 5 --move 8   # require an 8c move to enter
"""

from __future__ import annotations

import argparse
import statistics
import time
from dataclasses import dataclass

from dotenv import load_dotenv

from agent.config import RiskLimits
from agent.risk import PortfolioState, evaluate
from kalshi_client import KalshiClient

load_dotenv()

# Markets with genuine trading history observed during live scans.
UNIVERSE = [
    ("KXDROPOUTPRIMARY", "KXDROPOUTPRIMARY-26-MMIL2"),   # Max Miller dropout
    ("KXRETIREMM", "KXRETIREMM-26"),                      # McConnell resign
    ("KXSCRSENS", "KXSCRSENS-26-RNOR"),                   # SC Sen primary
    ("KXSCRSENS", "KXSCRSENS-26-RFRY"),
    ("KXCONGRESSTESTIFY", "KXCONGRESSTESTIFY-27JAN-AFAU"),  # Fauci testify
    ("KXMISENGOVCOMBO", "KXMISENGOVCOMBO-26NOV-DEMREP"),
    ("KXEDWARDSOUT", "KXEDWARDSOUT-26JUL-26NOV03"),
    ("KXCENSUREEDWARDS", "KXCENSUREEDWARDS-26NOV"),
    ("KXTNPRIMARY", "KXTNPRIMARY-05R26-AOGL"),
    ("KXTNPRIMARY", "KXTNPRIMARY-07D26-VDIX"),
    ("KXFLPRIMARY", "KXFLPRIMARY-24D26-SJON"),
    ("KXGOVMNNOMR", "KXGOVMNNOMR-26-MLIN"),
]


@dataclass
class Candle:
    ts: int
    close: float      # cents
    high: float
    low: float
    volume: float


@dataclass
class Trade:
    ticker: str
    entry_ts: int
    entry_price: float     # cents, what we actually paid
    side: str
    size: int
    size_usd: float
    trigger_move: float
    exit_price_1h: float | None = None
    exit_price_4h: float | None = None
    exit_price_end: float | None = None

    def pnl_usd(self, exit_price: float | None) -> float | None:
        if exit_price is None:
            return None
        # long the chosen side; price is in cents of that side
        return self.size * (exit_price - self.entry_price) / 100.0


def fetch_candles(client: KalshiClient, series: str, ticker: str,
                   days: int) -> list[Candle]:
    now = int(time.time())
    try:
        data = client.get_market_candlesticks(
            series_ticker=series, ticker=ticker,
            start_ts=now - days * 86400, end_ts=now, period_interval=60,
        )
    except Exception:
        return []
    out: list[Candle] = []
    for c in data.get("candlesticks", []):
        p = c.get("price") or {}
        if p.get("close_dollars") is None:
            continue
        out.append(Candle(
            ts=c.get("end_period_ts", 0),
            close=float(p["close_dollars"]) * 100,
            high=float(p.get("high_dollars") or p["close_dollars"]) * 100,
            low=float(p.get("low_dollars") or p["close_dollars"]) * 100,
            volume=float(c.get("volume_fp") or 0),
        ))
    return out


def simulate(candles: list[Candle], ticker: str, limits: RiskLimits,
             move_threshold: float, vol_threshold: float,
             lookback: int) -> list[Trade]:
    """Momentum rule: after a >=move_threshold move over `lookback` candles
    on >=vol_threshold volume, enter in the direction of the move.

    Entry pays a modeled 2c spread cost (we cross to take liquidity), which
    is deliberately pessimistic rather than assuming mid-price fills.
    """
    trades: list[Trade] = []
    for i in range(lookback, len(candles) - 1):
        window = candles[i - lookback:i + 1]
        move = window[-1].close - window[0].close
        vol = sum(c.volume for c in window)
        if abs(move) < move_threshold or vol < vol_threshold:
            continue

        side = "yes" if move > 0 else "no"
        mid = candles[i].close
        # price of the side we're buying, plus spread cost
        raw_entry = mid if side == "yes" else (100.0 - mid)
        entry = raw_entry + 2.0

        judgment = {
            "should_trade": True,
            "side": side,
            # mechanical proxy: assume half the observed move continues
            "fair_value_cents": (mid + move * 0.5) if side == "yes"
                                 else (100.0 - (mid + move * 0.5)),
            "confidence": min(0.95, 0.65 + abs(move) / 100.0),
        }
        market = {
            "ticker": ticker,
            "yes_bid_cents": mid - 1,
            "yes_ask_cents": mid + 1,
            "book_depth_contracts": max(vol, 1.0),
        }
        decision = evaluate(judgment, market, PortfolioState(), limits)
        if not decision["approved"]:
            continue

        t = Trade(ticker=ticker, entry_ts=candles[i].ts, entry_price=entry,
                  side=side, size=decision["size_contracts"],
                  size_usd=decision["size_usd"], trigger_move=move)

        def side_price(c: Candle) -> float:
            return c.close if side == "yes" else (100.0 - c.close)

        if i + 1 < len(candles):
            t.exit_price_1h = side_price(candles[i + 1])
        if i + 4 < len(candles):
            t.exit_price_4h = side_price(candles[i + 4])
        t.exit_price_end = side_price(candles[-1])
        trades.append(t)
    return trades


def report(all_trades: list[Trade], horizon: str) -> dict:
    getter = {"1h": lambda t: t.exit_price_1h,
              "4h": lambda t: t.exit_price_4h,
              "end": lambda t: t.exit_price_end}[horizon]
    pnls = [t.pnl_usd(getter(t)) for t in all_trades]
    pnls = [p for p in pnls if p is not None]
    if not pnls:
        return {"horizon": horizon, "trades": 0}
    wins = [p for p in pnls if p > 0]
    return {
        "horizon": horizon,
        "trades": len(pnls),
        "total_pnl": round(sum(pnls), 2),
        "avg_pnl": round(statistics.mean(pnls), 3),
        "median_pnl": round(statistics.median(pnls), 3),
        "win_rate": round(len(wins) / len(pnls), 3),
        "best": round(max(pnls), 2),
        "worst": round(min(pnls), 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--move", type=float, default=5.0,
                    help="cents of move required to trigger entry")
    ap.add_argument("--vol", type=float, default=200.0,
                    help="contracts of volume required in window")
    ap.add_argument("--lookback", type=int, default=3, help="candles (hours)")
    args = ap.parse_args()

    client = KalshiClient.from_env()
    limits = RiskLimits()

    print(f"Backtest: {args.days}d hourly candles | trigger >={args.move}c "
          f"over {args.lookback}h on >={args.vol} contracts")
    print(f"Risk: max_position=${limits.max_position_usd} "
          f"min_conf={limits.min_confidence} min_edge={limits.min_edge_cents}c "
          f"max_spread={limits.max_spread_cents}c\n")

    all_trades: list[Trade] = []
    for series, ticker in UNIVERSE:
        candles = fetch_candles(client, series, ticker, args.days)
        if len(candles) < args.lookback + 2:
            print(f"  {ticker:38s} insufficient history ({len(candles)} candles)")
            continue
        trades = simulate(candles, ticker, limits, args.move, args.vol, args.lookback)
        rng = f"{min(c.close for c in candles):.0f}-{max(c.close for c in candles):.0f}c"
        print(f"  {ticker:38s} {len(candles):3d} candles  range {rng:10s} "
              f"-> {len(trades)} entries")
        all_trades.extend(trades)

    print(f"\n=== {len(all_trades)} simulated entries ===")
    if not all_trades:
        print("No entries triggered. Loosen --move/--vol or extend --days.")
        return

    for horizon in ("1h", "4h", "end"):
        r = report(all_trades, horizon)
        if r.get("trades"):
            print(f"\nHorizon {r['horizon']:>3s}: n={r['trades']:3d}  "
                  f"total=${r['total_pnl']:>7.2f}  avg=${r['avg_pnl']:>6.3f}  "
                  f"median=${r['median_pnl']:>6.3f}  win_rate={r['win_rate']:.1%}  "
                  f"best=${r['best']}  worst=${r['worst']}")

    print("\nPer-ticker (end-of-series horizon):")
    by_ticker: dict[str, list[Trade]] = {}
    for t in all_trades:
        by_ticker.setdefault(t.ticker, []).append(t)
    for tk, ts in sorted(by_ticker.items()):
        r = report(ts, "end")
        if r.get("trades"):
            print(f"  {tk:38s} n={r['trades']:3d} total=${r['total_pnl']:>7.2f} "
                  f"win={r['win_rate']:.0%}")

    print("\nNOTE: mechanical momentum rule, not LLM judgment. Entry pays a "
          "modeled 2c spread cost. See module docstring for what this does "
          "and does not validate.")


if __name__ == "__main__":
    main()
