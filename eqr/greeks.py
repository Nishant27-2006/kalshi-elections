"""Digital Greeks by finite difference over your own Monte Carlo.

>>> THE AUTHOR WRITES THE BODIES. <<<

The point of this module is NOT to compute Greeks -- agent/digital.py
already has closed forms. The point is that your MC and the closed forms
must agree, which is what proves you understand both.

CRITICAL: use COMMON RANDOM NUMBERS. Pass the same seed to both the base
and the bumped simulation. Fresh randoms make the finite difference
(signal + noise)/h, and with h = 1e-4 the noise wins by orders of
magnitude. If a test is flaky, this is why.
"""
from __future__ import annotations


def fd_delta(forward: float, strike: float, sigma: float, t_years: float,
             h: float = 1e-4, n_paths: int = 400_000,
             seed: int = 31) -> float:
    """Central difference dPrice/dForward with common random numbers."""
    raise NotImplementedError("Day 3: yours to write")


def fd_vega(forward: float, strike: float, sigma: float, t_years: float,
            h: float = 1e-4, n_paths: int = 400_000,
            seed: int = 31) -> float:
    """Central difference dPrice/dSigma with common random numbers."""
    raise NotImplementedError("Day 3: yours to write")


def vega_sign(forward: float, strike: float, sigma: float,
              t_years: float) -> int:
    """+1, -1 or 0. Use the ANALYTIC vega, not the finite difference --
    a noisy estimate near the zero crossing would return the wrong sign.
    Return 0 when |vega| is below 1e-9."""
    raise NotImplementedError("Day 3: yours to write")
