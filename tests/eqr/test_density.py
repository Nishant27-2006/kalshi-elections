"""Day 4. A ladder of digitals is a CDF; one difference gives the density."""
import math

import pytest

from agent import digital
from eqr import density


def _lognormal_ladder(forward, sigma, t, strikes):
    """P(X >= K) under GBM -- a ladder with a KNOWN density."""
    return [digital.digital_call(forward, k, sigma, t) for k in strikes]


def test_pdf_is_first_difference_of_survival_function():
    pdf = density.pdf_from_cdf([10.0, 20.0, 30.0, 40.0], [0.9, 0.6, 0.25, 0.05])
    assert len(pdf) == 3
    assert [m for _, m in pdf] == pytest.approx([0.3, 0.35, 0.20], abs=1e-9)


def test_pdf_bucket_strikes_are_midpoints():
    pdf = density.pdf_from_cdf([10.0, 20.0, 30.0], [0.9, 0.6, 0.25])
    assert [k for k, _ in pdf] == pytest.approx([15.0, 25.0])


def test_unsorted_strikes_raise():
    with pytest.raises(ValueError):
        density.pdf_from_cdf([30.0, 10.0, 20.0], [0.2, 0.9, 0.6])


def test_moments_recover_a_known_lognormal():
    F, sigma, T = 100.0, 0.3, 1.0
    strikes = [float(k) for k in range(20, 401, 2)]
    pdf = density.pdf_from_cdf(strikes, _lognormal_ladder(F, sigma, T, strikes))
    m = density.moments(pdf)
    assert m["mass"] == pytest.approx(1.0, abs=0.02)
    assert m["mean"] == pytest.approx(F, rel=0.03)
    assert m["var"] == pytest.approx(F * F * (math.exp(sigma ** 2 * T) - 1.0), rel=0.10)
    assert m["skew"] > 0.0     # lognormal is right-skewed


def test_negative_mass_flags_a_monotonicity_violation():
    pdf = density.pdf_from_cdf([10.0, 20.0, 30.0], [0.5, 0.6, 0.1])
    bad = density.negative_mass(pdf)
    assert len(bad) == 1
    assert bad[0][1] < 0


def test_clean_ladder_has_no_negative_mass():
    strikes = [float(k) for k in range(50, 200, 5)]
    pdf = density.pdf_from_cdf(strikes, _lognormal_ladder(100.0, 0.4, 0.5, strikes))
    assert density.negative_mass(pdf) == []


def test_mass_captured_is_below_one_for_a_truncated_ladder():
    """Drill Q4: a ladder spanning 90-110 cannot hold all the mass."""
    strikes = [float(k) for k in range(90, 111)]
    m = density.moments(
        density.pdf_from_cdf(strikes, _lognormal_ladder(100.0, 0.6, 1.0, strikes)))
    assert m["mass"] < 0.5


def test_implied_move_brackets_the_centre():
    strikes = [float(k) for k in range(20, 401, 2)]
    pdf = density.pdf_from_cdf(strikes, _lognormal_ladder(100.0, 0.3, 1.0, strikes))
    lo, hi = density.implied_move(pdf, confidence=0.68)
    assert lo < 100.0 < hi


def test_implied_move_returns_none_when_mass_is_insufficient():
    assert density.implied_move([(10.0, 0.1), (20.0, 0.1)], confidence=0.68) is None
