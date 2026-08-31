"""Day 1. These fail until eqr/gbm.py is written. THE AUTHOR writes gbm.py.

The load-bearing test is test_mc_converges_to_closed_form: an independent
Monte-Carlo implementation agreeing with agent/digital.py's closed form is
the only evidence that either one is right.
"""
import math

import numpy as np
import pytest

from agent import digital
from eqr import gbm


def test_brownian_paths_shape_and_origin():
    W = gbm.brownian_paths(n_paths=500, n_steps=50, t_years=1.0, seed=7)
    assert W.shape == (500, 51)
    assert np.allclose(W[:, 0], 0.0)


def test_brownian_variance_grows_linearly_in_time():
    W = gbm.brownian_paths(n_paths=200_000, n_steps=4, t_years=1.0, seed=11)
    for k, t in enumerate([0.25, 0.5, 0.75, 1.0], start=1):
        assert W[:, k].var() == pytest.approx(t, rel=0.02)


def test_brownian_increments_are_independent():
    W = gbm.brownian_paths(n_paths=200_000, n_steps=2, t_years=1.0, seed=13)
    d1 = W[:, 1] - W[:, 0]
    d2 = W[:, 2] - W[:, 1]
    assert abs(np.corrcoef(d1, d2)[0, 1]) < 0.01


def test_quadratic_variation_converges_to_T():
    """Drill question 2, made executable."""
    T = 1.0
    W = gbm.brownian_paths(n_paths=64, n_steps=20_000, t_years=T, seed=3)
    qv = (np.diff(W, axis=1) ** 2).sum(axis=1)
    assert qv.mean() == pytest.approx(T, rel=0.02)


def test_gbm_terminal_is_a_martingale():
    """E[S(T)] == F. Drill question 3."""
    F = 100.0
    S = gbm.gbm_terminal(forward=F, sigma=0.6, t_years=0.5,
                         n_paths=400_000, seed=17)
    se = S.std() / math.sqrt(len(S))
    assert abs(S.mean() - F) < 4.0 * se


def test_gbm_terminal_is_lognormal_with_right_variance():
    F, sigma, T = 100.0, 0.4, 2.0
    S = gbm.gbm_terminal(F, sigma, T, n_paths=400_000, seed=19)
    logs = np.log(S / F)
    assert logs.mean() == pytest.approx(-0.5 * sigma ** 2 * T, abs=0.01)
    assert logs.var() == pytest.approx(sigma ** 2 * T, rel=0.02)


@pytest.mark.parametrize("strike", [80.0, 100.0, 125.0])
def test_mc_converges_to_closed_form(strike):
    """THE GATE. Two independent implementations must agree."""
    F, sigma, T = 100.0, 0.5, 0.25
    mc, se = gbm.mc_digital_call(F, strike, sigma, T,
                                 n_paths=500_000, seed=23)
    closed = digital.digital_call(F, strike, sigma, T)
    assert closed is not None
    assert abs(mc - closed) < 4.0 * se, (
        f"MC {mc:.5f} vs closed form {closed:.5f}, se {se:.5f}")


def test_mc_standard_error_matches_bernoulli_formula():
    """Drill question 5, made executable."""
    F, K, sigma, T, n = 100.0, 105.0, 0.5, 0.25, 200_000
    price, se = gbm.mc_digital_call(F, K, sigma, T, n_paths=n, seed=29)
    assert se == pytest.approx(math.sqrt(price * (1.0 - price) / n), rel=0.05)


def test_seed_is_reproducible():
    a = gbm.mc_digital_call(100.0, 100.0, 0.4, 1.0, n_paths=10_000, seed=5)
    b = gbm.mc_digital_call(100.0, 100.0, 0.4, 1.0, n_paths=10_000, seed=5)
    assert a == b
