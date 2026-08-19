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
import json
import statistics
import tempfile
import time
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

from agent.config import RiskLimits
from agent.portfolio import Portfolio, Position
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
             lookback: int) -> tuple[list[Trade], list[dict]]:
    """Momentum rule: after a >=move_threshold move over `lookback` candles
    on >=vol_threshold volume, enter in the direction of the move.

    Entry pays a modeled 2c spread cost (we cross to take liquidity), which
    is deliberately pessimistic rather than assuming mid-price fills.
    """
    trades: list[Trade] = []
    candidates: list[dict] = []
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
        def side_price_of(c: Candle, sd=side) -> float:
            return c.close if sd == "yes" else (100.0 - c.close)

        cand = {
            "ts": candles[i].ts, "ticker": ticker, "side": side,
            "entry": entry, "move": move, "judgment": judgment,
            "market": market,
            "exit_1h": side_price_of(candles[i + 1]) if i + 1 < len(candles) else None,
            "exit_4h": side_price_of(candles[i + 4]) if i + 4 < len(candles) else None,
            "exit_end": side_price_of(candles[-1]),
        }
        candidates.append(cand)

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
    return trades, candidates


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


# The backtest keeps its ledger in a scratch file: replaying history must
# never overwrite the live position ledger.
_SCRATCH = Path(tempfile.gettempdir()) / "kalshi_backtest_positions.json"

MOVE_BUCKETS = ((0.0, 5.0), (5.0, 10.0), (10.0, 20.0), (20.0, 1e9))


def bucket_label(move: float) -> str:
    a = abs(move)
    for lo, hi in MOVE_BUCKETS:
        if lo <= a < hi:
            return f">={lo:.0f}c" if hi >= 1e9 else f"{lo:.0f}-{hi:.0f}c"
    return "?"


def report_by_bucket(trades: list["Trade"], horizon: str) -> list[dict]:
    """Win rate split by trigger size.

    The headline number hides the shape: the biggest triggers were the worst
    bucket. Reporting only the pooled win rate would let a 6% bucket sit
    inside a respectable-looking average.
    """
    buckets: dict[str, list[Trade]] = {}
    for t in trades:
        buckets.setdefault(bucket_label(t.trigger_move), []).append(t)
    out = []
    order = [f"{lo:.0f}-{hi:.0f}c" if hi < 1e9 else f">={lo:.0f}c"
             for lo, hi in MOVE_BUCKETS]
    for label in order:
        ts = buckets.get(label)
        if not ts:
            continue
        r = report(ts, horizon)
        r["bucket"] = label
        out.append(r)
    return out


def simulate_stateful(all_candidates: list[dict], limits: RiskLimits,
                      hold_hours: int = 4) -> list["Trade"]:
    """Replay every candidate in time order against ONE running portfolio.

    This is the difference the ledger makes. The stateless path evaluates each
    entry against a blank PortfolioState, so the duplicate-position,
    max_open_positions, daily-loss and total-capital caps can never reject
    anything -- exactly the condition the live loop was in before
    agent/portfolio.py existed. Here a position occupies a slot and consumes
    capital until it is closed `hold_hours` later, so the caps actually bind.
    """
    book = Portfolio()
    trades: list[Trade] = []
    rejections: dict[str, int] = {}
    open_until: dict[str, tuple[int, float]] = {}    # ticker -> (close_ts, exit px)

    for cand in sorted(all_candidates, key=lambda c: c["ts"]):
        now = cand["ts"]

        # close anything whose holding period elapsed, freeing slot + capital
        for tk, (close_ts, exit_px) in list(open_until.items()):
            if close_ts <= now:
                book.close_position(tk, exit_px, "backtest hold elapsed",
                                    path=_SCRATCH)
                del open_until[tk]

        decision = evaluate(cand["judgment"], cand["market"],
                            book.risk_state(), limits)
        if not decision["approved"]:
            key = decision["reason"].split("(")[0].strip()[:40]
            rejections[key] = rejections.get(key, 0) + 1
            continue

        t = Trade(ticker=cand["ticker"], entry_ts=now, entry_price=cand["entry"],
                  side=cand["side"], size=decision["size_contracts"],
                  size_usd=decision["size_usd"], trigger_move=cand["move"])
        t.exit_price_1h = cand["exit_1h"]
        t.exit_price_4h = cand["exit_4h"]
        t.exit_price_end = cand["exit_end"]
        trades.append(t)

        book.open_position(Position(
            ticker=cand["ticker"], side=cand["side"],
            size_contracts=decision["size_contracts"],
            entry_price_cents=cand["entry"], cost_usd=decision["size_usd"],
        ), path=_SCRATCH)
        exit_px = cand["exit_4h"] if cand["exit_4h"] is not None else cand["entry"]
        open_until[cand["ticker"]] = (now + hold_hours * 3600, exit_px)

    print()
    print("=== Risk-gate rejections with a REAL portfolio (stateful) ===")
    if not rejections:
        print("  none -- no cap ever bound")
    for reason, n in sorted(rejections.items(), key=lambda kv: -kv[1]):
        print(f"  {n:4d}  {reason}")
    return trades


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--move", type=float, default=5.0,
                    help="cents of move required to trigger entry")
    ap.add_argument("--vol", type=float, default=200.0,
                    help="contracts of volume required in window")
    ap.add_argument("--lookback", type=int, default=3, help="candles (hours)")
    ap.add_argument("--stateful", action="store_true",
                    help="replay entries chronologically against ONE running "
                         "portfolio so the four caps actually bind")
    ap.add_argument("--hold-hours", type=int, default=4,
                    help="how long a stateful position occupies a slot")
    ap.add_argument("--universe-from", metavar="SCAN_JSON",
                    help="read (series, ticker) pairs from a find_momentum "
                         "--out file instead of the hardcoded UNIVERSE. The "
                         "built-in list has gone stale -- most of its tickers "
                         "now return 0-2 candles, which is why the default "
                         "run produces a sample too small to read.")
    args = ap.parse_args()

    client = KalshiClient.from_env()
    limits = RiskLimits()

    print(f"Backtest: {args.days}d hourly candles | trigger >={args.move}c "
          f"over {args.lookback}h on >={args.vol} contracts")
    print(f"Risk: max_position=${limits.max_position_usd} "
          f"min_conf={limits.min_confidence} min_edge={limits.min_edge_cents}c "
          f"max_spread={limits.max_spread_cents}c\n")

    all_trades: list[Trade] = []
    all_candidates: list[dict] = []
    universe = UNIVERSE
    if args.universe_from:
        with open(args.universe_from, encoding="utf-8") as f:
            scan = json.load(f)
        seen, universe = set(), []
        for r in scan.get("results", []):
            pair = (r.get("series"), r.get("ticker"))
            if all(pair) and pair not in seen:
                seen.add(pair)
                universe.append(pair)
        print(f"universe: {len(universe)} tickers from {args.universe_from}")

    for series, ticker in universe:
        candles = fetch_candles(client, series, ticker, args.days)
        if len(candles) < args.lookback + 2:
            print(f"  {ticker:38s} insufficient history ({len(candles)} candles)")
            continue
        trades, cands = simulate(candles, ticker, limits, args.move, args.vol,
                                 args.lookback)
        rng = f"{min(c.close for c in candles):.0f}-{max(c.close for c in candles):.0f}c"
        print(f"  {ticker:38s} {len(candles):3d} candles  range {rng:10s} "
              f"-> {len(trades)} entries")
        all_trades.extend(trades)
        all_candidates.extend(cands)

    if args.stateful:
        stateless_n = len(all_trades)
        if _SCRATCH.exists():
            _SCRATCH.unlink()
        all_trades = simulate_stateful(all_candidates, limits, args.hold_hours)
        print(f"  stateless entries: {stateless_n}  ->  stateful entries: "
              f"{len(all_trades)}  "
              f"({stateless_n - len(all_trades)} blocked by portfolio caps)")

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

    print()
    print("Win rate by trigger-move bucket (4h horizon):")
    for r in report_by_bucket(all_trades, "4h"):
        print(f"  {r['bucket']:>8s}  n={r['trades']:3d}  win={r['win_rate']:6.1%}  "
              f"median=${r['median_pnl']:>7.3f}  total=${r['total_pnl']:>8.2f}")

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
