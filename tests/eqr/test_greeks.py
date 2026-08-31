"""Day 3. Finite-difference Greeks must reproduce the closed forms."""
import pytest

from agent import digital
from eqr import greeks


@pytest.mark.parametrize("strike", [90.0, 100.0, 115.0])
def test_fd_delta_matches_closed_form(strike):
    F, sigma, T = 100.0, 0.5, 0.25
    closed = digital.delta(F, strike, sigma, T)
    assert closed is not None
    assert greeks.fd_delta(F, strike, sigma, T) == pytest.approx(closed, rel=0.05)


@pytest.mark.parametrize("strike", [85.0, 120.0])
def test_fd_vega_matches_closed_form(strike):
    F, sigma, T = 100.0, 0.5, 0.25
    closed = digital.vega(F, strike, sigma, T)
    assert closed is not None
    assert greeks.fd_vega(F, strike, sigma, T) == pytest.approx(closed, rel=0.08)


def test_vega_is_negative_in_the_money_and_positive_out():
    """Drill Q3. THE digital-specific fact."""
    F, sigma, T = 100.0, 0.5, 0.25
    assert greeks.vega_sign(F, 80.0, sigma, T) == -1
    assert greeks.vega_sign(F, 130.0, sigma, T) == +1


def test_vega_vanishes_at_the_peak_vol_strike():
    F, K, T = 100.0, 130.0, 0.25
    pk = digital.peak_vol(F, K, T)
    assert pk is not None
    assert greeks.vega_sign(F, K, pk, T) == 0


def test_common_random_numbers_are_used():
    """Same seed must give EXACTLY the same number, or randoms are leaking."""
    a = greeks.fd_delta(100.0, 105.0, 0.5, 0.25, seed=41)
    b = greeks.fd_delta(100.0, 105.0, 0.5, 0.25, seed=41)
    assert a == b
