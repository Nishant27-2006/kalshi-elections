"""Day 6. IC and quantile spread. The t-stat/deflated-Sharpe tests PASS
already -- those two functions are delivered."""
import pytest

from eqr import evaluate


def test_ic_is_one_for_a_perfectly_ranked_signal():
    assert evaluate.information_coefficient(
        [1.0, 2.0, 3.0, 4.0, 5.0], [0.01, 0.02, 0.03, 0.04, 0.05]
    ) == pytest.approx(1.0)


def test_ic_is_minus_one_for_a_perfectly_inverted_signal():
    assert evaluate.information_coefficient(
        [1.0, 2.0, 3.0, 4.0, 5.0], [0.05, 0.04, 0.03, 0.02, 0.01]
    ) == pytest.approx(-1.0)


def test_ic_drops_none_pairs():
    # only (1.0, 0.01) and (4.0, 0.04) survive -> 2 pairs -> None
    assert evaluate.information_coefficient(
        [1.0, None, 3.0, 4.0], [0.01, 0.02, None, 0.04]) is None


def test_ic_uses_average_ranks_for_ties():
    ic = evaluate.information_coefficient([5.0, 5.0, 9.0], [0.01, 0.02, 0.03])
    assert ic is not None
    assert ic == pytest.approx(0.8660254, abs=1e-6)


def test_quantile_spread_is_positive_for_a_good_signal():
    assert evaluate.quantile_spread(
        list(range(20)), [i * 0.001 for i in range(20)], n_q=5) > 0


def test_quantile_spread_returns_none_when_too_few_names():
    assert evaluate.quantile_spread([1.0, 2.0], [0.1, 0.2], n_q=5) is None


def test_ic_t_stat_delivered_matches_hand_computation():
    assert evaluate.ic_t_stat([0.02, 0.04, 0.00, 0.06]) == pytest.approx(
        2.3237900, abs=1e-6)


def test_deflated_sharpe_penalises_many_trials():
    assert evaluate.deflated_sharpe(2.0, n_trials=1000, n_obs=250) < 2.0
    assert (evaluate.deflated_sharpe(2.0, 1000, 250)
            < evaluate.deflated_sharpe(2.0, 10, 250))
