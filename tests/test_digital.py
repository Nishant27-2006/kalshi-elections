"""Tests for digital-option Black-Scholes.

The round-trip is the load-bearing one: price a digital from a known sigma,
then recover that sigma from the price. An implementation that cannot
recover a sigma it just used is wrong, and this must be provable without any
market data or API key.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent.digital import (SECONDS_PER_YEAR, d1_d2, delta, digital_call,
                           gamma, implied_vol, implied_vol_roots,
                           max_digital_price, moneyness, peak_vol, vega,
                           years_between)


# ------------------------------------------------------------ round trip

@pytest.mark.parametrize("sigma", [0.10, 0.25, 0.60, 1.20, 3.00])
@pytest.mark.parametrize("k", [80.0, 95.0, 100.0, 110.0, 140.0])
def test_implied_vol_recovers_the_sigma_that_priced_the_option(sigma, k):
    """THE TEST EVERYTHING ELSE RESTS ON: price from a known sigma, then
    invert, and land back where you started.

    Two real properties of digitals shape what can be asserted, and neither
    is a defect:

    1. NON-UNIQUENESS. An out-of-the-money digital is hump-shaped in sigma,
       so a price below the peak has TWO implied vols. The true sigma must be
       one of them -- demanding it be the low one would be demanding the
       wrong answer half the time.
    2. SATURATION. Far from the money the price underflows to exactly 0.0 or
       1.0 in float. A saturated quote carries no information about sigma,
       and inventing one from it would be the worst kind of fabricated
       number. None is the correct answer there.
    """
    f, t = 100.0, 0.05
    p = digital_call(f, k, sigma, t)
    assert p is not None

    if not (0.0 < p < 1.0):
        # Saturated: no sigma is recoverable, and the code must say so.
        assert implied_vol(p, f, k, t) is None
        return

    lo, hi = implied_vol_roots(p, f, k, t)
    roots = [r for r in (lo, hi) if r is not None]
    assert roots, f"no sigma recovered for K={k}, sigma={sigma}, price={p:.6g}"

    # Tolerance scales with how flat the price is in sigma there. When the
    # option is worth 1e-5, a huge range of sigmas produce the same quote to
    # float precision -- that is the data's limit, not the solver's.
    tol = 1e-4 if 1e-3 < p < 1 - 1e-3 else 5e-2
    assert any(abs(r - sigma) < tol for r in roots),         f"sigma={sigma} not among recovered {roots} (price {p:.6g})"


def test_an_otm_digital_has_a_hard_price_ceiling_no_volatility_can_beat():
    """THE NON-OBVIOUS RESULT. An out-of-the-money digital does NOT approach
    1 as volatility rises. More vol drags the lognormal median away from the
    forward faster than it thickens the upper tail, so the price peaks and
    then FALLS. At F=100, K=110, T=0.05 the ceiling is 0.3312 -- no sigma,
    however large, prices that strike above it.

    A live quote above this ceiling is inconsistent with every lognormal, and
    that is the cheapest mispricing check available: it needs no fitting, no
    smile, and no view."""
    f, k, t = 100.0, 110.0, 0.05
    ceiling = max_digital_price(f, k, t)
    assert ceiling == pytest.approx(0.3312, abs=1e-3)
    for s in (0.1, 0.5, 1.0, star := peak_vol(f, k, t), 5.0, 20.0, 49.0):
        assert digital_call(f, k, s, t) <= ceiling + 1e-12
    assert star == pytest.approx(math.sqrt(2 * math.log(k / f) / t))
    # a quote above the ceiling has no implied vol at all
    assert implied_vol(ceiling + 0.05, f, k, t) is None


def test_an_in_the_money_digital_is_monotone_and_has_one_root():
    """K < F has no interior peak, so the price falls monotonically from 1 to
    0 and the inversion is unambiguous."""
    f, k, t = 100.0, 90.0, 0.05
    assert peak_vol(f, k, t) is None
    assert max_digital_price(f, k, t) == 1.0
    prices = [digital_call(f, k, s, t) for s in (0.05, 0.5, 2.0, 10.0)]
    assert all(a > b for a, b in zip(prices, prices[1:]))
    lo, hi = implied_vol_roots(prices[1], f, k, t)
    assert lo == pytest.approx(0.5, abs=1e-6)
    assert hi is None, "a monotone price has exactly one root"


def test_both_roots_reprice_to_the_same_quote():
    """The two branches are genuinely both solutions -- this is ambiguity in
    the data, not an artefact of the solver."""
    f, k, t = 100.0, 110.0, 0.05
    price = 0.25
    lo, hi = implied_vol_roots(price, f, k, t)
    assert lo is not None and hi is not None and hi > lo
    assert digital_call(f, k, lo, t) == pytest.approx(price, abs=1e-8)
    assert digital_call(f, k, hi, t) == pytest.approx(price, abs=1e-8)


def test_the_price_is_exactly_the_normal_cdf_of_d2():
    """At zero rates the digital IS N(d2) -- not proportional to it, equal to
    it. This is why a Kalshi quote can be read directly as a probability."""
    f, k, s, t = 100.0, 110.0, 0.6, 0.05
    d1, d2 = d1_d2(f, k, s, t)
    expected = 0.5 * (1 + math.erf(d2 / math.sqrt(2)))
    assert digital_call(f, k, s, t) == pytest.approx(expected)


def test_d1_and_d2_differ_by_exactly_sigma_root_t():
    f, k, s, t = 100.0, 90.0, 0.4, 0.25
    d1, d2 = d1_d2(f, k, s, t)
    assert d1 - d2 == pytest.approx(s * math.sqrt(t))


# ------------------------------------------------------- monotonicity

def test_the_price_falls_as_the_strike_rises():
    """P(X >= K) must be non-increasing in K. This is the same no-arbitrage
    constraint the ladder scanner checks against live quotes -- if the model
    itself violated it, the scanner would flag the model."""
    f, s, t = 100.0, 0.5, 0.05
    prices = [digital_call(f, k, s, t) for k in range(70, 141, 5)]
    assert all(a >= b for a, b in zip(prices, prices[1:]))


def test_a_far_out_strike_is_worth_almost_nothing_and_a_far_in_one_almost_all():
    f, s, t = 100.0, 0.5, 0.05
    assert digital_call(f, 1000.0, s, t) < 0.01
    assert digital_call(f, 1.0, s, t) > 0.99


# --------------------------------------------------------- vega sign

def test_vega_changes_sign_across_the_forward():
    """THE TRAP THIS PINS. More vol pushes probability out of the middle into
    BOTH tails, so it raises an out-of-the-money digital and LOWERS an
    in-the-money one. A vanilla's vega is positive everywhere. Assuming the
    same here is the easiest way to misread a digital position, and it is why
    implied_vol uses bisection rather than Newton."""
    f, s, t = 100.0, 0.5, 0.05
    assert vega(f, 130.0, s, t) > 0, "OTM digital gains from more vol"
    assert vega(f, 70.0, s, t) < 0, "ITM digital loses from more vol"


def test_raising_vol_really_does_move_the_price_the_way_vega_says():
    """Vega is a derivative; this checks it against an actual reprice, so a
    sign error in the closed form cannot pass unnoticed."""
    f, t = 100.0, 0.05
    for k, direction in ((130.0, 1), (70.0, -1)):
        lo = digital_call(f, k, 0.50, t)
        hi = digital_call(f, k, 0.55, t)
        assert (hi - lo) * direction > 0


# ----------------------------------------------------------- degenerate

def test_degenerate_inputs_return_none_not_a_plausible_number():
    """A zero-time or zero-vol contract is not a 50/50 market. Returning 0.5
    there would look like a real quote and silently poison a backtest."""
    assert digital_call(100.0, 100.0, 0.5, 0.0) is None
    assert digital_call(100.0, 100.0, 0.0, 0.05) is None
    assert digital_call(0.0, 100.0, 0.5, 0.05) is None
    assert digital_call(100.0, 0.0, 0.5, 0.05) is None
    assert d1_d2(100.0, 100.0, 0.5, 0.0) is None


def test_an_impossible_price_yields_no_implied_vol():
    """Prices at or outside the bounds are not consistent with any lognormal.
    None says so; a number would invent a belief the market never expressed."""
    assert implied_vol(0.0, 100.0, 110.0, 0.05) is None
    assert implied_vol(1.0, 100.0, 110.0, 0.05) is None
    assert implied_vol(1.5, 100.0, 110.0, 0.05) is None
    assert implied_vol(-0.2, 100.0, 110.0, 0.05) is None


def test_a_price_no_sigma_can_reach_yields_none():
    """A quote above an OTM digital's ceiling is not consistent with any
    lognormal, and the right answer is None rather than a fitted number.

    Note the ITM side is NOT such a case: a deep in-the-money digital quoted
    at 1c is perfectly reachable, at an enormous sigma (about 24.6 for
    F=100, K=10, T=0.05). Treating that as unreachable was an error in an
    earlier version of this test."""
    f, k, t = 100.0, 110.0, 0.05
    assert implied_vol(max_digital_price(f, k, t) + 0.05, f, k, t) is None
    # ...and the ITM case really is reachable
    assert implied_vol(0.01, 100.0, 10.0, 0.05) is not None


# ------------------------------------------------------------- greeks

def test_delta_is_positive_and_peaks_at_the_money():
    """A digital's delta is a spike, not a ramp -- which is why they are far
    harder to hedge near expiry than vanillas."""
    f, s, t = 100.0, 0.5, 0.05
    atm = delta(f, 100.0, s, t)
    wing = delta(f, 200.0, s, t)
    assert atm > 0 and wing > 0
    assert atm > wing * 10


def test_delta_matches_a_numerical_bump():
    f, k, s, t = 100.0, 115.0, 0.5, 0.05
    h = 1e-4
    num = (digital_call(f + h, k, s, t) - digital_call(f - h, k, s, t)) / (2 * h)
    assert delta(f, k, s, t) == pytest.approx(num, rel=1e-4)


def test_vega_matches_a_numerical_bump():
    f, k, t = 100.0, 115.0, 0.05
    s, h = 0.5, 1e-6
    num = (digital_call(f, k, s + h, t) - digital_call(f, k, s - h, t)) / (2 * h)
    assert vega(f, k, s, t) == pytest.approx(num, rel=1e-3)


def test_gamma_matches_a_numerical_second_bump():
    f, k, s, t = 100.0, 115.0, 0.5, 0.05
    h = 1e-3
    num = (digital_call(f + h, k, s, t) - 2 * digital_call(f, k, s, t)
           + digital_call(f - h, k, s, t)) / (h * h)
    assert gamma(f, k, s, t) == pytest.approx(num, rel=1e-3)


def test_greeks_return_none_on_degenerate_input():
    for fn in (delta, vega, gamma):
        assert fn(100.0, 110.0, 0.5, 0.0) is None


# ------------------------------------------------------------ utilities

def test_moneyness_is_zero_at_the_money_and_signed_either_side():
    assert moneyness(100.0, 100.0) == pytest.approx(0.0)
    assert moneyness(100.0, 90.0) > 0, "strike below forward is in the money"
    assert moneyness(100.0, 110.0) < 0


def test_time_to_expiry_never_goes_negative():
    """An expired contract has zero time left, not negative time. A negative
    T makes sqrt(T) complex and every formula downstream nonsense."""
    assert years_between(100.0, 50.0) == 0.0
    assert years_between(0.0, SECONDS_PER_YEAR) == pytest.approx(1.0)
