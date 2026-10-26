"""Backtest the options mathematics against recorded Kalshi ladders.

WHAT IS TRADED. For each snapshot the ladder's implied volatility is
computed strike by strike, a smooth smile is fitted across log-moneyness,
and every strike is REPRICED at its fitted vol. A strike quoted below its
fitted price is cheap; above it, rich. Positions are held a fixed number of
snapshots and closed by crossing the book.

WHY COMPARE PRICES AND NOT VOLS. A digital's vega CHANGES SIGN across the
forward: more volatility raises an out-of-the-money digital and lowers an
in-the-money one. So "implied vol below the fit" means the option is cheap
on one side of the forward and RICH on the other, and a strategy phrased in
vol terms silently inverts on half the book. Repricing at the fitted vol and
comparing dollars sidesteps the sign entirely.

THE BAR EVERY RESULT MUST CLEAR. Plan 1 measured a round-trip cost of about
7.18% of capital, fee-dominated, against a mean directional move of 0.185%.
Any edge reported here is net of both legs of Kalshi's 0.07*P*(1-P) fee and
of crossing the spread, because a gross number on this exchange is not a
result.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from agent.digital import digital_call, implied_vol_roots, moneyness
from agent.ladder import Ladder, ladders_from_rows
from agent.risk_unit import MIN_PRICE_DOLLARS, fee_per_contract, ru_per_contract

# A ladder that captures little of the distribution has meaningless moments:
# its forward is pinned inside the observed window whatever the market thinks.
MIN_MASS_CAPTURED: float = 0.80

# Strikes this far from the money are saturated at 0 or 1 and carry no vol
# information -- inverting them produces noise, not a smile.
MIN_QUOTE: float = 0.03
MAX_QUOTE: float = 0.97

# Fitting a curvature term needs enough distinct strikes to be a fit rather
# than an interpolation.
MIN_SMILE_POINTS: int = 6


@dataclass(frozen=True)
class SmilePoint:
    strike: float
    x: float          # log-moneyness ln(F/K)
    mid: float
    ivol: float


@dataclass
class Fit:
    """Quadratic smile in log-moneyness: ivol = a + b*x + c*x^2."""
    a: float
    b: float
    c: float
    n: int
    rmse: float

    def vol_at(self, x: float) -> float:
        return self.a + self.b * x + self.c * x * x


def smile_points(lad: Ladder) -> list[SmilePoint]:
    """Implied vol per tradeable strike, using the LOW root.

    The low branch is chosen for continuity: it is the one that joins
    smoothly to the in-the-money side, so a smile built from it does not jump
    where strikes cross the forward.
    """
    f, t = lad.forward(), lad.t_years
    if f is None or not t:
        return []
    out = []
    for r in lad.rungs:
        if not (MIN_QUOTE < r.mid < MAX_QUOTE):
            continue
        lo, _ = implied_vol_roots(r.mid, f, r.strike, t)
        if lo is None:
            continue
        x = moneyness(f, r.strike)
        if x is None:
            continue
        out.append(SmilePoint(r.strike, x, r.mid, lo))
    return out


def fit_smile(points: list[SmilePoint]) -> Fit | None:
    """Least-squares quadratic in log-moneyness, solved in closed form.

    Quadratic because that is the smallest shape carrying the two facts a
    smile actually has: a level and a curvature. A linear fit cannot express
    the smile at all (it would call one wing cheap and the other rich by
    construction), and anything higher starts fitting the tick noise the
    density differences already suffer from.
    """
    n = len(points)
    if n < MIN_SMILE_POINTS:
        return None
    xs = [p.x for p in points]
    ys = [p.ivol for p in points]
    # Normal equations for [1, x, x^2]
    s0 = float(n)
    s1 = sum(xs)
    s2 = sum(x * x for x in xs)
    s3 = sum(x ** 3 for x in xs)
    s4 = sum(x ** 4 for x in xs)
    t0 = sum(ys)
    t1 = sum(x * y for x, y in zip(xs, ys))
    t2 = sum(x * x * y for x, y in zip(xs, ys))
    m = [[s0, s1, s2, t0], [s1, s2, s3, t1], [s2, s3, s4, t2]]
    # Gaussian elimination with partial pivoting
    for i in range(3):
        piv = max(range(i, 3), key=lambda r: abs(m[r][i]))
        if abs(m[piv][i]) < 1e-18:
            return None
        m[i], m[piv] = m[piv], m[i]
        for r in range(3):
            if r == i:
                continue
            f = m[r][i] / m[i][i]
            for c in range(i, 4):
                m[r][c] -= f * m[i][c]
    a, b, c = (m[i][3] / m[i][i] for i in range(3))
    fit = Fit(a, b, c, n, 0.0)
    resid = [p.ivol - fit.vol_at(p.x) for p in points]
    return Fit(a, b, c, n, math.sqrt(sum(r * r for r in resid) / n))


@dataclass
class Trade:
    ts: float
    event: str
    strike: float
    side: str            # "buy" (long YES) or "sell" (short YES via NO)
    entry_c: float       # price paid in cents
    exit_c: float        # price received in cents
    edge_c: float        # modelled mispricing at entry, cents
    ru: float

    @property
    def gross(self) -> float:
        """Return on capital deployed, before fees."""
        if self.entry_c <= 0:
            return 0.0
        return (self.exit_c - self.entry_c) / self.entry_c

    @property
    def fees(self) -> float:
        e, x = self.entry_c / 100.0, self.exit_c / 100.0
        return (fee_per_contract(e) + fee_per_contract(x)) / max(e, 1e-9)

    @property
    def net(self) -> float:
        return self.gross - self.fees


@dataclass
class Book:
    trades: list[Trade] = field(default_factory=list)
    skipped: dict = field(default_factory=lambda: defaultdict(int))

    def bucket_returns(self) -> list[float]:
        by = defaultdict(list)
        for t in self.trades:
            by[t.ts].append(t.net)
        return [st.fmean(v) for _, v in sorted(by.items())]

    def sharpe(self) -> float | None:
        b = self.bucket_returns()
        if len(b) < 2:
            return None
        sd = st.stdev(b)
        return None if sd == 0 else st.fmean(b) / sd


def run(ladders: dict, horizon: int, edge_threshold_c: float,
        max_trades_per_snapshot: int = 5) -> Book:
    """Trade fitted-price deviations, hold `horizon` snapshots, cross out."""
    book = Book()
    by_event: dict[str, list[Ladder]] = defaultdict(list)
    for (event, _ts), lad in ladders.items():
        by_event[event].append(lad)

    for event, lads in by_event.items():
        lads.sort(key=lambda l: l.ts)
        index = {l.ts: l for l in lads}
        times = [l.ts for l in lads]
        for i, lad in enumerate(lads):
            if i + horizon >= len(lads):
                break
            exit_lad = lads[i + horizon]
            if lad.mass_captured() < MIN_MASS_CAPTURED:
                book.skipped["thin_ladder"] += 1
                continue
            f, t = lad.forward(), lad.t_years
            if f is None or not t:
                book.skipped["no_forward"] += 1
                continue
            pts = smile_points(lad)
            fit = fit_smile(pts)
            if fit is None:
                book.skipped["no_fit"] += 1
                continue

            exit_by_strike = {r.strike: r for r in exit_lad.rungs}
            cands = []
            for p in pts:
                fair = digital_call(f, p.strike, fit.vol_at(p.x), t)
                if fair is None:
                    continue
                edge_c = (fair - p.mid) * 100.0     # +ve => market too cheap
                cands.append((abs(edge_c), edge_c, p))
            cands.sort(reverse=True)

            taken = 0
            for _, edge_c, p in cands:
                if taken >= max_trades_per_snapshot:
                    break
                if abs(edge_c) < edge_threshold_c:
                    break
                rung = next((r for r in lad.rungs if r.strike == p.strike), None)
                ex = exit_by_strike.get(p.strike)
                if rung is None or ex is None:
                    book.skipped["no_exit_quote"] += 1
                    continue
                if edge_c > 0:
                    entry_c, exit_c, side = rung.ask_c, ex.bid_c, "buy"
                else:
                    # Short YES is long NO: pay (100 - yes_bid), receive
                    # (100 - yes_ask) on exit. Kalshi has no naked short.
                    entry_c, exit_c, side = 100.0 - rung.bid_c, 100.0 - ex.ask_c, "sell"
                if entry_c < MIN_PRICE_DOLLARS * 100 or exit_c <= 0:
                    book.skipped["below_min_price"] += 1
                    continue
                try:
                    ru = ru_per_contract(entry_c / 100.0,
                                         spread_cents=rung.spread_c,
                                         void_rate=0.005)
                except ValueError:
                    book.skipped["bad_ru"] += 1
                    continue
                book.trades.append(Trade(lad.ts, event, p.strike, side,
                                         entry_c, exit_c, edge_c, ru))
                taken += 1
    return book


def realised_vol(lads: list[Ladder]) -> float | None:
    """Annualised vol of the ladder's own forward series.

    The forward is what the ladder says the underlying is worth, so its
    realised variation is the closest thing to realised vol available without
    an external spot feed -- and it is measured on exactly the same clock as
    the implied vol it is compared against, which avoids the horizon mismatch
    that would otherwise manufacture a premium out of nothing.
    """
    fs = [(l.ts, l.forward()) for l in sorted(lads, key=lambda l: l.ts)]
    fs = [(t, f) for t, f in fs if f]
    if len(fs) < 3:
        return None
    rets, dts = [], []
    for (t0, f0), (t1, f1) in zip(fs, fs[1:]):
        if f0 > 0 and f1 > 0 and t1 > t0:
            rets.append(math.log(f1 / f0))
            dts.append(t1 - t0)
    if len(rets) < 2:
        return None
    dt = st.median(dts)
    if dt <= 0:
        return None
    per_step = st.stdev(rets)
    return per_step * math.sqrt((365.0 * 24 * 3600) / dt)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recording", default="state/book_recording.jsonl")
    ap.add_argument("--series", default="KXBTCD")
    ap.add_argument("--horizon", type=int, default=10)
    ap.add_argument("--edge", type=float, default=1.0,
                    help="minimum modelled mispricing to trade, in cents")
    args = ap.parse_args()

    rows = []
    with Path(args.recording).open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("series") == args.series:
                rows.append(r)
    if not rows:
        print(f"no rows for {args.series}")
        return 1

    ladders = ladders_from_rows(rows)
    by_event = defaultdict(list)
    for (e, _t), l in ladders.items():
        by_event[e].append(l)

    print(f"{args.series}: {len(rows)} rows -> {len(ladders)} ladders "
          f"across {len(by_event)} events")
    print(f"\n{'event':22}{'snaps':>7}{'rungs':>7}{'mass':>7}{'fwd':>10}"
          f"{'impl_vol':>10}{'real_vol':>10}")
    for e, lads in sorted(by_event.items()):
        lads.sort(key=lambda l: l.ts)
        mid = lads[len(lads) // 2]
        pts = smile_points(mid)
        fit = fit_smile(pts)
        rv = realised_vol(lads)
        print(f"{e:22}{len(lads):>7}{len(mid.rungs):>7}"
              f"{mid.mass_captured():>7.2f}{(mid.forward() or 0):>10.0f}"
              f"{(fit.a if fit else float('nan')):>10.3f}"
              f"{(rv if rv else float('nan')):>10.3f}")

    print(f"\n=== BACKTEST: fitted-price deviation, horizon {args.horizon}, "
          f"edge >= {args.edge}c ===")
    book = run(ladders, args.horizon, args.edge)
    if not book.trades:
        print("no trades")
        return 0
    nets = [t.net for t in book.trades]
    gross = [t.gross for t in book.trades]
    fees = [t.fees for t in book.trades]
    wins = sum(1 for n in nets if n > 0)
    print(f"  trades              {len(book.trades)}")
    print(f"  skipped             {dict(book.skipped)}")
    print(f"  hit rate            {wins / len(nets):.1%}")
    print(f"  mean GROSS return   {st.fmean(gross):+.3%}")
    print(f"  mean fees           {st.fmean(fees):.3%}")
    print(f"  mean NET return     {st.fmean(nets):+.3%}")
    print(f"  median NET          {st.median(nets):+.3%}")
    print(f"  total RU committed  {sum(t.ru for t in book.trades):.1f}")
    s = book.sharpe()
    print(f"  SHARPE (per bucket) {s:.4f}" if s is not None else
          "  SHARPE              n/a")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
