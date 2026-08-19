import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from ru_calibration import BreachStats, adverse_excursion, breach_stats


def test_adverse_excursion_is_the_worst_drawdown_for_a_yes_long():
    """Entered at 50c, the path dipped to 38c: 12c of adverse move."""
    assert adverse_excursion(50.0, [50.0, 46.0, 38.0, 61.0]) == pytest.approx(0.12)


def test_a_path_that_never_goes_against_you_has_zero_excursion():
    assert adverse_excursion(50.0, [50.0, 55.0, 70.0]) == 0.0


def test_the_no_side_measures_the_opposite_direction():
    """Short YES / long NO is hurt when the price RISES."""
    assert adverse_excursion(50.0, [50.0, 72.0], side="no") == pytest.approx(0.22)


def test_an_empty_path_has_no_measurable_excursion():
    assert adverse_excursion(50.0, []) == 0.0


def test_breach_rate_counts_positions_whose_move_exceeded_their_RU():
    """(realised adverse excursion, predicted RU) pairs."""
    obs = [(0.30, 0.20), (0.10, 0.20), (0.05, 0.20), (0.50, 0.20)]
    stats = breach_stats(obs, nominal=0.05)
    assert stats.n == 4
    assert stats.breaches == 2
    assert stats.rate == pytest.approx(0.5)
    assert stats.nominal == 0.05


def test_an_empty_sample_reports_no_rate_rather_than_zero():
    """Zero breaches out of zero observations is not a 0% breach rate."""
    stats = breach_stats([], nominal=0.05)
    assert stats.n == 0
    assert stats.rate is None
