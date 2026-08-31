"""Risk-neutral density from a Kalshi threshold ladder.

>>> THE AUTHOR WRITES THE BODIES. <<<

Kalshi rungs quote P(X >= K), so the ladder IS 1 - CDF. Breeden-Litzenberger
needs d2C/dK2 for vanillas; here the exchange has already done one of those
derivatives for you, and a single first difference gives the density.

DO NOT renormalise mass to 1. A truncated ladder genuinely does not observe
the tails, and pretending otherwise silently inflates every moment you
compute. Report `mass` and let the caller decide.
"""
from __future__ import annotations


def pdf_from_cdf(strikes: list[float],
                 p_ge: list[float]) -> list[tuple[float, float]]:
    """Bucket masses from a survival curve. Returns (midpoint, mass) pairs.

    Input must be sorted ascending by strike; raise ValueError if not.
    Output has len(strikes) - 1 entries. Mass may be NEGATIVE when the
    quotes violate monotonicity -- do not clip it, that is the signal.
    """
    raise NotImplementedError("Day 4: yours to write")


def moments(pdf: list[tuple[float, float]]) -> dict:
    """mean, var, stdev, skew, kurtosis, mass.

    Moments are computed on the OBSERVED mass without renormalising, then
    divided by `mass`, so a truncated ladder gives a conditional moment and
    `mass` tells you how much to distrust it. skew and kurtosis are the
    standardised third and fourth central moments; kurtosis is NOT excess.
    """
    raise NotImplementedError("Day 4: yours to write")


def negative_mass(pdf: list[tuple[float, float]]
                  ) -> list[tuple[float, float]]:
    """Every bucket with mass < 0. Empty list when the ladder is clean."""
    raise NotImplementedError("Day 4: yours to write")


def implied_move(pdf: list[tuple[float, float]],
                 confidence: float = 0.68) -> tuple[float, float] | None:
    """Narrowest (lo, hi) strike interval holding `confidence` of the mass.

    None when the observed mass is less than `confidence` -- you cannot
    report a 68% interval from a ladder that only observes 40% of the
    distribution.
    """
    raise NotImplementedError("Day 4: yours to write")
