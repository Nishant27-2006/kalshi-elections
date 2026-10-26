"""Validate the RISK model without any alpha model.

These are different questions and conflating them is a common failure:

    alpha validation -- does the signal predict direction?
    risk validation  -- does a position sized at 1 RU actually realise about
                        $1 of adverse excursion out of sample?

The second needs no alpha at all: replay recorded books, take systematic
entries, and compare realised adverse excursion against the RU prediction.

MEASURED, and this is NOT what was originally hoped: as the RU formula
currently stands, predicted RU can EXCEED the maximum loss a YES contract
can take (the price cannot fall below zero), which makes a breach
arithmetically impossible rather than merely unlikely. The region is NOT a
single band and NOT simply 'cheap contracts are safe' -- it depends on the
spread. Breach-impossible price runs, computed from the shipped formula:

    vertical          2c spread      6c spread      8c spread
    mlb_game          23.3-67.7c     3.0-70.5c      3.0-71.8c
    atp_match         20.1-70.9c     3.0-73.3c      3.0-74.3c
    esports_series    15.1-75.9c     3.0-77.7c      3.0-78.6c

So on a TIGHT book a cheap longshot CAN breach -- mlb_game at a 2c spread
is breachable below about 23c -- while the same contract on a wide book
cannot breach anywhere above 3c. The mid-price zone is impossible in every
vertical at every spread measured.

The direction that matters: esports has the WIDER no-breach zone at every
spread. Its larger void rate and wider quotes RAISE predicted RU, so at mid
prices esports breaches LESS often than MLB, the opposite of the
discrimination this harness was built to demonstrate. Treat a clean
calibration run as uninformative there, not as evidence the RU is sound.

Cause: for a BOUNDED binary, a two-sigma move is definitionally the whole
distance to settlement -- at 50c the volatility term alone equals the entire
capital -- so no ceiling on RU repairs this. Only a smaller SIGMA_MULTIPLE
does, and that halves RU and therefore DOUBLES position size. Spec 7.4
assigns parameter revision to the monthly human-approved re-fit, so this
module does not attempt it.

A calibrated risk model is worth more than an uncalibrated alpha model,
because it is what keeps the account solvent while the alpha search runs.

Spec section 7.3.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
import math
from dataclasses import dataclass
from pathlib import Path

from agent.risk_unit import ru_per_contract, MIN_PRICE_DOLLARS
from agent.void_rates import DEFAULT_VOID_RATE, vertical_for_series, void_rate_for_series


def adverse_excursion(entry_price_c: float, path_c: list[float],
                      side: str = "yes") -> float:
    """Worst move AGAINST the position, in DOLLARS per contract.

    entry_price_c  entry price in cents
    path_c         subsequent prices in cents, in time order
    side           "yes" (hurt by falls) or "no" (hurt by rises)
    """
    if not path_c:
        return 0.0
    if side == "yes":
        worst = min(path_c)
        move_c = max(0.0, entry_price_c - worst)
    else:
        worst = max(path_c)
        move_c = max(0.0, worst - entry_price_c)
    return move_c / 100.0


@dataclass(frozen=True)
class BreachStats:
    """How often realised adverse excursion exceeded the RU prediction.

    `rate` is None for an empty sample: zero breaches out of zero
    observations is not a 0% breach rate, and reporting it as one would be
    the same survivorship error the repo already documents.
    """
    n: int
    breaches: int
    rate: float | None
    nominal: float


def breach_stats(observations: list[tuple[float, float]],
                 nominal: float) -> BreachStats:
    """observations: (realised_adverse_excursion_usd, predicted_ru_usd) pairs.

    `nominal` is the breach rate the model implies, so the caller can compare
    observed against expected rather than eyeballing a bare number.
    """
    n = len(observations)
    if n == 0:
        return BreachStats(0, 0, None, nominal)
    breaches = sum(1 for realised, predicted in observations
                   if realised > predicted)
    return BreachStats(n, breaches, breaches / n, nominal)


# With SIGMA_MULTIPLE = 2.0 the model plans for a two-sigma adverse traverse,
# so a well-calibrated book should breach only occasionally. This is the
# number the observed rate is compared against, not a target to hit.
NOMINAL_BREACH_RATE = 0.05


@dataclass
class SkipCounts:
    """How many tickers calibrate() dropped, and why.

    `main()` prints `len(by_ticker)` tickers loaded but `stats` only counts
    the ones that made it all the way to a measurement -- a gap a reader can
    easily mistake for the sample size. Pass an instance in via calibrate()'s
    `skips` kwarg to have it populated in place; calibrate()'s return type
    stays a plain dict[str, BreachStats] either way, so existing callers are
    unaffected.
    """
    too_few_rows: int = 0
    empty_path: int = 0
    missing_quote: int = 0
    unquoted_path: int = 0
    sizing_error: int = 0

    @property
    def total(self) -> int:
        return (self.too_few_rows + self.empty_path + self.missing_quote
               + self.unquoted_path + self.sizing_error)


def load_recording(path: Path) -> dict[str, list[dict]]:
    """Recorded JSONL grouped by ticker, each series sorted by timestamp."""
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


def calibrate(by_ticker: dict[str, list[dict]],
              horizon: int,
              skips: SkipCounts | None = None) -> dict[str, BreachStats]:
    """Systematic entry at each ticker's first quote, held `horizon` steps.

    NO ALPHA MODEL: every ticker is entered, so this measures the RISK model
    alone. Grouped by vertical because the void term is vertical-specific.

    `skips`, if passed, is populated in place with a count of dropped
    tickers by reason -- see SkipCounts.
    """
    if skips is None:
        skips = SkipCounts()
    obs_by_vertical: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for ticker, rows in by_ticker.items():
        if len(rows) < 2:
            skips.too_few_rows += 1
            continue
        entry, path = rows[0], rows[1:1 + horizon]
        if not path:
            skips.empty_path += 1
            continue
        ask = entry.get("yes_ask_c")
        spread = entry.get("spread_c")
        if ask is None or spread is None:
            skips.missing_quote += 1
            continue

        series = entry.get("series") or ticker.split("-", 1)[0]
        vertical = vertical_for_series(series)
        rate = void_rate_for_series(series)
        if rate is None:
            vertical, rate = "unmeasured", DEFAULT_VOID_RATE

        try:
            predicted = ru_per_contract(ask / 100.0, spread_cents=spread,
                                        void_rate=rate)
        except ValueError as exc:
            # A malformed row (e.g. a negative spread reaching this far)
            # must not abort the whole replay -- announce and move on.
            print(f"  skip {ticker}: {type(exc).__name__}: {exc}")
            skips.sizing_error += 1
            continue

        path_asks = [r["yes_ask_c"] for r in path
                    if r.get("yes_ask_c") is not None]
        if not path_asks:
            # Every row in the held path is unquoted: this is MISSING DATA,
            # not a measured non-breach. Scoring it as 0.0 excursion would
            # silently bias the breach rate downward, and books go unquoted
            # precisely when risk is real.
            skips.unquoted_path += 1
            continue
        realised = adverse_excursion(ask, path_asks)
        obs_by_vertical[vertical].append((realised, predicted))

    return {v: breach_stats(obs, NOMINAL_BREACH_RATE)
            for v, obs in obs_by_vertical.items()}


@dataclass(frozen=True)
class ScalingFit:
    """Realised adverse excursion fitted as `k * t**alpha`, t in seconds.

    READ `stable` BEFORE READING `alpha`. Measured on 37 minutes of live
    books, the fitted exponent slides monotonically from 0.98 to 0.44 as the
    fitting window is extended, and R^2 falls from 0.95 to 0.82. A single
    power law DOES NOT describe this data: excursion grows quickly at short
    horizons and then SATURATES, which is concave in log-log and cannot be
    captured by one exponent.

    That matters because the naive reading is backwards. Fitted on the first
    8 minutes alone the exponent is 0.68 and the market looks like it TRENDS
    -- the regime a momentum strategy needs. Fitted on the full recording it
    is 0.44 and the market MEAN-REVERTS. The first number is an artefact of
    the window, and a fund that sized on it would have bought a trend that
    is not there.

    When `stable` is False, `alpha` describes the fitted window and nothing
    beyond it, and `excursion_at` must not be used to extrapolate.
    """
    k: float
    alpha: float
    n_points: int
    fitted_from_s: float
    fitted_to_s: float
    r_squared: float
    alpha_half_window: float

    @property
    def stable(self) -> bool:
        """True when halving the fitting window barely moves the exponent.

        A power law is scale-free: fitted on half the range it must give the
        same exponent. When it does not, the model is misspecified and no
        extrapolation from it is trustworthy.
        """
        return (abs(self.alpha - self.alpha_half_window) <= 0.10
                and self.r_squared >= 0.95)

    @property
    def saturating(self) -> bool:
        """Excursion is flattening: the half-window exponent exceeds the
        full-window one, so later horizons add less than earlier ones."""
        return self.alpha_half_window > self.alpha + 0.10

    def excursion_at(self, seconds: float) -> float:
        return self.k * (seconds ** self.alpha)

    def extrapolation_factor(self, seconds: float) -> float:
        """How far beyond the fitted data a query reaches."""
        if self.fitted_to_s <= 0:
            return float("inf")
        return seconds / self.fitted_to_s


def _fit_loglog(pts: list[tuple[float, float]]) -> tuple[float, float, float]:
    """(alpha, k, r_squared) by least squares on log(t) vs log(excursion)."""
    xs = [math.log(t) for t, _ in pts]
    ys = [math.log(v) for _, v in pts]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    denom = sum((a - mx) ** 2 for a in xs)
    if denom == 0:
        return 0.0, 0.0, 0.0
    alpha = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / denom
    pred = [my + alpha * (x - mx) for x in xs]
    ssr = sum((b - q) ** 2 for b, q in zip(ys, pred))
    sst = sum((b - my) ** 2 for b in ys)
    r2 = 1.0 - ssr / sst if sst > 0 else 0.0
    return alpha, math.exp(my - alpha * mx), r2


def excursion_points(by_ticker: dict[str, list[dict]],
                     min_sample: int = 50) -> list[tuple[float, float]]:
    """(holding_seconds, mean realised excursion) across every horizon."""
    ts = sorted({r["ts"] for rows in by_ticker.values() for r in rows})
    if len(ts) < 4:
        return []
    steps = [b - a for a, b in zip(ts, ts[1:])]
    step = sorted(steps)[len(steps) // 2]
    if step <= 0:
        return []
    pts: list[tuple[float, float]] = []
    for h in range(1, len(ts) - 1):
        vals = []
        for ticker, rows in by_ticker.items():
            if len(rows) < h + 1:
                continue
            entry, path = rows[0], rows[1:1 + h]
            ask = entry.get("yes_ask_c")
            if ask is None or ask < MIN_PRICE_DOLLARS * 100.0:
                continue
            asks = [x["yes_ask_c"] for x in path
                    if x.get("yes_ask_c") is not None]
            if not asks:
                continue
            vals.append(adverse_excursion(ask, asks))
        if len(vals) >= min_sample:
            m = sum(vals) / len(vals)
            if m > 0:
                pts.append((h * step, m))
    return pts


def excursion_scaling(by_ticker: dict[str, list[dict]],
                      min_sample: int = 50) -> ScalingFit | None:
    """Fit excursion against holding time, AND check the fit is scale-free.

    The half-window refit is the whole point. A power law fitted on half the
    range must return the same exponent; when it does not, one exponent is
    the wrong model and every extrapolation off it is invented precision.
    """
    pts = excursion_points(by_ticker, min_sample)
    if len(pts) < 3:
        return None
    alpha, k, r2 = _fit_loglog(pts)
    half = pts[:max(3, len(pts) // 2)]
    alpha_half, _, _ = _fit_loglog(half)
    return ScalingFit(k=k, alpha=alpha, n_points=len(pts),
                      fitted_from_s=pts[0][0], fitted_to_s=pts[-1][0],
                      r_squared=r2, alpha_half_window=alpha_half)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recording", default="state/book_recording.jsonl")
    ap.add_argument("--horizon", type=int, default=10,
                    help="snapshots held after entry")
    args = ap.parse_args()

    by_ticker = load_recording(Path(args.recording))
    skips = SkipCounts()
    stats = calibrate(by_ticker, args.horizon, skips=skips)
    if not stats:
        print("no ticker had enough snapshots to measure -- record longer")
        return 0

    measured = sum(s.n for s in stats.values())
    print(f"RU calibration: {measured} tickers measured, {skips.total} "
          f"dropped, out of {len(by_ticker)} tickers loaded, "
          f"horizon {args.horizon} snapshots")
    print(f"{'vertical':22} {'n':>6} {'breaches':>9} {'rate':>8} {'nominal':>8}")
    for vertical, s in sorted(stats.items()):
        rate = "n/a" if s.rate is None else f"{s.rate:.1%}"
        print(f"  {vertical:20} {s.n:6} {s.breaches:9} {rate:>8} "
              f"{s.nominal:8.1%}")
    print("\nA rate far ABOVE nominal means RU is under-stating risk; far "
          "BELOW means it is over-stating and positions are too small.")

    fit = excursion_scaling(by_ticker)
    if fit is None:
        print("\nNot enough of a recording to fit the excursion curve.")
        return 0

    print("\n=== HOW EXCURSION GROWS WITH HOLDING TIME ===")
    print(f"  fitted on {fit.n_points} horizons, {fit.fitted_from_s:.0f}s "
          f"to {fit.fitted_to_s:.0f}s")
    print(f"  excursion = {fit.k:.6f} * t^{fit.alpha:.3f}   (R^2 {fit.r_squared:.3f})")
    print(f"  same fit on HALF the range gives alpha {fit.alpha_half_window:.3f}")

    if not fit.stable:
        print("\n  THE FIT IS NOT SCALE-FREE, so a single exponent is the "
              "WRONG MODEL here.")
        print(f"  Halving the window moves alpha by "
              f"{abs(fit.alpha - fit.alpha_half_window):.3f}; a real power "
              f"law would not move at all.")
        if fit.saturating:
            print("  Excursion SATURATES: it grows quickly early and then "
                  "flattens, which is")
            print("  mean reversion, not a trend. Fitted on the first "
                  "eighth of this recording")
            print("  alone the exponent reads 0.68 and the market looks "
                  "like it TRENDS -- the")
            print("  regime a momentum strategy needs. It does not. That "
                  "number is an artefact")
            print("  of the window, and sizing on it would buy a trend "
                  "that is not there.")
        print("\n  Refusing to extrapolate. Measured values only:")
        pts = excursion_points(by_ticker)
        for t_s, e in pts:
            if t_s in (pts[0][0], pts[len(pts)//4][0], pts[len(pts)//2][0],
                       pts[-1][0]):
                print(f"    {t_s:7.0f}s held -> excursion {e:.4f}"
                      f"   vs a 0.40 RU: RU is {0.40/e:5.1f}x larger")
        print("  To learn what RU should be at settlement, record to "
              "settlement. Spec 10b.")
        return 0

    print("\n  hold      excursion  extrapolation  verdict vs a 0.40 RU")
    for label, secs in (("1 min", 60), ("1 hour", 3600), ("3 hours", 10800),
                        ("1 day", 86400), ("1 week", 604800)):
        e = fit.excursion_at(secs)
        f = fit.extrapolation_factor(secs)
        verdict = ("RU far too big" if e < 0.20 else
                   "RU about right" if e < 0.60 else "RU TOO SMALL")
        flag = "" if f <= 3 else (" (est.)" if f <= 30 else " (WIDE EST.)")
        print(f"  {label:9} {e:9.4f} {f:11.0f}x{flag:13} {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
