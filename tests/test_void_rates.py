import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.void_rates import (DEFAULT_VOID_RATE, VOID_RATES,
                              vertical_for_series, void_rate_for_series)


def test_measured_rates_match_the_spec_table():
    """These are measured from the settled feed, not assumed. Spec section 3.2."""
    assert VOID_RATES["mlb_game"] == 0.005
    assert VOID_RATES["esports_series"] == 0.099
    assert VOID_RATES["scheduled_data"] == 0.0


def test_series_maps_to_its_vertical():
    assert vertical_for_series("KXMLBGAME") == "mlb_game"
    assert vertical_for_series("KXCS2GAME") == "esports_series"
    assert vertical_for_series("KXBTCD") == "scheduled_data"


def test_an_unmapped_series_returns_none_not_a_guess():
    """Invariant K: no invented data. An unknown series has no measured rate."""
    assert vertical_for_series("KXTOTALLYUNKNOWN") is None
    assert void_rate_for_series("KXTOTALLYUNKNOWN") is None


def test_the_conservative_default_is_the_worst_measured_rate():
    """A caller choosing to proceed without a measurement must not get an
    optimistic number. The default is the worst rate we have observed."""
    assert DEFAULT_VOID_RATE == max(VOID_RATES.values())
