"""Day 2. The two-root problem, made executable."""
import pytest

from agent import digital
from eqr import surface


def test_surface_point_recovers_the_vol_it_was_priced_with():
    F, T, sigma = 100.0, 0.25, 0.45
    quotes = [(k, digital.digital_call(F, k, sigma, T))
              for k in (85.0, 95.0, 100.0, 110.0)]
    pts = surface.build_surface(F, T, quotes)
    assert len(pts) == 4
    for p in pts:
        assert p.invertible
        assert p.iv_low == pytest.approx(sigma, abs=1e-4)


def test_out_of_the_money_quote_has_two_roots():
    """K far above F: price is non-monotone in sigma, so two vols fit."""
    F, K, T = 100.0, 130.0, 0.25
    peak = digital.peak_vol(F, K, T)
    assert peak is not None
    price = 0.5 * digital.max_digital_price(F, K, T)
    p = surface.build_surface(F, T, [(K, price)])[0]
    assert p.iv_low is not None and p.iv_high is not None
    assert p.iv_low < peak < p.iv_high
    assert digital.digital_call(F, K, p.iv_low, T) == pytest.approx(price, abs=1e-6)
    assert digital.digital_call(F, K, p.iv_high, T) == pytest.approx(price, abs=1e-6)


def test_in_the_money_quote_has_one_root():
    """K below F: price IS monotone in sigma, so iv_high must be None."""
    F, K, T, sigma = 100.0, 80.0, 0.25, 0.5
    price = digital.digital_call(F, K, sigma, T)
    p = surface.build_surface(F, T, [(K, price)])[0]
    assert p.iv_low == pytest.approx(sigma, abs=1e-4)
    assert p.iv_high is None


def test_quote_above_the_attainable_maximum_is_not_invertible():
    F, K, T = 100.0, 130.0, 0.25
    mx = digital.max_digital_price(F, K, T)
    p = surface.build_surface(F, T, [(K, min(0.999, mx + 0.05))])[0]
    assert p.invertible is False
    assert p.iv_low is None


def test_moneyness_sign_convention():
    pts = surface.build_surface(100.0, 0.25, [(80.0, 0.9), (125.0, 0.1)])
    assert pts[0].moneyness > 0     # strike below forward
    assert pts[1].moneyness < 0


def test_smile_slope_is_none_with_fewer_than_two_invertible_points():
    assert surface.smile_slope([]) is None


def test_flat_vol_gives_zero_smile_slope():
    F, T, sigma = 100.0, 0.25, 0.4
    quotes = [(k, digital.digital_call(F, k, sigma, T))
              for k in (90.0, 95.0, 105.0, 110.0)]
    pts = surface.build_surface(F, T, quotes)
    assert surface.smile_slope(pts) == pytest.approx(0.0, abs=1e-3)
