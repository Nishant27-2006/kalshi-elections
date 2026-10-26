"""Digital Greeks by finite difference over your own Monte Carlo.

>>> THE AUTHOR WRITES THE BODIES. <<<

The point of this module is NOT to compute Greeks -- agent/digital.py
already has closed forms. The point is that your MC and the closed forms
must agree, which is what proves you understand both.

TWO THINGS WILL BITE YOU, AND BOTH ARE THE LESSON.

1. THE BUMP CANNOT BE TINY. A digital's payoff is an INDICATOR, so
   bump-and-revalue does not measure a smooth derivative -- it counts how
   many of your finitely many paths cross the strike inside the bump
   window. With 400,000 paths one path is 2.5e-6 of probability. A bump of
   h = 1e-4 moves the price by about 3e-6, so roughly ONE path crosses,
   and the estimate is quantised noise. Measured 2026-08-30 at h = 1e-4:
   delta was wrong by -18% at K=90, -21% at K=100, and -100% at K=115,
   where zero paths crossed and the estimator returned exactly 0.

   This is why the defaults below are h = 0.5 for delta (0.5% of a forward
   of 100) and h = 0.01 for vega (2% of a sigma of 0.5). They are not the
   same number because a forward and a volatility do not live on the same
   scale. At those bumps the same code lands within about 2%.

   The tension is real and you should be able to state it: a large h adds
   discretisation BIAS, a small h adds VARIANCE, and with a discontinuous
   payoff the variance term blows up far faster than the bias term.

2. COMMON RANDOM NUMBERS. Pass the SAME seed to the base and the bumped
   simulation so the two runs share their draws and the difference cancels
   the noise instead of compounding it. Measured at h = 0.5: CRN gives
   1.3% error, independent draws 4.6%. At h = 0.05: 4.4% versus 46%. The
   smaller your bump, the more CRN is doing for you.

   Note what the test suite can and cannot prove here.
   `test_common_random_numbers_are_used` only checks that the same seed
   returns the same number, which any seeded implementation satisfies. The
   tests that actually enforce CRN are the accuracy ones -- lose it and
   they drift out of tolerance. Do not read a green determinism test as
   evidence you got this right.
"""
from __future__ import annotations


def fd_delta(forward: float, strike: float, sigma: float, t_years: float,
             h: float = 0.5, n_paths: int = 400_000,
             seed: int = 31) -> float:
    """Central difference dPrice/dForward with common random numbers.

        (P(F + h) - P(F - h)) / (2h)

    Both evaluations must use `seed`, unchanged. h defaults to 0.5, an
    ABSOLUTE bump on the forward -- see the module docstring for why it is
    not 1e-4.
    """
    raise NotImplementedError("Day 3: yours to write")


def fd_vega(forward: float, strike: float, sigma: float, t_years: float,
            h: float = 0.01, n_paths: int = 400_000,
            seed: int = 31) -> float:
    """Central difference dPrice/dSigma with common random numbers.

        (P(sigma + h) - P(sigma - h)) / (2h)

    h defaults to 0.01, an ABSOLUTE bump on volatility. A vol of 0.5 and a
    forward of 100 do not take the same bump, which is the whole reason
    this default differs from fd_delta's.
    """
    raise NotImplementedError("Day 3: yours to write")


def vega_sign(forward: float, strike: float, sigma: float,
              t_years: float) -> int:
    """+1, -1 or 0.

    Use the ANALYTIC vega from agent/digital.py, NOT your finite
    difference. Near the zero crossing the FD estimate is noise around
    zero and would return the wrong sign roughly half the time -- and the
    sign is the one thing about a digital's vega you cannot afford to get
    wrong. Return 0 when |vega| is below 1e-9.
    """
    raise NotImplementedError("Day 3: yours to write")
