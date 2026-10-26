"""Implied-vol surface from a strip of Kalshi digitals.

>>> THE AUTHOR WRITES THE BODIES. <<<

The whole difficulty is that a digital's price is not monotone in sigma
out of the money, so inversion is not a function -- it is a relation with
up to two branches. agent/digital.py already exposes `implied_vol_roots`,
`peak_vol` and `max_digital_price`; use them rather than rolling a solver.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SurfacePoint:
    strike: float
    price: float
    moneyness: float
    iv_low: float | None
    iv_high: float | None
    invertible: bool


def build_surface(forward: float, t_years: float,
                  quotes: list[tuple[float, float]]) -> list[SurfacePoint]:
    """One SurfacePoint per (strike, price) quote, in the order given.

    invertible is False when no sigma reproduces the price -- which happens
    when an out-of-the-money quote exceeds `max_digital_price`. Return the
    point with iv_low = iv_high = None rather than dropping it: a
    non-invertible quote is a signal, not a nuisance.
    """
    raise NotImplementedError("Day 2: yours to write")


def smile_slope(points: list[SurfacePoint]) -> float | None:
    """OLS slope of iv_low against moneyness over invertible points.

    None when fewer than two points are invertible. This is the crudest
    possible skew measure and that is deliberate -- you will replace it on
    Day 4 once you have a real density.
    """
    raise NotImplementedError("Day 2: yours to write")
