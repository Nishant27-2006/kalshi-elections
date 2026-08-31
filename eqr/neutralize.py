"""Neutralization.

>>> THE AUTHOR WRITES THE BODIES. <<<

A raw Kalshi cross-section is dominated by group effects: 40 KXBTCD rungs
all track one Bitcoin price. A signal that loads on "is a BTC rung" will
show a large IC on any day BTC moves, and that is not alpha -- it is a
factor bet you did not know you were making.

Order matters: demean within group FIRST, then z-score. Reversing them
lets a large group's dispersion set the scale for every other group.
"""
from __future__ import annotations


def demean_by_group(values: list[float | None],
                    groups: list[str]) -> list[float | None]:
    """Subtract each group's mean from its members. None passes through."""
    raise NotImplementedError("Day 8: yours to write")


def zscore(values: list[float | None]) -> list[float | None]:
    """(x - mean) / sample_std over non-None values, ddof = 1.

    Returns all None when the standard deviation is zero -- a constant
    signal carries no cross-sectional information and must not be
    resurrected by dividing by an epsilon.
    """
    raise NotImplementedError("Day 8: yours to write")


def regress_out(values: list[float | None],
                factors: list[list[float]]) -> list[float | None]:
    """OLS residual of values on factors, no intercept added automatically.

    Include an intercept explicitly as a column of ones if you want one.
    Use numpy.linalg.lstsq -- it handles the rank-deficient case that
    perfectly collinear group dummies produce, which a normal-equations
    inverse does not.
    """
    raise NotImplementedError("Day 8: yours to write")
