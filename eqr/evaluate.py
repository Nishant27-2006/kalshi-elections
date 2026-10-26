"""Signal evaluation.

MIXED OWNERSHIP. `information_coefficient` and `quantile_spread` are YOURS
-- hand-building an IC is the highest-value hour of Day 6. Everything
below the divider is delivered.
"""
from __future__ import annotations

import math


def information_coefficient(signal_values: list[float | None],
                            forward_returns: list[float | None]
                            ) -> float | None:
    """>>> YOURS <<< Spearman rank correlation of signal vs forward return.

    Pairs where EITHER side is None are dropped. Returns None when fewer
    than 3 usable pairs remain -- a rank correlation on two points is
    always +-1 and is not information.

    Ties must be handled with AVERAGE ranks. Ranking [5, 5, 9] as [1, 2, 3]
    invents an ordering the signal never expressed.
    """
    raise NotImplementedError("Day 6: yours to write")


def quantile_spread(signal_values: list[float | None],
                    forward_returns: list[float | None],
                    n_q: int = 5) -> float | None:
    """>>> YOURS <<< Mean forward return of the top quantile minus bottom.

    None when fewer than n_q usable pairs remain. This is the number a PM
    actually cares about: an IC of 0.04 that comes entirely from the middle
    of the distribution is not tradeable.
    """
    raise NotImplementedError("Day 6: yours to write")


# ---------------------------------------------------------------- delivered

def ic_t_stat(ics: list[float]) -> float | None:
    """t-stat of the mean IC across rebalances.

    Newey-West is NOT applied: overlapping horizons make these
    autocorrelated and this t-stat is therefore OPTIMISTIC. Treat it as an
    upper bound, and say so out loud when someone asks.
    """
    clean = [x for x in ics if x is not None and not math.isnan(x)]
    n = len(clean)
    if n < 2:
        return None
    mean = sum(clean) / n
    var = sum((x - mean) ** 2 for x in clean) / (n - 1)
    if var <= 0:
        return None
    return mean / math.sqrt(var / n)


def deflated_sharpe(observed_sharpe: float, n_trials: int,
                    n_obs: int) -> float | None:
    """Sharpe adjusted for how many strategies you TRIED before this one.

    Bailey & Lopez de Prado. The expected maximum Sharpe from n_trials
    independent random strategies is roughly sqrt(2*ln(n_trials)) /
    sqrt(n_obs). If your observed Sharpe does not clear that, you found
    noise and named it alpha.
    """
    if n_trials < 1 or n_obs < 2:
        return None
    expected_max = math.sqrt(2.0 * math.log(max(n_trials, 2))) / math.sqrt(n_obs)
    return observed_sharpe - expected_max
