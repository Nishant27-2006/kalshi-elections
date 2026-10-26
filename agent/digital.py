"""Black-Scholes for the only option Kalshi actually lists: the digital.

WHY NOT PLAIN BLACK-SCHOLES. Kalshi lists no puts or calls -- every contract
returns `market_type: binary`, and threshold markets return
`strike_type: greater`. A Kalshi contract already IS a cash-or-nothing
digital call paying $1 if the underlying finishes at or above the strike.
Its Black-Scholes value is

    C_digital = e^{-rT} * N(d2)

so at Kalshi tenors, where e^{-rT} is within a rounding error of 1, THE
QUOTED PRICE IS N(d2). You do not price these with the model. You invert
them to recover what the market believes.

    d1 = [ln(F/K) + (sigma^2 / 2) T] / (sigma sqrt(T))
    d2 = d1 - sigma sqrt(T)

FORWARD, NOT SPOT. Kalshi publishes no underlying price, so `S` is not
available. This module takes the FORWARD F, which the caller recovers from
the ladder's own risk-neutral mean. Under r=0 forward and spot coincide, and
building a vol surface from the forward implied by the option strip is
standard practice rather than a workaround -- but it does mean implied vol
here is a statement about the ladder's internal consistency, not about the
gap between Kalshi and a spot exchange. See the spec's open question 2.

EVERY FUNCTION HERE IS PURE. No network, no market data, no state -- so the
round-trip test (price a ladder from a known sigma, recover that sigma) can
run before any of this sees a real quote. An implementation that cannot
recover a sigma it just used is wrong, and that has to be provable without
an API key.
"""
from __future__ import annotations

import math

# Below this the pricing formulas divide by ~0 and return noise rather than a
# number. Callers get None instead of a plausible-looking value.
MIN_T_YEARS: float = 1e-9
MIN_SIGMA: float = 1e-6
MAX_SIGMA: float = 50.0

SECONDS_PER_YEAR: float = 365.0 * 24.0 * 3600.0


def _norm_cdf(x: float) -> float:
    """Standard normal CDF via erf -- exact to machine precision, no scipy."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def d1_d2(forward: float, strike: float, sigma: float,
          t_years: float) -> tuple[float, float] | None:
    """(d1, d2), or None when the inputs cannot support a finite answer."""
    if (forward <= 0 or strike <= 0 or sigma < MIN_SIGMA
            or t_years < MIN_T_YEARS):
        return None
    vol_t = sigma * math.sqrt(t_years)
    d1 = (math.log(forward / strike) + 0.5 * sigma * sigma * t_years) / vol_t
    return d1, d1 - vol_t


def digital_call(forward: float, strike: float, sigma: float, t_years: float,
                 rate: float = 0.0) -> float | None:
    """P(X >= K) under lognormal dynamics: the Kalshi YES price.

    Returns None rather than a number when the inputs are degenerate. A
    degenerate input is not a 50/50 market and must not be reported as one.
    """
    dd = d1_d2(forward, strike, sigma, t_years)
    if dd is None:
        return None
    return math.exp(-rate * t_years) * _norm_cdf(dd[1])


def peak_vol(forward: float, strike: float, t_years: float) -> float | None:
    """The sigma that MAXIMISES an out-of-the-money digital, or None if the
    price is monotone in sigma (in- or at-the-money).

    Setting vega to zero gives d1 = 0, hence

        sigma* = sqrt( 2 * ln(K/F) / T )

    which is real only when K > F. Verified numerically: at F=100, K=110,
    T=0.05 this returns 1.9525 and vega there is -2.4e-17.
    """
    if forward <= 0 or strike <= 0 or t_years < MIN_T_YEARS:
        return None
    if strike <= forward:
        return None                      # monotone: no interior maximum
    return math.sqrt(2.0 * math.log(strike / forward) / t_years)


def max_digital_price(forward: float, strike: float, t_years: float,
                      rate: float = 0.0) -> float:
    """The highest an OTM digital can be worth at ANY volatility.

    A genuinely useful bound on this exchange and not an obvious one. An
    out-of-the-money digital does NOT approach 1 as volatility rises -- more
    vol eventually drags the price back down, because the lognormal median
    falls away from the forward faster than the upper tail thickens. At
    F=100, K=110, T=0.05 the ceiling is 0.3312.

    A quote ABOVE this ceiling cannot be produced by any lognormal. That is a
    model-free statement about the quote, not a fitting failure, and it is
    the cheapest possible check that a strike is mispriced relative to its
    own moneyness and time to expiry.

    In- and at-the-money digitals are monotone decreasing in sigma, so their
    ceiling is the zero-vol limit of 1.0.
    """
    star = peak_vol(forward, strike, t_years)
    if star is None:
        return 1.0
    v = digital_call(forward, strike, star, t_years, rate)
    return 1.0 if v is None else v


def _bisect(f, lo: float, hi: float, tol: float, max_iter: int) -> float | None:
    f_lo, f_hi = f(lo), f(hi)
    if f_lo is None or f_hi is None or f_lo * f_hi > 0:
        return None
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        f_mid = f(mid)
        if f_mid is None:
            return None
        if abs(f_mid) < tol or (hi - lo) < tol:
            return mid
        if f_lo * f_mid <= 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)


def implied_vol_roots(price: float, forward: float, strike: float,
                      t_years: float, rate: float = 0.0, tol: float = 1e-10,
                      max_iter: int = 200) -> tuple[float | None, float | None]:
    """(low_root, high_root). DIGITAL IMPLIED VOL IS NOT UNIQUE.

    This is the central difference from a vanilla and it is easy to get
    wrong. For an out-of-the-money digital the price is HUMP-SHAPED in sigma:
    it goes to 0 as sigma -> 0 (the forward never reaches the strike) and
    ALSO to 0 as sigma -> infinity (the lognormal median collapses), peaking
    at `peak_vol` in between. So a quote below the peak has TWO implied vols,
    one either side, and a quote above the peak has none at all.

    In- and at-the-money digitals are monotone decreasing in sigma and have
    exactly one root, returned as the low one with None beside it.

    Returning both is the honest interface. Collapsing silently to one hides
    a real ambiguity in the data, and picking the wrong branch inverts the
    sign of every vega that follows.
    """
    if not (0.0 < price < 1.0) or forward <= 0 or strike <= 0:
        return None, None
    if t_years < MIN_T_YEARS:
        return None, None

    def f(s: float) -> float | None:
        v = digital_call(forward, strike, s, t_years, rate)
        return None if v is None else v - price

    star = peak_vol(forward, strike, t_years)
    if star is None or not (MIN_SIGMA < star < MAX_SIGMA):
        return _bisect(f, MIN_SIGMA, MAX_SIGMA, tol, max_iter), None

    if price > max_digital_price(forward, strike, t_years, rate):
        # Above the ceiling: no lognormal produces this quote at all.
        return None, None
    return (_bisect(f, MIN_SIGMA, star, tol, max_iter),
            _bisect(f, star, MAX_SIGMA, tol, max_iter))


def implied_vol(price: float, forward: float, strike: float, t_years: float,
                rate: float = 0.0, tol: float = 1e-10,
                max_iter: int = 200) -> float | None:
    """The LOW implied-vol root, or None if no sigma reproduces the price.

    The low branch is the conventional choice: it is the one continuous with
    the in-the-money side of the smile, so a surface built from it does not
    jump discontinuously as strikes cross the forward. Callers that need the
    ambiguity should use `implied_vol_roots`.
    """
    lo, _ = implied_vol_roots(price, forward, strike, t_years, rate, tol,
                              max_iter)
    return lo


def delta(forward: float, strike: float, sigma: float,
          t_years: float, rate: float = 0.0) -> float | None:
    """dPrice/dForward. A digital's delta is a spike at the strike, not a
    smooth ramp -- it peaks at the money and decays either side, which is why
    digitals are far harder to hedge than vanillas near expiry."""
    dd = d1_d2(forward, strike, sigma, t_years)
    if dd is None:
        return None
    _, d2 = dd
    return (math.exp(-rate * t_years) * _norm_pdf(d2)
            / (forward * sigma * math.sqrt(t_years)))


def vega(forward: float, strike: float, sigma: float,
         t_years: float, rate: float = 0.0) -> float | None:
    """dPrice/dSigma. CHANGES SIGN across the forward.

    More volatility pushes probability out of the middle and into both tails,
    so it RAISES an out-of-the-money digital and LOWERS an in-the-money one.
    A vanilla's vega is positive everywhere; assuming the same here is the
    single easiest way to misread a digital position, and it is why
    implied_vol uses bisection instead of Newton.
    """
    dd = d1_d2(forward, strike, sigma, t_years)
    if dd is None:
        return None
    d1, d2 = dd
    return -math.exp(-rate * t_years) * _norm_pdf(d2) * d1 / sigma


def gamma(forward: float, strike: float, sigma: float,
          t_years: float, rate: float = 0.0) -> float | None:
    """d2Price/dForward2."""
    dd = d1_d2(forward, strike, sigma, t_years)
    if dd is None:
        return None
    d1, d2 = dd
    vol_t = sigma * math.sqrt(t_years)
    return (-math.exp(-rate * t_years) * _norm_pdf(d2) * d1
            / (forward * forward * vol_t * vol_t))


def moneyness(forward: float, strike: float) -> float | None:
    """log(F/K). Zero at the money, positive when the strike is below the
    forward. Log rather than the ratio so the wings are symmetric, which is
    what makes a smile plot readable."""
    if forward <= 0 or strike <= 0:
        return None
    return math.log(forward / strike)


def years_between(now_ts: float, expiry_ts: float) -> float:
    """Time to expiry in years, floored at zero."""
    return max(0.0, (expiry_ts - now_ts) / SECONDS_PER_YEAR)
