"""Validate the RISK model without any alpha model.

These are different questions and conflating them is a common failure:

    alpha validation -- does the signal predict direction?
    risk validation  -- does a position sized at 1 RU actually realise about
                        $1 of adverse excursion out of sample?

The second needs no alpha at all: replay recorded books, take systematic
entries, and compare realised adverse excursion against the RU prediction. If
the void term is right, esports positions should breach their RU far more
often than MLB games. That is directly falsifiable.

A calibrated risk model is worth more than an uncalibrated alpha model,
because it is what keeps the account solvent while the alpha search runs.

Spec section 7.3.
"""
from __future__ import annotations

from dataclasses import dataclass


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


import argparse
import json
from collections import defaultdict
from pathlib import Path

from agent.risk_unit import ru_per_contract
from agent.void_rates import DEFAULT_VOID_RATE, vertical_for_series, void_rate_for_series

# With SIGMA_MULTIPLE = 2.0 the model plans for a two-sigma adverse traverse,
# so a well-calibrated book should breach only occasionally. This is the
# number the observed rate is compared against, not a target to hit.
NOMINAL_BREACH_RATE = 0.05


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
              horizon: int) -> dict[str, BreachStats]:
    """Systematic entry at each ticker's first quote, held `horizon` steps.

    NO ALPHA MODEL: every ticker is entered, so this measures the RISK model
    alone. Grouped by vertical because the void term is vertical-specific.
    """
    obs_by_vertical: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for ticker, rows in by_ticker.items():
        if len(rows) < 2:
            continue
        entry, path = rows[0], rows[1:1 + horizon]
        if not path:
            continue
        ask = entry.get("yes_ask_c")
        spread = entry.get("spread_c")
        if ask is None or spread is None:
            continue

        series = entry.get("series") or ticker.split("-", 1)[0]
        vertical = vertical_for_series(series)
        rate = void_rate_for_series(series)
        if rate is None:
            vertical, rate = "unmeasured", DEFAULT_VOID_RATE

        predicted = ru_per_contract(ask / 100.0, spread_cents=spread,
                                    void_rate=rate)
        mids = [r["yes_ask_c"] for r in path if r.get("yes_ask_c") is not None]
        realised = adverse_excursion(ask, mids)
        obs_by_vertical[vertical].append((realised, predicted))

    return {v: breach_stats(obs, NOMINAL_BREACH_RATE)
            for v, obs in obs_by_vertical.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recording", default="state/book_recording.jsonl")
    ap.add_argument("--horizon", type=int, default=10,
                    help="snapshots held after entry")
    args = ap.parse_args()

    by_ticker = load_recording(Path(args.recording))
    stats = calibrate(by_ticker, args.horizon)
    if not stats:
        print("no ticker had enough snapshots to measure -- record longer")
        return 0

    print(f"RU calibration over {len(by_ticker)} tickers, "
          f"horizon {args.horizon} snapshots")
    print(f"{'vertical':22} {'n':>6} {'breaches':>9} {'rate':>8} {'nominal':>8}")
    for vertical, s in sorted(stats.items()):
        rate = "n/a" if s.rate is None else f"{s.rate:.1%}"
        print(f"  {vertical:20} {s.n:6} {s.breaches:9} {rate:>8} "
              f"{s.nominal:8.1%}")
    print("\nA rate far ABOVE nominal means RU is under-stating risk; far "
          "BELOW means it is over-stating and positions are too small.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
