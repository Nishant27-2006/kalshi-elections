"""Day 4b. Puts on an exchange that lists none.

The gate is test_two_constructions_of_the_same_put_agree: the density
expectation and the digital-strip integral must land on the same number.

Tolerances here were calibrated against Black-Scholes before this file
shipped. At 2-point strike spacing both constructions land within 0.13% of
the closed form, so the 1% allowances below are not generous guesses.
"""
import math

import pytest

from agent import digital
from eqr import puts

# --- a tiny hand-computable density -------------------------------------
# mean = 10(.2) + 20(.5) + 30(.3) = 21
PDF = [(10.0, 0.2), (20.0, 0.5), (30.0, 0.3)]
PDF_MEAN = 21.0


def _lognormal_ladder(F, sigma, T, strikes):
    return [digital.digital_call(F, k, sigma, T) for k in strikes]


def _pdf_from(strikes, p_ge):
    return [(0.5 * (strikes[i] + strikes[i + 1]), p_ge[i] - p_ge[i + 1])
            for i in range(len(strikes) - 1)]


def _bs_put(F, K, sigma, T):
    d1, d2 = digital.d1_d2(F, K, sigma, T)
    n = digital._norm_cdf
    return K * n(-d2) - F * n(-d1)


# --- the digital put is already listed ----------------------------------

def test_digital_put_is_the_complement_of_the_yes_leg():
    assert puts.digital_put(0.62) == pytest.approx(0.38)
    assert puts.digital_put(0.0) == pytest.approx(1.0)
    assert puts.digital_put(1.0) == pytest.approx(0.0)


def test_digital_put_rejects_a_probability_outside_the_unit_interval():
    with pytest.raises(ValueError):
        puts.digital_put(1.4)
    with pytest.raises(ValueError):
        puts.digital_put(-0.01)


# --- the vanilla put, built from the density ----------------------------

def test_vanilla_put_hand_computed():
    # (25-10)*0.2 + (25-20)*0.5 + 0*0.3 = 3.0 + 2.5 = 5.5
    assert puts.vanilla_put(PDF, 25.0) == pytest.approx(5.5, abs=1e-12)


def test_vanilla_call_hand_computed():
    # 0 + 0 + (30-25)*0.3 = 1.5
    assert puts.vanilla_call(PDF, 25.0) == pytest.approx(1.5, abs=1e-12)


def test_put_below_every_outcome_is_worthless():
    assert puts.vanilla_put(PDF, 5.0) == pytest.approx(0.0, abs=1e-12)


def test_call_above_every_outcome_is_worthless():
    assert puts.vanilla_call(PDF, 40.0) == pytest.approx(0.0, abs=1e-12)


def test_empty_density_prices_nothing():
    assert puts.vanilla_put([], 25.0) is None
    assert puts.vanilla_call([], 25.0) is None
    assert puts.parity_error([], 25.0, 100.0) is None


# --- parity -------------------------------------------------------------

def test_parity_is_exact_against_the_densitys_own_mean():
    """Arithmetic, not evidence -- but if this fails your sums are wrong."""
    assert puts.parity_error(PDF, 25.0, PDF_MEAN) == pytest.approx(0.0, abs=1e-12)
    assert puts.parity_error(PDF, 12.0, PDF_MEAN) == pytest.approx(0.0, abs=1e-12)


def test_parity_error_measures_the_gap_to_a_different_forward():
    # C - P = 1.5 - 5.5 = -4.0 ; F - K = 22 - 25 = -3.0 ; error = -1.0
    assert puts.parity_error(PDF, 25.0, 22.0) == pytest.approx(-1.0, abs=1e-12)


# --- against the closed form -------------------------------------------

@pytest.mark.parametrize("strike", [80.0, 100.0, 120.0])
def test_vanilla_put_matches_black_scholes_on_a_lognormal_ladder(strike):
    F, sigma, T = 100.0, 0.3, 1.0
    strikes = [float(k) for k in range(2, 401, 2)]
    pdf = _pdf_from(strikes, _lognormal_ladder(F, sigma, T, strikes))
    got = puts.vanilla_put(pdf, strike)
    assert got == pytest.approx(_bs_put(F, strike, sigma, T), rel=0.01)


# --- THE GATE -----------------------------------------------------------

@pytest.mark.parametrize("strike", [80.0, 100.0, 120.0])
def test_two_constructions_of_the_same_put_agree(strike):
    """Density expectation vs integral of the digital strip."""
    F, sigma, T = 100.0, 0.3, 1.0
    strikes = [float(k) for k in range(2, 401, 2)]
    p_ge = _lognormal_ladder(F, sigma, T, strikes)
    by_density = puts.vanilla_put(_pdf_from(strikes, p_ge), strike)
    by_strip = puts.put_from_digitals(strikes, p_ge, strike)
    assert by_density is not None and by_strip is not None
    assert by_strip == pytest.approx(by_density, rel=0.01)


def test_put_from_digitals_needs_rungs_below_the_strike():
    assert puts.put_from_digitals([50.0, 60.0], [0.9, 0.8], 10.0) is None


def test_put_from_digitals_ignores_rungs_above_the_strike():
    """Adding rungs above K must not change a put struck at K."""
    F, sigma, T = 100.0, 0.3, 1.0
    short = [float(k) for k in range(2, 121, 2)]
    long_ = [float(k) for k in range(2, 401, 2)]
    a = puts.put_from_digitals(short, _lognormal_ladder(F, sigma, T, short), 90.0)
    b = puts.put_from_digitals(long_, _lognormal_ladder(F, sigma, T, long_), 90.0)
    assert a == pytest.approx(b, rel=1e-9)


def test_a_truncated_ladder_understates_a_deep_put():
    """Mass you cannot see is value you cannot price. Know which way it errs."""
    F, sigma, T = 100.0, 0.6, 1.0
    wide = [float(k) for k in range(2, 601, 2)]
    narrow = [float(k) for k in range(60, 141, 2)]
    pw = puts.vanilla_put(_pdf_from(wide, _lognormal_ladder(F, sigma, T, wide)), 120.0)
    pn = puts.vanilla_put(_pdf_from(narrow, _lognormal_ladder(F, sigma, T, narrow)), 120.0)
    assert pn < pw
    assert not math.isclose(pn, pw, rel_tol=0.05)
