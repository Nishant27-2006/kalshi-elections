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

from ru_calibration import (calibrate, load_recording, excursion_scaling,
                            excursion_points, ScalingFit)


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
    alongside a flat 50c ticker that does not. This fixture is symmetric
    under a realised/predicted comparison reversal (n=2, breaches=1 either
    way), so it does NOT catch that bug on its own --
    test_a_mid_priced_book_cannot_breach_its_own_RU and
    test_an_unmeasured_series_falls_back_to_the_worst_known_void_rate do.
    What this test actually proves is that a genuine collapse from a strong
    favourite realises more adverse excursion than its RU predicts, while a
    flat book in the same batch does not."""
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


def test_a_path_that_loses_all_its_quotes_is_skipped_not_scored_as_zero(tmp_path):
    """An unquoted path is MISSING DATA, not a measured non-breach. Scoring it
    as 0.0 excursion would silently bias the breach rate downward -- and books
    go unquoted precisely when risk is real."""
    p = tmp_path / "rec.jsonl"
    rows = [_row("KXMLBGAME-Q", 1, 49, 51, series="KXMLBGAME")]
    for ts in (2, 3, 4):
        r = _row("KXMLBGAME-Q", ts, 49, 51, series="KXMLBGAME")
        r["yes_ask_c"] = None
        rows.append(r)
    p.write_text("\n".join(json.dumps(x) for x in rows), encoding="utf-8")

    stats = calibrate(load_recording(p), horizon=3)
    assert stats == {}, "an unquoted path must not be scored as a non-breach"


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


def test_a_malformed_row_is_skipped_not_allowed_to_abort_the_replay(capsys, tmp_path):
    """A negative spread reaching ru_per_contract raises ValueError there.
    One bad ticker must not abort the whole replay: it is announced and
    skipped, and other tickers are still measured."""
    from ru_calibration import SkipCounts

    p = tmp_path / "rec.jsonl"
    rows = [
        _row("KXMLBGAME-BAD", 1, 51, 49, series="KXMLBGAME"),  # bid>ask: spread -2
        _row("KXMLBGAME-BAD", 2, 51, 49, series="KXMLBGAME"),
    ]
    for ts, price in enumerate([50, 50, 50, 50], start=1):
        rows.append(_row("KXMLBGAME-Y", ts, price - 1, price + 1,
                         series="KXMLBGAME"))
    p.write_text("\n".join(json.dumps(x) for x in rows), encoding="utf-8")

    skips = SkipCounts()
    stats = calibrate(load_recording(p), horizon=3, skips=skips)
    assert stats["mlb_game"].n == 1, "the good ticker must still be measured"
    assert skips.sizing_error == 1
    printed = capsys.readouterr().out
    assert "KXMLBGAME-BAD" in printed, "the skipped ticker must be named"
    assert "ValueError" in printed, "the failure type must be announced"


def test_skip_counts_add_up_to_the_gap_between_loaded_and_measured(tmp_path):
    from ru_calibration import SkipCounts

    p = tmp_path / "rec.jsonl"
    rows = [
        # too_few_rows: a single snapshot
        _row("KXMLBGAME-ONE", 1, 49, 51, series="KXMLBGAME"),
        # missing_quote: no ask on the entry row
    ]
    missing = _row("KXMLBGAME-NOQUOTE", 1, 49, 51, series="KXMLBGAME")
    missing["yes_ask_c"] = None
    rows.append(missing)
    rows.append(_row("KXMLBGAME-NOQUOTE", 2, 49, 51, series="KXMLBGAME"))
    # one healthy ticker so calibrate() returns something
    for ts, price in enumerate([50, 50, 50, 50], start=1):
        rows.append(_row("KXMLBGAME-Y", ts, price - 1, price + 1,
                         series="KXMLBGAME"))
    p.write_text("\n".join(json.dumps(x) for x in rows), encoding="utf-8")

    by_ticker = load_recording(p)
    skips = SkipCounts()
    stats = calibrate(by_ticker, horizon=3, skips=skips)
    measured = sum(s.n for s in stats.values())
    assert measured + skips.total == len(by_ticker)
    assert skips.too_few_rows == 1
    assert skips.missing_quote == 1


def test_execution_stays_disabled_throughout_this_plan():
    """GLOBAL CONSTRAINT: nothing in Plan 1 may enable execution."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from agent.risk import RISK
    assert RISK.is_live() is False


# ------------------------------------------------- excursion scaling fit

def _walk_recording(alpha, k=0.001, n_bars=30, n_tickers=60, step=18):
    """Synthetic paths whose mean adverse excursion grows as k * t**alpha."""
    out = {}
    for j in range(n_tickers):
        rows = [_row(f"KXMLBGAME-{j}", 1, 49, 51, series="KXMLBGAME")]
        for b in range(1, n_bars):
            drop = k * ((b * step) ** alpha) * 100.0
            # alternate sign so half the names fall and half rise; the
            # excursion measure only sees the falls
            px = 51 - drop if j % 2 == 0 else 51 + drop
            rows.append(_row(f"KXMLBGAME-{j}", b + 1, px - 2, px,
                             series="KXMLBGAME"))
        out[f"KXMLBGAME-{j}"] = rows
    return out


def test_the_scaling_fit_recovers_a_known_exponent():
    """If the fit cannot recover an exponent it was handed, no number it
    produces about real data means anything."""
    fit = excursion_scaling(_walk_recording(alpha=0.5), min_sample=10)
    assert fit is not None
    assert fit.alpha == pytest.approx(0.5, abs=0.05)

    trending = excursion_scaling(_walk_recording(alpha=0.8), min_sample=10)
    assert trending.alpha == pytest.approx(0.8, abs=0.05)


def test_a_trending_market_is_distinguishable_from_a_random_walk():
    """alpha > 0.5 means moves PERSIST. That is simultaneously the regime a
    momentum strategy needs and the regime where a risk measure fitted on
    short windows understates long holds. Confusing the two is how a fund
    talks itself into size."""
    walk = excursion_scaling(_walk_recording(alpha=0.5), min_sample=10)
    trend = excursion_scaling(_walk_recording(alpha=0.9), min_sample=10)
    assert trend.alpha > walk.alpha + 0.2


def test_the_fit_reports_how_far_an_answer_is_extrapolated():
    """Asking a fit built on 8 minutes about a 24-hour hold is a 180x
    extrapolation. The caller must be able to see that rather than reading
    the answer as a measurement."""
    fit = excursion_scaling(_walk_recording(alpha=0.5), min_sample=10)
    assert fit.extrapolation_factor(fit.fitted_to_s) == pytest.approx(1.0)
    assert fit.extrapolation_factor(fit.fitted_to_s * 200) == pytest.approx(200.0)


def test_the_fit_refuses_a_recording_too_short_to_fit():
    """Three points is not a curve. Returning a confident exponent from two
    bars would be the worst kind of invented number."""
    assert excursion_scaling({}, min_sample=1) is None
    tiny = {"A": [_row("A", 1, 49, 51, series="KXMLBGAME"),
                  _row("A", 2, 48, 50, series="KXMLBGAME")]}
    assert excursion_scaling(tiny, min_sample=1) is None


def test_excursion_at_is_the_fitted_power_law():
    fit = excursion_scaling(_walk_recording(alpha=0.6), min_sample=10)
    assert fit.excursion_at(100.0) == pytest.approx(fit.k * 100.0 ** fit.alpha)
    # and it is monotonically increasing in time
    assert fit.excursion_at(1000.0) > fit.excursion_at(100.0)


def _saturating_recording(n_bars=40, n_tickers=60, step=18, cap=0.05):
    """Paths whose excursion grows then FLATTENS -- no power law fits."""
    out = {}
    for j in range(n_tickers):
        rows = [_row(f"KXMLBGAME-{j}", 1, 49, 51, series="KXMLBGAME")]
        for b in range(1, n_bars):
            # saturating: approaches `cap` and stops
            drop = cap * (1 - 2.718 ** (-b / 4.0)) * 100.0
            px = 51 - drop if j % 2 == 0 else 51 + drop
            rows.append(_row(f"KXMLBGAME-{j}", b + 1, px - 2, px,
                             series="KXMLBGAME"))
        out[f"KXMLBGAME-{j}"] = rows
    return out


def test_a_genuine_power_law_is_reported_as_stable():
    """The stability check must not cry wolf: data that really is scale-free
    has to pass, or the harness refuses to extrapolate from anything."""
    fit = excursion_scaling(_walk_recording(alpha=0.5, n_bars=40),
                            min_sample=10)
    assert fit.stable is True
    assert fit.r_squared > 0.95
    assert abs(fit.alpha - fit.alpha_half_window) < 0.10


def test_a_saturating_curve_is_caught_as_not_scale_free():
    """THE DEFECT THIS EXISTS TO PREVENT. Excursion that flattens is not a
    power law, but least squares will still hand back a confident-looking
    exponent. Fitted on the first eighth of the real recording that exponent
    read 0.68 -- 'the market trends' -- and on the whole recording 0.44 --
    'the market mean-reverts'. Sizing on the first number would buy a trend
    that is not there."""
    fit = excursion_scaling(_saturating_recording(), min_sample=10)
    assert fit is not None
    assert fit.stable is False, "a saturating curve must not read as stable"
    assert fit.saturating is True
    assert fit.alpha_half_window > fit.alpha, "early horizons look steeper"


def test_the_exponent_from_a_saturating_curve_depends_on_the_window():
    """Concretely: the same data fitted over two ranges gives two different
    exponents. That is the definition of a misspecified model."""
    rec = _saturating_recording(n_bars=40)
    short = {k: v[:12] for k, v in rec.items()}
    full = excursion_scaling(rec, min_sample=10)
    part = excursion_scaling(short, min_sample=10)
    assert abs(part.alpha - full.alpha) > 0.10


def test_stability_requires_both_a_matching_exponent_and_a_good_fit():
    """Either failure alone is disqualifying."""
    good = ScalingFit(k=1e-4, alpha=0.50, n_points=50, fitted_from_s=18,
                      fitted_to_s=900, r_squared=0.99,
                      alpha_half_window=0.52)
    assert good.stable is True
    drifting = ScalingFit(k=1e-4, alpha=0.44, n_points=50, fitted_from_s=18,
                          fitted_to_s=900, r_squared=0.99,
                          alpha_half_window=0.63)
    assert drifting.stable is False
    noisy = ScalingFit(k=1e-4, alpha=0.50, n_points=50, fitted_from_s=18,
                       fitted_to_s=900, r_squared=0.70,
                       alpha_half_window=0.51)
    assert noisy.stable is False
