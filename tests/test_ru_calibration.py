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


import json

from ru_calibration import calibrate, load_recording


def _row(ticker, ts, bid, ask, series=None):
    return {"ts": ts, "ticker": ticker,
            "series": series or ticker.split("-", 1)[0],
            "event_ticker": "E", "yes_bid_c": bid, "yes_ask_c": ask,
            "spread_c": ask - bid, "oi": 1000.0, "v24": 100.0}


def test_a_recording_loads_grouped_by_ticker_in_time_order(tmp_path):
    p = tmp_path / "rec.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in [
        _row("KXA-1", 3, 40, 42), _row("KXA-1", 1, 50, 52),
        _row("KXB-1", 2, 10, 12)]), encoding="utf-8")
    by_ticker = load_recording(p)
    assert set(by_ticker) == {"KXA-1", "KXB-1"}
    assert [r["ts"] for r in by_ticker["KXA-1"]] == [1, 3]


def test_calibration_reports_breaches_per_vertical(tmp_path):
    """A book that collapses 50c -> 5c and a flat one both stay within RU bounds."""
    p = tmp_path / "rec.jsonl"
    rows = []
    for ts, price in enumerate([50, 45, 30, 5], start=1):
        rows.append(_row("KXMLBGAME-X", ts, price - 1, price + 1,
                         series="KXMLBGAME"))
    for ts, price in enumerate([50, 50, 50, 50], start=1):
        rows.append(_row("KXMLBGAME-Y", ts, price - 1, price + 1,
                         series="KXMLBGAME"))
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    stats = calibrate(load_recording(p), horizon=3)
    assert "mlb_game" in stats
    assert stats["mlb_game"].n == 2
    assert stats["mlb_game"].breaches == 0


def test_a_ticker_with_too_short_a_path_is_skipped(tmp_path):
    p = tmp_path / "rec.jsonl"
    p.write_text(json.dumps(_row("KXMLBGAME-Z", 1, 49, 51,
                                 series="KXMLBGAME")), encoding="utf-8")
    stats = calibrate(load_recording(p), horizon=3)
    assert stats == {} or stats["mlb_game"].n == 0


def test_execution_stays_disabled_throughout_this_plan():
    """GLOBAL CONSTRAINT: nothing in Plan 1 may enable execution."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from agent.risk import RISK
    assert RISK.is_live() is False
