"""Brownian motion, GBM, and a Monte-Carlo digital pricer.

>>> THE AUTHOR WRITES THE BODIES. <<<

Signatures and contracts are fixed here so the delivered tests compile.
Every `raise NotImplementedError` below is yours to replace.

Pure and I/O-free by design, so tests run with no API key.
"""
from __future__ import annotations

import numpy as np


def brownian_paths(n_paths: int, n_steps: int, t_years: float,
                   seed: int) -> np.ndarray:
    """Standard Brownian motion on [0, t_years], shape (n_paths, n_steps+1).

    W[:, 0] must be exactly 0. Increments are iid N(0, dt) with
    dt = t_years / n_steps. Use np.random.default_rng(seed).
    """
    raise NotImplementedError("Day 1: yours to write")


def gbm_terminal(forward: float, sigma: float, t_years: float,
                 n_paths: int, seed: int) -> np.ndarray:
    """S(T) under zero-drift GBM: F * exp(-0.5*sigma^2*T + sigma*W(T)).

    Returns shape (n_paths,). Only the terminal value is needed to price a
    European payoff, so do not simulate a full path here -- one normal draw
    per path is both correct and ~n_steps times faster.
    """
    raise NotImplementedError("Day 1: yours to write")


def mc_digital_call(forward: float, strike: float, sigma: float,
                    t_years: float, n_paths: int,
                    seed: int) -> tuple[float, float]:
    """(price, standard_error) for a cash-or-nothing digital call, r = 0.

    price = mean of the indicator 1{S(T) >= strike}.
    standard_error = sqrt(p*(1-p)/n) -- the Bernoulli SE from drill Q5, not
    the sample std of the indicator divided by sqrt(n) with ddof=1. They
    agree to O(1/n); use the closed form so the test comparing them is
    checking your understanding rather than a numerical accident.
    """
    raise NotImplementedError("Day 1: yours to write")
