"""Day 8. Removing the factor bet you did not know you were making."""
import pytest

from eqr import neutralize


def test_demean_by_group_removes_group_means():
    out = neutralize.demean_by_group([1.0, 3.0, 10.0, 20.0], ["A", "A", "B", "B"])
    assert out == pytest.approx([-1.0, 1.0, -5.0, 5.0])


def test_demean_by_group_propagates_none():
    out = neutralize.demean_by_group([1.0, None, 3.0], ["A", "A", "A"])
    assert out[1] is None
    assert out[0] == pytest.approx(-1.0)
    assert out[2] == pytest.approx(1.0)


def test_zscore_has_zero_mean_and_unit_std():
    clean = [x for x in neutralize.zscore([1.0, 2.0, 3.0, 4.0, 5.0]) if x is not None]
    assert sum(clean) == pytest.approx(0.0, abs=1e-12)
    n = len(clean)
    assert sum(x * x for x in clean) / (n - 1) == pytest.approx(1.0, abs=1e-9)


def test_zscore_returns_all_none_for_zero_variance():
    assert neutralize.zscore([5.0, 5.0, 5.0]) == [None, None, None]


def test_regress_out_removes_a_perfectly_collinear_factor():
    resid = neutralize.regress_out([2.0, 4.0, 6.0, 8.0], [[1.0, 2.0, 3.0, 4.0]])
    assert all(abs(r) < 1e-9 for r in resid)


def test_regress_out_leaves_an_orthogonal_signal_alone():
    vals = [1.0, -1.0, 1.0, -1.0]
    resid = neutralize.regress_out(vals, [[1.0, 1.0, -1.0, -1.0]])
    assert resid == pytest.approx(vals, abs=1e-9)


def test_group_dummies_and_demeaning_agree():
    """Drill Q2 made executable."""
    vals = [1.0, 3.0, 10.0, 20.0]
    by_demean = neutralize.demean_by_group(vals, ["A", "A", "B", "B"])
    by_regress = neutralize.regress_out(
        vals, [[1.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 1.0]])
    assert by_regress == pytest.approx(by_demean, abs=1e-9)
