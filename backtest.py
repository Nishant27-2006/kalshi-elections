"""Backtest a strategy against a recorded order book and report its Sharpe.

WHAT THIS IS HONEST ABOUT
-------------------------
Plan 1 ships no alpha model, so the headline strategy here is the NULL
strategy: enter every ticker, hold, exit. Its return is not a prediction --
it is the COST FLOOR. Any real signal has to clear the spread and both legs
of Kalshi's fee before it earns anything, and the null run measures exactly
how deep that hole is.

A momentum strategy is also implemented, because that is the hypothesis this
fund was originally proposed around, and it is testable on the same data:
enter only when the last `lookback` snapshots moved the price up by at least
`threshold` cents. Its parameters are fitted on a TRAIN slice and scored once
on a TEST slice that the fit never saw.

THREE THINGS THAT MAKE A BACKTEST LIE, AND WHAT IS DONE ABOUT EACH
------------------------------------------------------------------
1. Crossing the spread for free. Entries pay the ASK, exits receive the BID,
   and both legs pay `fee_per_contract`. A backtest that marks at the mid
   invents money that no order ever earned.

2. Pooling correlated trades. Fifty tickers entered in the same 15-second
   bucket are not fifty independent bets -- one market-wide move hits all of
   them. Returns are therefore averaged WITHIN each entry timestamp first,
   and the Sharpe is computed across those portfolio buckets. Pooling every
   trade as independent inflates the ratio by roughly sqrt(names).

3. Fitting and scoring on the same data. The parameter grid is searched on
   the train slice only, split by TIME (not by ticker, which would leak a
   ticker's later behaviour into its own training set), and the winner is
   scored once on the held-out tail. The Deflated Sharpe Ratio then charges
   for how many configurations were tried, because the best of 40 random
   strategies looks good by construction.

Spec sections 7.3 and 7.4.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from agent.risk_unit import (fee_per_contract, ru_per_contract, FEE_LEGS,
                             MIN_PRICE_DOLLARS)
from agent.void_rates import DEFAULT_VOID_RATE, vertical_for_series, void_rate_for_series

# A trade is skipped rather than priced when the book is this wide, because
# the exit assumption (lift the bid) stops being credible on a book nobody is
# quoting seriously.
MAX_TRADEABLE_SPREAD_CENTS: float = 25.0

# The spread that matters is the one RELATIVE TO PRICE. An 11c contract
# quoted 7/11 is a 4c spread -- trivial in cents, and a 36% round-trip haircut
# before the market has moved at all. Measured on this board, 12% of rows are
# under 3c and 13% have NO BID; scoring those at (0 - ask)/ask reports -100%
# per trade and drowns every other effect. The RU sizer already refuses them
# via MIN_PRICE_DOLLARS, so the backtest refuses them too -- a backtest that
# trades what the sizer would not is measuring a strategy nobody can run.
MAX_SPREAD_FRACTION: float = 0.10

# Kalshi ticks in whole cents; a modelled edge below one tick is noise.
TICK_CENTS: float = 1.0


@dataclass
class Trade:
    ts: int
    ticker: str
    series: str
    entry_ask_c: float
    exit_bid_c: float
    spread_c: float
    ru: float

    @property
    def gross_return(self) -> float:
        """Return on capital deployed, BEFORE fees. Entry at ask, exit at bid."""
        return (self.exit_bid_c - self.entry_ask_c) / self.entry_ask_c

    @property
    def mid_return(self) -> float:
        """Mid-to-mid return: DIRECTION only, paying no spread and no fee.

        This is not achievable -- no order fills at the mid on Kalshi. It is
        the diagnostic that separates the two reasons a strategy loses: if
        mid_return is around zero the signal has no direction, and if it is
        positive but net_return is negative the signal is real but too small
        to clear the cost of trading it. Those need completely different
        fixes, and the net number alone cannot tell them apart.
        """
        entry_mid = self.entry_ask_c - self.spread_c / 2.0
        exit_mid = self.exit_bid_c + self.spread_c / 2.0
        if entry_mid <= 0:
            return 0.0
        return (exit_mid - entry_mid) / entry_mid

    @property
    def spread_cost(self) -> float:
        """The round-trip spread, as a fraction of capital deployed."""
        return self.spread_c / self.entry_ask_c

    @property
    def fee_drag(self) -> float:
        """Both fee legs, as a fraction of the capital deployed."""
        entry = self.entry_ask_c / 100.0
        exit_ = self.exit_bid_c / 100.0
        paid = fee_per_contract(entry) + fee_per_contract(exit_)
        return paid / entry

    @property
    def net_return(self) -> float:
        return self.gross_return - self.fee_drag

    @property
    def return_per_ru(self) -> float:
        """Dollars earned per dollar of Risk Unit committed.

        This is the number that matters for sizing: a strategy that makes 2%
        on capital while burning 3 RU is worse than one making 1% on 1 RU.
        """
        if self.ru <= 0:
            return 0.0
        return (self.net_return * self.entry_ask_c / 100.0) / self.ru


@dataclass
class Result:
    name: str
    trades: list[Trade] = field(default_factory=list)
    buckets: list[float] = field(default_factory=list)
    n_configs_tried: int = 1
    skipped: dict = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.trades)

    @property
    def mean_return(self) -> float | None:
        return statistics.fmean(t.net_return for t in self.trades) if self.trades else None

    @property
    def mean_mid_return(self) -> float | None:
        return statistics.fmean(t.mid_return for t in self.trades) if self.trades else None

    @property
    def mean_spread_cost(self) -> float | None:
        return statistics.fmean(t.spread_cost for t in self.trades) if self.trades else None

    @property
    def mean_fee_drag(self) -> float | None:
        return statistics.fmean(t.fee_drag for t in self.trades) if self.trades else None

    @property
    def hit_rate(self) -> float | None:
        if not self.trades:
            return None
        return sum(1 for t in self.trades if t.net_return > 0) / len(self.trades)

    @property
    def mean_ru(self) -> float | None:
        return statistics.fmean(t.ru for t in self.trades) if self.trades else None

    @property
    def total_ru(self) -> float:
        return sum(t.ru for t in self.trades)

    @property
    def return_per_ru(self) -> float | None:
        if not self.trades:
            return None
        return statistics.fmean(t.return_per_ru for t in self.trades)

    @property
    def sharpe_per_bucket(self) -> float | None:
        """Sharpe across portfolio buckets -- the honest one.

        None when fewer than two buckets exist, or when every bucket returned
        exactly the same amount (zero variance is not infinite Sharpe, it is
        an unmeasurable one).
        """
        if len(self.buckets) < 2:
            return None
        sd = statistics.stdev(self.buckets)
        if sd == 0.0:
            return None
        return statistics.fmean(self.buckets) / sd

    def sharpe_annualised(self, seconds_per_bucket: float) -> float | None:
        """Per-bucket Sharpe scaled to a year.

        REPORT THIS WITH SUSPICION. Scaling a 15-second holding period by
        sqrt(2.1 million) assumes the edge survives being redeployed two
        million times a year with no capacity limit, no autocorrelation and
        no slippage. It does not. The per-bucket figure is the measurement;
        this is the extrapolation.
        """
        s = self.sharpe_per_bucket
        if s is None or seconds_per_bucket <= 0:
            return None
        buckets_per_year = (365.0 * 24 * 3600) / seconds_per_bucket
        return s * math.sqrt(buckets_per_year)

    @property
    def deflated_sharpe(self) -> float | None:
        """Sharpe after charging for the number of configurations tried.

        Bailey & Lopez de Prado: the expected maximum Sharpe of N independent
        random strategies is strictly positive, so the best of a grid search
        must clear that bar before it means anything. Returns the haircut
        Sharpe, not a probability.
        """
        s = self.sharpe_per_bucket
        if s is None or self.n_configs_tried < 1:
            return None
        n = self.n_configs_tried
        if n == 1:
            return s
        # Expected max of n standard normals (Bailey/LdP approximation).
        euler = 0.5772156649
        e_max = ((1 - euler) * _norm_ppf(1 - 1.0 / n)
                 + euler * _norm_ppf(1 - 1.0 / (n * math.e)))
        return s - e_max


def _norm_ppf(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation)."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"p must be in (0,1), got {p!r}")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def load_series_paths(path: Path) -> dict[str, list[dict]]:
    """Recorded JSONL grouped by ticker, each path sorted by timestamp."""
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            by_ticker[row["ticker"]].append(row)
    for rows in by_ticker.values():
        rows.sort(key=lambda r: r["ts"])
    return dict(by_ticker)


def _ru_for(row: dict, series: str) -> float | None:
    ask, spread = row.get("yes_ask_c"), row.get("spread_c")
    if ask is None or spread is None or spread < 0:
        return None
    rate = void_rate_for_series(series)
    if rate is None:
        rate = DEFAULT_VOID_RATE
    try:
        return ru_per_contract(ask / 100.0, spread_cents=spread, void_rate=rate)
    except ValueError:
        return None


def momentum_signal(path: list[dict], i: int, lookback: int,
                    threshold_c: float) -> bool:
    """True when the ask rose by >= threshold over the previous `lookback`.

    Uses ONLY rows at or before i. A signal that peeks at i+1 is the classic
    way a backtest invents alpha it can never trade.
    """
    if lookback <= 0 or i < lookback:
        return False
    now = path[i].get("yes_ask_c")
    then = path[i - lookback].get("yes_ask_c")
    if now is None or then is None:
        return False
    return (now - then) >= threshold_c


def run_strategy(by_ticker: dict[str, list[dict]], horizon: int,
                 name: str = "null", lookback: int = 0,
                 threshold_c: float = 0.0,
                 ts_min: int | None = None,
                 ts_max: int | None = None) -> Result:
    """Enter at ask, hold `horizon` snapshots, exit at bid.

    `lookback == 0` is the NULL strategy: every eligible bar is entered, so
    the result measures cost, not skill.
    """
    res = Result(name=name)
    by_bucket: dict[int, list[float]] = defaultdict(list)
    skipped: dict[str, int] = defaultdict(int)

    for ticker, path in by_ticker.items():
        series = (path[0].get("series") or ticker.split("-", 1)[0])
        for i, row in enumerate(path):
            j = i + horizon
            if j >= len(path):
                break
            ts = row.get("ts")
            if ts is None:
                continue
            if ts_min is not None and ts < ts_min:
                continue
            if ts_max is not None and ts >= ts_max:
                continue

            ask, spread = row.get("yes_ask_c"), row.get("spread_c")
            exit_bid = path[j].get("yes_bid_c")
            if ask is None or spread is None:
                skipped["wide_or_unpriced"] += 1
                continue
            if exit_bid is None:
                # The exit leg went dark. Missing data, NOT a flat return --
                # counted so the sample size stays honest about what it lost.
                skipped["no_bid"] += 1
                continue
            bid = row.get("yes_bid_c")
            if ask <= 0 or spread < 0 or spread > MAX_TRADEABLE_SPREAD_CENTS:
                skipped["wide_or_unpriced"] += 1
                continue
            if ask < MIN_PRICE_DOLLARS * 100.0:
                skipped["below_min_price"] += 1
                continue
            if bid is None or bid <= 0 or exit_bid <= 0:
                skipped["no_bid"] += 1
                continue
            if spread / ask > MAX_SPREAD_FRACTION:
                skipped["spread_fraction"] += 1
                continue
            if lookback and not momentum_signal(path, i, lookback, threshold_c):
                continue

            ru = _ru_for(row, series)
            if ru is None:
                continue
            t = Trade(ts=ts, ticker=ticker, series=series, entry_ask_c=ask,
                      exit_bid_c=exit_bid, spread_c=spread, ru=ru)
            res.trades.append(t)
            by_bucket[ts].append(t.net_return)

    res.buckets = [statistics.fmean(v) for _, v in sorted(by_bucket.items())]
    res.skipped = dict(skipped)
    return res


def split_by_time(by_ticker: dict[str, list[dict]],
                  train_fraction: float = 0.6) -> tuple[int, int, int]:
    """(first_ts, split_ts, last_ts). Split by CLOCK, never by ticker.

    Splitting by ticker would put a ticker's early bars in train and its late
    bars in test, leaking that ticker's own regime across the boundary.
    """
    all_ts = sorted({r["ts"] for rows in by_ticker.values() for r in rows})
    if not all_ts:
        raise ValueError("recording contains no timestamps")
    cut = all_ts[int(len(all_ts) * train_fraction)] if len(all_ts) > 1 else all_ts[0]
    return all_ts[0], cut, all_ts[-1]


def tune_momentum(by_ticker: dict[str, list[dict]], horizon: int,
                  ts_min: int, ts_max: int,
                  lookbacks: tuple[int, ...] = (1, 2, 3, 5, 8),
                  thresholds: tuple[float, ...] = (1.0, 2.0, 3.0, 5.0),
                  min_trades: int = 30) -> tuple[dict, list[dict]]:
    """Grid-search momentum params on the TRAIN slice only.

    Returns (best_config, all_configs). A configuration with fewer than
    `min_trades` is recorded but never chosen -- a 3-trade Sharpe of 4.0 is
    not a finding.
    """
    rows = []
    for lb in lookbacks:
        for th in thresholds:
            r = run_strategy(by_ticker, horizon, name=f"mom lb={lb} th={th}",
                             lookback=lb, threshold_c=th,
                             ts_min=ts_min, ts_max=ts_max)
            rows.append({"lookback": lb, "threshold_c": th, "n": r.n,
                         "sharpe": r.sharpe_per_bucket,
                         "mean_return": r.mean_return,
                         "return_per_ru": r.return_per_ru})
    eligible = [c for c in rows if c["n"] >= min_trades and c["sharpe"] is not None]
    best = max(eligible, key=lambda c: c["sharpe"]) if eligible else {}
    return best, rows


def _fmt(x, pct=False, nd=4):
    if x is None:
        return "n/a"
    return f"{x*100:.{nd-2}f}%" if pct else f"{x:.{nd}f}"


def report(res: Result, seconds_per_bucket: float, label: str) -> None:
    print(f"\n--- {label} ---")
    print(f"  trades                {res.n}")
    print(f"  portfolio buckets     {len(res.buckets)}")
    if res.skipped:
        tot = sum(res.skipped.values())
        detail = "  ".join(f"{k}={v}" for k, v in sorted(res.skipped.items()))
        print(f"  bars skipped          {tot}   ({detail})")
    print(f"  hit rate              {_fmt(res.hit_rate, pct=True)}")
    print(f"  DECOMPOSITION, per trade, as a fraction of capital deployed:")
    print(f"    direction (mid-mid) {_fmt(res.mean_mid_return, pct=True, nd=5)}"
          f"   <- what the market actually did")
    print(f"    spread paid         {_fmt(res.mean_spread_cost, pct=True, nd=5)}"
          f"   <- unavoidable at market orders")
    print(f"    fees paid           {_fmt(res.mean_fee_drag, pct=True, nd=5)}"
          f"   <- both legs, Kalshi schedule")
    print(f"  mean net return       {_fmt(res.mean_return, pct=True, nd=5)}"
          f"   (per trade, on capital deployed)")
    print(f"  mean RU / contract    {_fmt(res.mean_ru)}")
    print(f"  return per RU         {_fmt(res.return_per_ru, pct=True, nd=5)}")
    print(f"  SHARPE (per bucket)   {_fmt(res.sharpe_per_bucket)}")
    print(f"  Sharpe annualised     {_fmt(res.sharpe_annualised(seconds_per_bucket))}"
          f"   <- extrapolation, not measurement")
    if res.n_configs_tried > 1:
        print(f"  Deflated Sharpe       {_fmt(res.deflated_sharpe)}"
              f"   (after {res.n_configs_tried} configs tried)")


def cost_table(spread_c: float = 1.0) -> list[tuple[float, float, float, float]]:
    """Round-trip cost of a flat market, by price. (price, spread%, fee%, total%)

    THE FINDING THIS EXISTS TO SHOW: on Kalshi the FEE dominates the
    spread, not the other way round. At 50c on a 1c book the spread costs
    1.98% and the fee costs 6.93%. Because the fee is 0.07*P*(1-P) it is
    largest exactly at the mid prices where the liquid books trade, and it
    nearly vanishes at the extremes. Cost is therefore MINIMISED on heavy
    favourites, which is the opposite of where a spread-only intuition
    would send you.
    """
    out = []
    for px in (5, 10, 25, 50, 75, 90, 95):
        ask, bid = px + spread_c / 2.0, px - spread_c / 2.0
        t = Trade(ts=0, ticker="", series="", entry_ask_c=ask,
                  exit_bid_c=bid, spread_c=spread_c, ru=1.0)
        out.append((float(px), t.spread_cost, t.fee_drag, -t.net_return))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recording", default="state/book_recording.jsonl")
    ap.add_argument("--horizon", type=int, default=4,
                    help="snapshots held after entry")
    ap.add_argument("--train-fraction", type=float, default=0.6)
    args = ap.parse_args()

    by_ticker = load_series_paths(Path(args.recording))
    if not by_ticker:
        print("recording is empty")
        return 1

    first, cut, last = split_by_time(by_ticker, args.train_fraction)
    all_ts = sorted({r["ts"] for rows in by_ticker.values() for r in rows})
    step = statistics.median([b - a for a, b in zip(all_ts, all_ts[1:])]) \
        if len(all_ts) > 1 else 0.0
    sec_per_bucket = step or 1.0

    print(f"recording: {len(by_ticker)} tickers, {len(all_ts)} snapshots, "
          f"{step:.0f}s median step, span {last - first}s")
    print(f"train {first}..{cut} ({cut - first}s)   "
          f"test {cut}..{last} ({last - cut}s)")
    print(f"horizon {args.horizon} snapshots = {args.horizon * step:.0f}s held")

    print("\n=== WHAT A ROUND TRIP COSTS ON A FLAT MARKET (1c book) ===")
    print(f"  {'price':>7}{'spread':>9}{'fee':>9}{'total':>9}")
    for px, sc, fd, tot in cost_table(1.0):
        print(f"  {px:>6.0f}c{sc*100:>8.2f}%{fd*100:>8.2f}%{tot*100:>8.2f}%")
    print("  The FEE dominates, and it peaks at 50c. Cost is lowest on "
          "heavy favourites.")
    print("  A resting LIMIT order pays neither the spread nor the taker "
          "fee -- which is the")
    print("  only structural way out of this table.")

    print("\n=== HORIZON SWEEP: does holding longer earn the cost back? ===")
    print(f"  {'bars':>5} {'held':>7} {'n':>7} {'direction':>11} {'cost':>9} "
          f"{'net':>9} {'sharpe':>9}")
    max_h = max(1, min(12, len(all_ts) - 2))
    for h in range(1, max_h + 1):
        r = run_strategy(by_ticker, h, name=f"null h={h}")
        if not r.n:
            continue
        cost = (r.mean_spread_cost or 0) + (r.mean_fee_drag or 0)
        print(f"  {h:>5} {h*step:>6.0f}s {r.n:>7} "
              f"{_fmt(r.mean_mid_return, pct=True, nd=5):>11} "
              f"{_fmt(cost, pct=True, nd=5):>9} "
              f"{_fmt(r.mean_return, pct=True, nd=5):>9} "
              f"{_fmt(r.sharpe_per_bucket):>9}")
    print("  A strategy is only possible where |direction| can exceed cost.")

    null_all = run_strategy(by_ticker, args.horizon, name="null")
    report(null_all, sec_per_bucket, "NULL STRATEGY, whole recording "
                                     "(this is the COST FLOOR)")

    best, grid = tune_momentum(by_ticker, args.horizon, first, cut)
    print(f"\n--- momentum grid on TRAIN ({len(grid)} configs) ---")
    print(f"  {'lb':>3} {'thr':>5} {'n':>7} {'sharpe':>9} {'ret/RU':>10}")
    for c in sorted(grid, key=lambda c: -(c["sharpe"] or -9)):
        print(f"  {c['lookback']:>3} {c['threshold_c']:>5.1f} {c['n']:>7} "
              f"{_fmt(c['sharpe']):>9} {_fmt(c['return_per_ru'], pct=True):>10}")

    if not best:
        print("\nNo momentum configuration reached the minimum trade count on "
              "train. Nothing to score out of sample.")
        return 0

    print(f"\nBEST ON TRAIN: lookback={best['lookback']} "
          f"threshold={best['threshold_c']}c  sharpe={_fmt(best['sharpe'])}")

    test = run_strategy(by_ticker, args.horizon,
                        name="momentum (test)", lookback=best["lookback"],
                        threshold_c=best["threshold_c"], ts_min=cut)
    test.n_configs_tried = len(grid)
    report(test, sec_per_bucket, "MOMENTUM, HELD-OUT TEST SLICE")

    null_test = run_strategy(by_ticker, args.horizon, name="null (test)",
                             ts_min=cut)
    report(null_test, sec_per_bucket, "NULL on the same test slice (the bar)")

    if test.mean_return is not None and null_test.mean_return is not None:
        edge = test.mean_return - null_test.mean_return
        print(f"\nMomentum edge over null on test: {_fmt(edge, pct=True, nd=5)} "
              f"per trade")
        print(f"One tick is {TICK_CENTS}c; on a {_fmt(null_test.mean_ru)} RU book "
              f"that is roughly {TICK_CENTS / 100.0 / (null_test.mean_ru or 1):.2%} "
              f"of RU. An edge below one tick is not tradeable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
