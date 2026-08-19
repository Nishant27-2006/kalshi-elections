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


def test_a_mid_priced_book_cannot_breach_its_own_RU(tmp_path):
    """At 51c the predicted RU (0.5324) EXCEEDS the maximum possible loss
    (0.5100), so neither a collapse to 5c nor a flat book can breach. This is
    a property of SIGMA_MULTIPLE=2.0, not of the data."""
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


def test_a_collapsing_favourite_breaches_its_RU(tmp_path):
    """Breaches live at the EXTREMES. A 91c favourite that goes to 2c realises
    0.89 of adverse excursion against a predicted RU of 0.5238, so it breaches
    -- and this is the only test that proves calibrate() compares realised
    against predicted in that order rather than the reverse."""
    p = tmp_path / "rec.jsonl"
    rows = []
    for ts, price in enumerate([91, 60, 20, 2], start=1):
        rows.append(_row("KXMLBGAME-F", ts, price - 1, price + 1,
                         series="KXMLBGAME"))
    for ts, price in enumerate([50, 50, 50, 50], start=1):
        rows.append(_row("KXMLBGAME-Y", ts, price - 1, price + 1,
                         series="KXMLBGAME"))
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    stats = calibrate(load_recording(p), horizon=3)
    assert stats["mlb_game"].n == 2
    assert stats["mlb_game"].breaches == 1
    assert stats["mlb_game"].rate == 0.5


def test_a_ticker_with_too_short_a_path_is_skipped(tmp_path):
    p = tmp_path / "rec.jsonl"
    p.write_text(json.dumps(_row("KXMLBGAME-Z", 1, 49, 51,
                                 series="KXMLBGAME")), encoding="utf-8")
    stats = calibrate(load_recording(p), horizon=3)
    assert stats == {}, "a ticker with no path must not appear in the output at all"


def test_an_unmeasured_series_falls_back_to_the_worst_known_void_rate(tmp_path):
    """A series with no measured void rate is NOT skipped and NOT guessed at:
    it is bucketed as 'unmeasured' and priced with DEFAULT_VOID_RATE, which is
    the MAXIMUM measured rate. An unknown vertical is treated as the worst one
    observed, so the fallback must never silently become a mean.

    The prices are chosen so the RATE ITSELF decides the outcome. Entered at
    92c and collapsing to 35c, realised excursion is 0.5700, which sits
    BETWEEN the RU predicted on a near-zero void rate (0.5192) and the RU
    predicted on DEFAULT_VOID_RATE (0.6103). So this position breaches under
    a weakened fallback and does not breach under the real one -- the
    assertion below flips if anyone lowers it."""
    p = tmp_path / "rec.jsonl"
    rows = [_row("KXZZUNKNOWN-1", ts, price - 1, price + 1,
                 series="KXZZUNKNOWN")
            for ts, price in enumerate([91, 70, 50, 34], start=1)]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    stats = calibrate(load_recording(p), horizon=3)
    assert set(stats) == {"unmeasured"}
    assert stats["unmeasured"].n == 1
    assert stats["unmeasured"].breaches == 0, (
        "a breach here means the fallback void rate was lowered below "
        "DEFAULT_VOID_RATE")


def test_execution_stays_disabled_throughout_this_plan():
    """GLOBAL CONSTRAINT: nothing in Plan 1 may enable execution."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from agent.risk import RISK
    assert RISK.is_live() is False
