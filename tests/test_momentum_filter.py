"""Scanner filtering and ranking. Pure -- no network.

Invariant H: the scan had no date filter and ranked absolute delta across all
575 series, so it surfaced Likud/Alaska/Wyoming noise alongside the race being
traded, and put thin-book repricing at the top.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import momentum_filter as mf

from momentum_filter import (annotate, ask_sum_cents, closes_within,
                             conviction_score, is_thin_book, parse_day,
                             parse_ts, rank, series_matches,
                             window_for_election_day)

ELECTION_DAY = "2026-08-18"


def mkt(close):
    return {"close_time": close}


# ---------------------------------------------------------------- parsing
def test_parses_z_suffixed_and_offset_timestamps():
    assert parse_ts("2026-08-18T23:00:00Z").tzinfo is not None
    assert parse_ts("2026-08-18T23:00:00+00:00").hour == 23


def test_naive_timestamps_are_treated_as_utc():
    assert parse_ts("2026-08-18T23:00:00").tzinfo == timezone.utc


def test_unparseable_timestamp_is_none_not_an_exception():
    assert parse_ts("not-a-date") is None
    assert parse_ts(None) is None


def test_a_bad_cli_date_fails_loudly():
    with pytest.raises(ValueError):
        parse_day("last tuesday")


# ---------------------------------------------------------------- window
def test_election_day_window_spans_the_day_either_side():
    after, before = window_for_election_day(ELECTION_DAY)
    assert after == datetime(2026, 8, 17, tzinfo=timezone.utc)
    assert before == datetime(2026, 8, 20, tzinfo=timezone.utc)


def test_market_closing_on_election_night_is_kept():
    after, before = window_for_election_day(ELECTION_DAY)
    assert closes_within(mkt("2026-08-18T23:59:00Z"), after, before)


def test_market_resolving_years_out_is_dropped():
    """The Alaska/Wyoming noise the unfiltered scan surfaced."""
    after, before = window_for_election_day(ELECTION_DAY)
    assert not closes_within(mkt("2028-11-07T23:59:00Z"), after, before)


def test_market_that_already_closed_is_dropped():
    after, before = window_for_election_day(ELECTION_DAY)
    assert not closes_within(mkt("2026-06-01T00:00:00Z"), after, before)


def test_missing_close_time_is_excluded_when_a_window_is_requested():
    """Including it would quietly reintroduce exactly what we filtered out."""
    after, before = window_for_election_day(ELECTION_DAY)
    assert not closes_within({}, after, before)
    assert not closes_within(mkt("garbage"), after, before)


def test_no_window_keeps_everything_including_undated():
    assert closes_within({}, None, None)
    assert closes_within(mkt("2028-11-07T00:00:00Z"), None, None)


def test_one_sided_windows_work():
    after = parse_day("2026-08-18")
    assert closes_within(mkt("2026-09-01T00:00:00Z"), after, None)
    assert not closes_within(mkt("2026-08-01T00:00:00Z"), after, None)


# ---------------------------------------------------------------- series
def test_series_substring_match_is_case_insensitive():
    assert series_matches("KXFLPRIMARY", ["fl"])
    assert series_matches("KXFLPRIMARY", ["FLPRIMARY"])


def test_series_filter_excludes_the_noise_series():
    pats = ["KXFL"]
    assert not series_matches("KXISRAELGOVT", pats)
    assert not series_matches("KXAKPRIMARY", pats)
    assert series_matches("KXFLPRIMARY", pats)


def test_regex_patterns_are_supported():
    assert series_matches("KXFLPRIMARY", ["^KXFL.*PRIMARY$"])


def test_no_pattern_keeps_everything():
    assert series_matches("KXANYTHING", None)
    assert series_matches("KXANYTHING", [])


def test_an_invalid_regex_does_not_crash_the_scan():
    assert series_matches("KXFLPRIMARY", ["FL("]) is False


# ---------------------------------------------------------------- ranking
ASKAR = {"ticker": "KXFLPRIMARY-22R26-CASK", "delta": 0.18, "volume": 7250.0,
         "yes_ask": 28.0}
DEEP = {"ticker": "KXFLGOV-DEEP", "delta": 0.06, "volume": 280000.0,
        "yes_ask": 55.0}


def test_absolute_delta_ranking_puts_the_thin_book_first():
    """Reproducing the old behaviour, which is the problem."""
    top = rank(annotate([ASKAR.copy(), DEEP.copy()]), by="delta")[0]
    assert top["ticker"] == "KXFLPRIMARY-22R26-CASK"


def test_conviction_ranking_demotes_the_thin_book_repricing():
    """Scanned against the depth NORMAL FOR THIS RACE (FL-22R ~280k/24h),
    the 18c thin-book move falls behind the 6c deep-book move."""
    recs = annotate([ASKAR.copy(), DEEP.copy()], thin_book_contracts=280000.0)
    assert rank(recs)[0]["ticker"] == "KXFLGOV-DEEP"


def test_the_default_threshold_only_narrows_the_gap():
    """Honest about the default: at a 20k reference depth the 18c move is
    discounted from 3x the deep move to near-parity, not inverted. The
    threshold has to match the race before the ranking actually flips."""
    recs = annotate([ASKAR.copy(), DEEP.copy()])
    askar = next(r for r in recs if r["thin_book"])
    deep = next(r for r in recs if not r["thin_book"])
    assert abs(ASKAR["delta"]) / abs(DEEP["delta"]) == pytest.approx(3.0)
    assert askar["conviction"] / deep["conviction"] < 1.15


def test_the_askar_case_is_flagged_thin():
    assert is_thin_book(ASKAR)
    assert not is_thin_book(DEEP)


def test_conviction_never_exceeds_the_raw_move():
    assert conviction_score(DEEP) <= abs(DEEP["delta"])
    assert conviction_score(ASKAR) < abs(ASKAR["delta"])


def test_a_full_size_book_keeps_its_move_intact():
    rec = {"delta": 0.10, "volume": 20000.0}
    assert conviction_score(rec) == pytest.approx(0.10)


def test_zero_volume_scores_zero():
    assert conviction_score({"delta": 0.5, "volume": 0.0}) == 0.0


def test_annotate_does_not_reorder():
    recs = annotate([ASKAR.copy(), DEEP.copy()])
    assert recs[0]["ticker"] == "KXFLPRIMARY-22R26-CASK"
    assert "conviction" in recs[0] and "thin_book" in recs[0]


# ---------------------------------------------------------------- ask-sum
def test_ask_sum_detects_a_longshot_premium():
    """A field summing to 117c carries premium; 104c is most of it gone."""
    before = [{"yes_ask": a} for a in (28.0, 61.0, 44.0, 8.0)]   # 141
    assert ask_sum_cents(before) == 141.0
    after = [{"yes_ask": a} for a in (28.0, 57.0, 40.0, 4.0)]
    assert ask_sum_cents(after) == 129.0
    assert ask_sum_cents(after) < ask_sum_cents(before), "field collapsing"


def test_ask_sum_is_none_when_nothing_is_quoted():
    assert ask_sum_cents([{"yes_ask": None}]) is None
    assert ask_sum_cents([]) is None


# ---------------------------------------------------------------- events
def test_event_ticker_uses_series_and_period():
    from momentum_filter import event_ticker
    assert event_ticker("KXFLPRIMARY-21D26-BTAY") == "KXFLPRIMARY-21D26"
    assert event_ticker("KXGOVFLNOMR-26-BD") == "KXGOVFLNOMR-26"


def test_event_ticker_handles_hyphenated_outcomes():
    """An exact-finish outcome is itself hyphenated; trimming one segment
    split one event into three and produced a nonsense ask-sum."""
    from momentum_filter import event_ticker
    for outcome in ("DON-COL-REN", "DON-FIS-COL", "DON-COL-FIS"):
        assert event_ticker(f"KXFLRGOVEXACT-26AUG18-{outcome}") == \
            "KXFLRGOVEXACT-26AUG18"


def test_ask_sums_group_by_event_not_series():
    """KXFLPRIMARY spans nine district races; summing the series gave 922c."""
    from momentum_filter import ask_sums_by_event
    # flag included: two candidate legs with no flag are undecidable by shape
    recs = [
        {"ticker": "KXFLPRIMARY-21D26-BTAY", "yes_ask": 61.0, "mutually_exclusive": True},
        {"ticker": "KXFLPRIMARY-21D26-JMAR", "yes_ask": 44.0, "mutually_exclusive": True},
        {"ticker": "KXFLPRIMARY-25R26-SSIN", "yes_ask": 80.0, "mutually_exclusive": True},
        {"ticker": "KXFLPRIMARY-25R26-DFRA", "yes_ask": 6.0, "mutually_exclusive": True},
    ]
    sums = ask_sums_by_event(recs)
    assert set(sums) == {"KXFLPRIMARY-21D26", "KXFLPRIMARY-25R26"}
    assert sums["KXFLPRIMARY-21D26"]["ask_sum_cents"] == 105.0
    assert sums["KXFLPRIMARY-21D26"]["premium_cents"] == 5.0
    assert all(s["ask_sum_cents"] < 200 for s in sums.values())


def test_ticker_match_targets_an_embedded_election_date():
    """close_time is not a usable election-day key here, so the ticker is."""
    from momentum_filter import ticker_matches
    assert ticker_matches("KXFLRGOVEXACT-26AUG18-DON-COL-REN", ["26AUG18"])
    assert not ticker_matches("KXGOVFLNOMR-26-BD", ["26AUG18"])


# ---------------------------------------------------------------- structure
def test_a_candidate_field_is_an_exclusive_field():
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": "KXHIGHNY-26AUG19-T85", "yes_ask": 31.0},
            {"ticker": "KXHIGHNY-26AUG19-B85.5", "yes_ask": 52.0},
            {"ticker": "KXHIGHNY-26AUG19-B87.5", "yes_ask": 19.0}]
    info = ask_sums_by_event(recs)["KXHIGHNY-26AUG19"]
    assert info["structure"] == "exclusive_field"
    assert info["premium_cents"] == 2.0


def test_a_cumulative_threshold_ladder_gets_no_premium():
    """KXCPIYOY-26AUG has 26 legs summing to 939c. That is a CDF, not vig."""
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": f"KXCPIYOY-26AUG-T{v}", "yes_ask": a} for v, a in
            [(3.0, 100.0), (3.1, 99.0), (3.2, 90.0), (3.3, 68.0),
             (3.4, 37.0), (3.5, 10.0), (3.6, 4.0)]]
    info = ask_sums_by_event(recs)["KXCPIYOY-26AUG"]
    assert info["structure"] == "threshold_ladder"
    assert info["premium_cents"] is None, "a CDF has no vig interpretation"


def test_the_exchange_flag_beats_the_shape_heuristic():
    from momentum_filter import is_threshold_ladder
    ladder_shaped = [{"ticker": f"X-26-T{v}", "yes_ask": a, "mutually_exclusive": True}
                     for v, a in [(1, 90.0), (2, 50.0), (3, 10.0)]]
    assert is_threshold_ladder(ladder_shaped) is False


def test_non_threshold_tickers_are_never_ladders():
    from momentum_filter import is_threshold_ladder
    assert is_threshold_ladder([{"ticker": "KXGOVFLNOMR-26-BD", "yes_ask": 98.0},
                                {"ticker": "KXGOVFLNOMR-26-JFIS", "yes_ask": 1.3},
                                {"ticker": "KXGOVFLNOMR-26-JCOL", "yes_ask": 0.3}]) is False


# ---------------------------------------------------------------- MLB shapes
def test_event_ticker_handles_hyphenated_series_tickers():
    """KXMLBWINS-BOS is a two-part SERIES name. The first-two-segments rule
    mapped KXMLBWINS-BOS-26-T95 to KXMLBWINS-BOS, merging every season's
    Boston wins event into one bogus field."""
    from momentum_filter import event_ticker
    assert event_ticker("KXMLBWINS-BOS-26-T95") == "KXMLBWINS-BOS-26"
    assert event_ticker("KXMLB-26-WSH") == "KXMLB-26"
    assert event_ticker("KXMLBGAME-26AUG202005WSHTEX-WSH") == \
        "KXMLBGAME-26AUG202005WSHTEX"
    assert event_ticker("KXMLBTOTAL-26AUG181910SDNYM-9") == \
        "KXMLBTOTAL-26AUG181910SDNYM"


def test_event_ticker_prefers_the_exchange_field():
    from momentum_filter import event_ticker
    assert event_ticker({"ticker": "KXMLBWINS-BOS-26-T95",
                         "event_ticker": "AUTHORITATIVE"}) == "AUTHORITATIVE"
    assert event_ticker({"ticker": "KXMLB-26-WSH"}) == "KXMLB-26"


def test_bare_numeric_strikes_are_recognised_as_a_ladder():
    """MLB game totals number their legs bare (-9, -12) rather than T-prefixed.
    Requiring the T classified a 578c cumulative ask-sum as an exclusive
    field, i.e. a 478c longshot premium that does not exist."""
    from momentum_filter import ask_sums_by_event, is_threshold_ladder
    recs = [{"ticker": f"KXMLBTOTAL-26AUG181910SDNYM-{n}", "yes_ask": a}
            for n, a in [(3, 97.0), (4, 92.0), (5, 88.0), (6, 77.0), (7, 70.0),
                         (8, 58.0), (9, 51.0), (12, 25.0), (13, 20.0)]]
    assert is_threshold_ladder(recs) is True
    info = ask_sums_by_event(recs)["KXMLBTOTAL-26AUG181910SDNYM"]
    assert info["structure"] == "threshold_ladder"
    assert info["premium_cents"] is None


def test_t_prefixed_season_wins_ladder_still_detected():
    from momentum_filter import is_threshold_ladder
    recs = [{"ticker": f"KXMLBWINS-BOS-26-T{n}", "yes_ask": a}
            for n, a in [(75, 100.0), (80, 99.0), (85, 86.0), (90, 35.0),
                         (95, 19.0), (100, 5.0), (105, 3.0)]]
    assert is_threshold_ladder(recs) is True


def test_a_two_leg_moneyline_is_an_exclusive_field():
    """Baseball has no draw, so two legs partition the outcome completely."""
    from momentum_filter import ask_sums_by_event
    # Real scanner records carry the exchange flag; without it a 2-leg sample
    # is genuinely undecidable (monotonicity needs >=3 points).
    recs = [{"ticker": "KXMLBGAME-26AUG202005WSHTEX-WSH", "yes_ask": 48.0,
             "mutually_exclusive": True},
            {"ticker": "KXMLBGAME-26AUG202005WSHTEX-TEX", "yes_ask": 56.0,
             "mutually_exclusive": True}]
    info = ask_sums_by_event(recs)["KXMLBGAME-26AUG202005WSHTEX"]
    assert info["structure"] == "exclusive_field"
    assert info["premium_cents"] == 4.0


def test_a_thirty_leg_championship_field_is_exclusive():
    from momentum_filter import is_threshold_ladder
    recs = [{"ticker": f"KXMLB-26-{c}", "yes_ask": a} for c, a in
            [("TB", 7.6), ("SD", 3.0), ("SEA", 1.9), ("TEX", 1.4), ("WSH", 0.1)]]
    assert is_threshold_ladder(recs) is False


# ---------------------------------------------------------------- soccer shapes
def test_a_one_leg_market_is_a_standalone_binary_not_a_ladder():
    """KXUCLBTTS is a single leg flagged mutually_exclusive=False, the same
    flag a cumulative ladder carries. Reading it as a ladder implied 'leg
    differences are the density', which is meaningless for one leg."""
    from momentum_filter import (ask_sums_by_event, is_standalone_binary,
                                 is_threshold_ladder)
    recs = [{"ticker": "KXUCLBTTS-26AUG19CELASK-BTTS", "yes_ask": 53.0,
             "event_ticker": "KXUCLBTTS-26AUG19CELASK",
             "mutually_exclusive": False}]
    assert is_standalone_binary(recs) is True
    assert is_threshold_ladder(recs) is False
    info = ask_sums_by_event(recs)["KXUCLBTTS-26AUG19CELASK"]
    assert info["structure"] == "standalone_binary"
    assert info["premium_cents"] is None, "one leg carries no vig reading"


def test_a_three_way_match_is_an_exclusive_field():
    """Soccer has a draw, so a match partitions into THREE legs. MLB's
    two-leg arithmetic does not transfer."""
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": f"KXUCLGAME-26AUG19CELASK-{c}", "yes_ask": a,
             "event_ticker": "KXUCLGAME-26AUG19CELASK",
             "mutually_exclusive": True}
            for c, a in [("TIE", 23.0), ("CEL", 60.0), ("ASK", 18.0)]]
    info = ask_sums_by_event(recs)["KXUCLGAME-26AUG19CELASK"]
    assert info["structure"] == "exclusive_field"
    assert info["legs"] == 3
    assert info["premium_cents"] == 1.0


def test_a_multi_leg_ladder_is_still_a_ladder():
    """Guard the standalone-binary fix against over-reach."""
    from momentum_filter import is_standalone_binary, is_threshold_ladder
    recs = [{"ticker": f"KXMLBTOTAL-26AUG181910SDNYM-{n}", "yes_ask": a}
            for n, a in [(5, 88.0), (7, 70.0), (9, 51.0), (12, 25.0)]]
    assert is_standalone_binary(recs) is False
    assert is_threshold_ladder(recs) is True


def test_the_three_structures_are_mutually_exclusive():
    from momentum_filter import ask_sums_by_event
    cases = {
        "standalone_binary": [{"ticker": "KXUCLBTTS-26AUG19X-BTTS",
                               "yes_ask": 53.0, "mutually_exclusive": False}],
        "exclusive_field": [{"ticker": f"KXUCLGAME-26AUG19X-{c}", "yes_ask": a,
                             "mutually_exclusive": True}
                            for c, a in [("TIE", 23.0), ("A", 60.0), ("B", 18.0)]],
        "threshold_ladder": [{"ticker": f"KXCPIYOY-26AUG-T{v}", "yes_ask": a}
                             for v, a in [(3.0, 100.0), (3.3, 68.0),
                                          (3.4, 37.0), (3.6, 4.0)]],
    }
    for expected, recs in cases.items():
        info = list(ask_sums_by_event(recs).values())[0]
        assert info["structure"] == expected, \
            f"{expected} misclassified as {info['structure']}"


def test_soccer_event_tickers_parse():
    from momentum_filter import event_ticker
    assert event_ticker("KXUCLGAME-26AUG19CELASK-TIE") == "KXUCLGAME-26AUG19CELASK"
    assert event_ticker("KXUCL1H-26AUG18LEVAEK-TIE") == "KXUCL1H-26AUG18LEVAEK"
    assert event_ticker("KXUCL-27-RMA") == "KXUCL-27"


# ---------------------------------------------------------------- crypto shapes
def test_a_188_leg_price_ladder_is_a_threshold_ladder():
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": f"KXBTCD-26AUG1815-T{p}.99", "yes_ask": a,
             "event_ticker": "KXBTCD-26AUG1815", "mutually_exclusive": False}
            for p, a in [(64999, 60.0), (65999, 40.0), (66999, 20.0),
                         (67999, 8.0), (68999, 2.0)]]
    info = ask_sums_by_event(recs)["KXBTCD-26AUG1815"]
    assert info["structure"] == "threshold_ladder"
    assert info["premium_cents"] is None


def test_a_window_maximum_ladder_uses_bare_cent_strikes():
    """KXBTCMAXMON strikes are integer cents (6750000 = $67,500)."""
    from momentum_filter import is_threshold_ladder
    recs = [{"ticker": f"KXBTCMAXMON-BTC-26AUG31-{s}", "yes_ask": a}
            for s, a in [(6750000, 34.0), (7000000, 14.0), (7250000, 6.0),
                         (7500000, 3.0), (8250000, 1.0)]]
    assert is_threshold_ladder(recs) is True


def test_a_one_leg_crypto_market_is_a_standalone_binary():
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": "KXBTC15M-26AUG181445-45", "yes_ask": 28.0,
             "event_ticker": "KXBTC15M-26AUG181445",
             "mutually_exclusive": False}]
    info = ask_sums_by_event(recs)["KXBTC15M-26AUG181445"]
    assert info["structure"] == "standalone_binary"
    assert info["premium_cents"] is None


def test_leg_count_beats_the_exclusivity_flag_on_one_leg_events():
    """KXBTC2026200 is ONE leg with mutually_exclusive=True, while KXBTC15M is
    ONE leg with False. Kalshi uses both flags on single-leg events, so the
    structure must key on leg count."""
    from momentum_filter import ask_sums_by_event
    for flag in (True, False):
        recs = [{"ticker": "KXBTC2026200-27JAN01-200000", "yes_ask": 3.0,
                 "event_ticker": "KXBTC2026200-27JAN01",
                 "mutually_exclusive": flag}]
        info = ask_sums_by_event(recs)["KXBTC2026200-27JAN01"]
        assert info["structure"] == "standalone_binary", f"flag={flag}"


def test_crypto_event_tickers_parse_including_three_segment_names():
    """KXBTCMAXMON-BTC-26AUG31 puts the asset between series and period."""
    from momentum_filter import event_ticker
    assert event_ticker("KXBTCMAXMON-BTC-26AUG31-6750000") == \
        "KXBTCMAXMON-BTC-26AUG31"
    assert event_ticker("KXBTCD-26AUG1815-T72299.99") == "KXBTCD-26AUG1815"
    assert event_ticker("KXBTC15M-26AUG181445-45") == "KXBTC15M-26AUG181445"
    assert event_ticker("KXBTC2026200-27JAN01-200000") == "KXBTC2026200-27JAN01"


# ---------------------------------------------------------------- corporate shapes
def test_a_date_indexed_ladder_is_detected_by_shape():
    """Corporate events ladder by DATE and rise with it. Testing only for a
    decreasing sequence classified every IPO/merger ladder as an exclusive
    field and reported its cumulative ask-sum as a longshot premium."""
    from momentum_filter import ask_sums_by_event, is_threshold_ladder
    recs = [{"ticker": f"KXIPOANTHROPIC-DATE-{d}", "yes_ask": a} for d, a in
            [("26SEP01", 2.0), ("26OCT01", 24.0), ("26NOV01", 68.0),
             ("26DEC01", 73.0), ("27JAN01", 90.0), ("27APR01", 93.0)]]
    assert is_threshold_ladder(recs) is True
    info = ask_sums_by_event(recs)["KXIPOANTHROPIC-DATE"]
    assert info["structure"] == "threshold_ladder"
    assert info["premium_cents"] is None
    assert info["legs"] == 6, "all legs must group into ONE event"


def test_a_date_outcome_does_not_become_its_own_event():
    """KXIPOANTHROPIC-DATE-26SEP01: the trailing date is the OUTCOME, so the
    event is KXIPOANTHROPIC-DATE. Treating it as the period split one 8-leg
    ladder into 8 standalone binaries."""
    from momentum_filter import event_ticker
    assert event_ticker("KXIPOANTHROPIC-DATE-26SEP01") == "KXIPOANTHROPIC-DATE"
    assert event_ticker("KXCOMPANYACTIONMERGER-27-26SEP01") == \
        "KXCOMPANYACTIONMERGER-27"
    assert event_ticker("KXAAPLCEOCHANGE-26") == "KXAAPLCEOCHANGE"
    assert event_ticker("KXACQANNOUNCEEBAY-27JAN01-JAN01") == \
        "KXACQANNOUNCEEBAY-27JAN01"


def test_a_trailing_date_that_is_NOT_last_is_still_the_period():
    """Guard the fix against over-reach: price ladders keep their period."""
    from momentum_filter import event_ticker
    assert event_ticker("KXBTCD-26AUG1815-T72299.99") == "KXBTCD-26AUG1815"
    assert event_ticker("KXBTCMAXMON-BTC-26AUG31-6750000") == \
        "KXBTCMAXMON-BTC-26AUG31"
    assert event_ticker("KXMLBWINS-BOS-26-T95") == "KXMLBWINS-BOS-26"
    assert event_ticker("KXFLRGOVEXACT-26AUG18-DON-COL-REN") == \
        "KXFLRGOVEXACT-26AUG18"


def test_falling_price_ladders_still_detected():
    """Both monotone directions are cumulative; neither may be lost."""
    from momentum_filter import is_threshold_ladder
    falling = [{"ticker": f"KXBTCD-26AUG1815-T{p}.99", "yes_ask": a}
               for p, a in [(64999, 60.0), (65999, 40.0), (66999, 20.0),
                            (67999, 8.0), (68999, 2.0)]]
    assert is_threshold_ladder(falling) is True


def test_a_single_leg_corporate_binary_classifies_as_standalone():
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": "KXACQANNOUNCEEBAY-27JAN01-JAN01", "yes_ask": 8.0,
             "mutually_exclusive": False}]
    info = ask_sums_by_event(recs)["KXACQANNOUNCEEBAY-27JAN01"]
    assert info["structure"] == "standalone_binary"


def test_date_strike_values_order_correctly():
    from momentum_filter import _strike_value
    assert _strike_value("26SEP01") < _strike_value("26OCT01")
    assert _strike_value("26DEC01") < _strike_value("27JAN01")
    assert _strike_value("3.4") == 3.4
    assert _strike_value("not-a-strike") is None


def test_a_two_leg_sample_without_the_flag_is_indeterminate():
    """Monotonicity needs >=3 points, so 2 legs and no exchange flag cannot be
    classified. Defaulting to exclusive_field printed a confident premium
    (-17c on a 2-leg KXIPOOPENAI sample) computed from a field never seen whole."""
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": "KXIPOOPENAI-DATE-26OCT01", "yes_ask": 30.0},
            {"ticker": "KXIPOOPENAI-DATE-26DEC01", "yes_ask": 53.0}]
    info = ask_sums_by_event(recs)["KXIPOOPENAI-DATE"]
    assert info["structure"] == "indeterminate"
    assert info["premium_cents"] is None


def test_the_exchange_flag_resolves_a_two_leg_sample():
    from momentum_filter import ask_sums_by_event
    for flag, expected in ((True, "exclusive_field"), (False, "threshold_ladder")):
        recs = [{"ticker": "KXX-26-T1", "yes_ask": 80.0, "mutually_exclusive": flag},
                {"ticker": "KXX-26-T2", "yes_ask": 40.0, "mutually_exclusive": flag}]
        assert ask_sums_by_event(recs)["KXX-26"]["structure"] == expected


def test_three_or_more_legs_are_still_decidable_without_a_flag():
    """Guard against over-reach: only the 2-leg case is undecidable."""
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": f"KXMLB-26-{c}", "yes_ask": a}
            for c, a in [("TB", 7.6), ("SD", 3.0), ("SEA", 1.9)]]
    assert ask_sums_by_event(recs)["KXMLB-26"]["structure"] != "indeterminate"


# ------------------------------------------------- flag vs shape disagreement
def test_a_mislabelled_partition_is_reported_as_disputed():
    """KXMOONMAN-31 is a 5-country partition asking 109.9c -- 100 plus ~10c
    vig -- yet Kalshi flags it mutually_exclusive=False. Trusting the flag
    labelled it a ladder and SUPPRESSED a real vig reading."""
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": f"KXMOONMAN-31-{c}", "yes_ask": a,
             "mutually_exclusive": False}
            for c, a in [("USA", 58.4), ("R", 1.9), ("PRC", 42.9),
                         ("I", 5.3), ("E", 1.4)]]
    info = ask_sums_by_event(recs)["KXMOONMAN-31"]
    assert info["structure"] == "disputed"
    assert info["premium_cents"] == pytest.approx(9.9)
    assert "AMBIGUOUS" in info["note"]
    assert "ONLY under the first" in info["note"],         "the premium must be presented as conditional, not asserted"


def test_a_genuine_ladder_is_not_disputed():
    """Guard against over-reach: when the shape AGREES with the flag there is
    no dispute, even though the ask-sum is large."""
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": f"KXBTCD-26AUG1815-T{p}.99", "yes_ask": a,
             "mutually_exclusive": False}
            for p, a in [(64999, 60.0), (65999, 40.0), (66999, 20.0),
                         (67999, 8.0), (68999, 2.0)]]
    info = ask_sums_by_event(recs)["KXBTCD-26AUG1815"]
    assert info["structure"] == "threshold_ladder"
    assert "note" not in info


def test_a_ladder_far_outside_the_vig_band_is_not_disputed():
    """A cumulative ladder summing to 253c is obviously not a 100-field."""
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": f"KXIPOANTHROPIC-DATE-{d}", "yes_ask": a,
             "mutually_exclusive": False}
            for d, a in [("26SEP01", 2.0), ("26NOV01", 68.0),
                         ("27JAN01", 90.0), ("27APR01", 93.0)]]
    assert ask_sums_by_event(recs)["KXIPOANTHROPIC-DATE"]["structure"] == \
        "threshold_ladder"


# ------------------------------------------------- conditional exclusive field
def test_a_sub_100_exclusive_field_is_flagged_ambiguous_not_incomplete():
    """KXMODELHIGH-27-1550 is a COMPLETE 8-leg ME=True field (it even has an
    'Other' leg) asking 37c, because 'no model reaches 1550' is not
    purchasable. The old note asserted sub-100 meant legs were missing."""
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": f"KXMODELHIGH-27-1550-{c}", "yes_ask": a,
             "mutually_exclusive": True}
            for c, a in [("QWEN", 1.0), ("OTHE", 1.0), ("KIMI", 2.0),
                         ("GROK", 1.0), ("GEMI", 6.0), ("ERNI", 1.0),
                         ("CLAU", 19.0), ("CHAT", 6.0)]]
    info = ask_sums_by_event(recs)["KXMODELHIGH-27"]
    assert info["structure"] == "exclusive_field"
    assert info["premium_cents"] == pytest.approx(-63.0)
    assert "conditional" in info["note"]
    assert "Not a vig reading" in info["note"]


def test_a_normal_field_near_100_carries_no_note():
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": f"KXUCLGAME-26AUG19X-{c}", "yes_ask": a,
             "mutually_exclusive": True}
            for c, a in [("TIE", 23.0), ("A", 60.0), ("B", 18.0)]]
    info = ask_sums_by_event(recs)["KXUCLGAME-26AUG19X"]
    assert info["premium_cents"] == 1.0 and "note" not in info


def test_independent_parallel_binaries_are_a_basket_not_a_ladder():
    """KXRAIN-26AUG19 is 20 DIFFERENT CITIES sharing one event, ME=False,
    asking 276c. It is neither a partition nor a cumulative ladder, and the
    flag shortcut ('not exclusive' => 'cumulative') labelled it a ladder."""
    from momentum_filter import ask_sums_by_event
    cities = [("SFO", 7), ("SEA", 3), ("SATX", 2), ("PHX", 12), ("PHIL", 5),
              ("OKC", 6), ("NYC", 9), ("MIA", 40), ("LAX", 1), ("DEN", 22),
              ("CHI", 30), ("BOS", 18), ("ATL", 35), ("DFW", 15), ("HOU", 28),
              ("DCA", 11), ("DTW", 14), ("MSP", 9), ("PDX", 4), ("LAS", 5)]
    recs = [{"ticker": f"KXRAIN-26AUG19-{c}", "yes_ask": float(a),
             "mutually_exclusive": False} for c, a in cities]
    info = ask_sums_by_event(recs)["KXRAIN-26AUG19"]
    assert info["structure"] == "independent_basket"
    assert info["premium_cents"] is None, "a basket ask-sum is not a premium"
    assert "NO meaning" in info["note"]


def test_a_basket_and_a_mislabelled_partition_are_separated_by_ask_sum():
    """The only signal available from prices. Documented as imperfect: a
    basket summing near 100 by chance lands in the ambiguous bucket."""
    from momentum_filter import ask_sums_by_event
    def classify(asks):
        recs = [{"ticker": f"KXX-26-L{i}", "yes_ask": float(a),
                 "mutually_exclusive": False} for i, a in enumerate(asks)]
        return ask_sums_by_event(recs)["KXX-26"]["structure"]
    assert classify([7, 3, 2, 12, 5, 6, 9, 40, 1, 22, 30, 18]) == \
        "independent_basket"          # 155c, well outside the vig band
    assert classify([58.4, 1.9, 42.9, 5.3, 1.4]) == "disputed"   # 109.9c


def test_ask_sums_work_on_raw_api_records():
    """The raw /markets payload ships `yes_ask_dollars` as a string and has no
    integer-cent `yes_ask`. Reading only `yes_ask` returned {} SILENTLY, so a
    caller saw 'no events' rather than 'wrong field'."""
    from momentum_filter import ask_sums_by_event
    raw = [{"ticker": f"KXRAIN-26AUG19-{c}", "event_ticker": "KXRAIN-26AUG19",
            "yes_ask_dollars": d, "mutually_exclusive": False}
           for c, d in [("SFO", "0.07"), ("SEA", "0.03"), ("PHX", "0.12"),
                        ("NYC", "0.09"), ("MIA", "0.40"), ("DEN", "0.22"),
                        ("CHI", "0.30")]]
    info = ask_sums_by_event(raw)["KXRAIN-26AUG19"]
    assert info["legs"] == 7
    assert info["ask_sum_cents"] == pytest.approx(123.0)


def test_reshaped_cent_records_still_work():
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": f"KXX-26-L{i}", "yes_ask": 20.0} for i in range(3)]
    assert ask_sums_by_event(recs)["KXX-26"]["ask_sum_cents"] == 60.0


# ------------------------------------------------- premium readability guard
def test_a_settled_book_reports_no_premium():
    """Kalshi quotes a FINALIZED leg at ask 1.0000 whether it won or lost, so a
    settled event's ask-sum is just its leg count. A 7-leg KXUFCMOV event
    reported +600c, presented identically to a real vig."""
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": f"KXUFCMOV-26AUG18FAZBRI-{c}", "yes_ask_dollars": "1.0000",
             "yes_bid_dollars": "0.0000", "status": "finalized",
             "event_ticker": "KXUFCMOV-26AUG18FAZBRI", "mutually_exclusive": True}
            for c in ("FAZSUB", "FAZKO", "FAZDEC", "DRAW", "BRISUB", "BRIKO",
                      "BRIDEC")]
    info = ask_sums_by_event(recs)["KXUFCMOV-26AUG18FAZBRI"]
    assert info["structure"] == "exclusive_field"
    assert info["premium_cents"] is None
    assert "FINALIZED" in info["note"]


def test_a_quoteless_book_reports_no_premium():
    """Every leg bidding ~0 with wide asks measures DORMANCY, not vig.
    KXWBCHEAVYWEIGHTTITLE-27 reported +516c on a book whose top bid was 3c."""
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": f"KXWBCHEAVYWEIGHTTITLE-27-F{i}",
             "yes_ask_dollars": "0.5000", "yes_bid_dollars": "0.0100",
             "event_ticker": "KXWBCHEAVYWEIGHTTITLE-27",
             "mutually_exclusive": True} for i in range(6)]
    info = ask_sums_by_event(recs)["KXWBCHEAVYWEIGHTTITLE-27"]
    assert info["premium_cents"] is None
    assert "no live bid side" in info["note"]


def test_a_live_two_sided_book_still_reports_its_premium():
    """Guard against over-reach: a healthy field must keep its vig reading."""
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": f"KXUFCFIGHT-26AUG22X-{c}", "yes_ask_dollars": a,
             "yes_bid_dollars": b, "status": "active",
             "event_ticker": "KXUFCFIGHT-26AUG22X", "mutually_exclusive": True}
            for c, a, b in [("HER", "0.6300", "0.6200"),
                            ("ROD", "0.3900", "0.3800")]]
    info = ask_sums_by_event(recs)["KXUFCFIGHT-26AUG22X"]
    assert info["premium_cents"] == pytest.approx(2.0)
    assert "note" not in info


def test_a_low_priced_but_two_sided_field_keeps_its_premium():
    """A longshot-heavy field is not the same as a quoteless one: MLB's
    championship field bids 0-7.5c and is perfectly live."""
    from momentum_filter import ask_sums_by_event
    recs = [{"ticker": f"KXMLB-26-{c}", "yes_ask_dollars": a,
             "yes_bid_dollars": b, "mutually_exclusive": True}
            for c, a, b in [("TB", "0.0760", "0.0750"), ("SD", "0.0300", "0.0200"),
                            ("SEA", "0.0190", "0.0180")]]
    info = ask_sums_by_event(recs)["KXMLB-26"]
    assert info["premium_cents"] is not None


def test_ladder_detection_works_on_raw_api_records():
    """`is_threshold_ladder` read `yes_ask` directly while raw /markets records
    ship only `yes_ask_dollars`. `asks` came back empty, the len<3 guard fired,
    and genuine ladders fell through to exclusive_field / independent_basket
    with a fabricated premium. `ask_sum_cents` was fixed for this; this call
    site was missed, and `_flag_only_ladder` calls it, so attaching the
    exchange flag did not rescue it."""
    from momentum_filter import ask_sums_by_event, is_threshold_ladder
    raw = [{"ticker": f"KXINXU-26AUG19H1600-T{p}", "yes_ask_dollars": str(a),
            "event_ticker": "KXINXU-26AUG19H1600", "mutually_exclusive": False}
           for p, a in [(7800, 0.95), (7850, 0.72), (7870, 0.50),
                        (7900, 0.28), (7950, 0.08)]]
    assert is_threshold_ladder([{k: v for k, v in r.items()
                                 if k != "mutually_exclusive"} for r in raw])
    info = ask_sums_by_event(raw)["KXINXU-26AUG19H1600"]
    assert info["structure"] == "threshold_ladder"
    assert info["premium_cents"] is None


def test_raw_records_still_separate_ladders_from_baskets():
    """The fix must not turn every ME=False event into a ladder."""
    from momentum_filter import ask_sums_by_event
    basket = [{"ticker": f"KXRAIN-26AUG19-{c}", "yes_ask_dollars": str(a),
               "event_ticker": "KXRAIN-26AUG19", "mutually_exclusive": False}
              for c, a in [("SFO", 0.07), ("SEA", 0.03), ("PHX", 0.12),
                           ("NYC", 0.09), ("MIA", 0.40), ("DEN", 0.22),
                           ("CHI", 0.30), ("BOS", 0.18)]]
    assert ask_sums_by_event(basket)["KXRAIN-26AUG19"]["structure"] == \
        "independent_basket"


def _field(n, ask_sum_cents, name="KXFIELD-26", bid_sum=None):
    """n mutually-exclusive legs whose asks total ask_sum_cents.

    Priced SKEWED, not flat: a real grid has a favourite. Splitting a 36-leg
    NASCAR field evenly gives every leg a ~2.75c bid, which correctly trips
    the quoteless-book guard -- a flat field is a dormant field, and the
    helper must not manufacture one while testing something else.
    """
    if bid_sum is None:
        bid_sum = max(ask_sum_cents - n, 0.0)

    def _split(total):
        fav = total * 0.25 if n > 1 else total
        return fav, ((total - fav) / (n - 1) if n > 1 else 0.0)

    a_fav, a_rest = _split(ask_sum_cents)
    b_fav, b_rest = _split(bid_sum)
    out = []
    for i in range(n):
        ask = a_fav if i == 0 else a_rest
        bid = b_fav if i == 0 else b_rest
        out.append({"ticker": f"{name}-L{i}", "event_ticker": name,
                    "yes_ask_dollars": f"{ask / 100:.4f}",
                    "yes_bid_dollars": f"{bid / 100:.4f}",
                    "mutually_exclusive": True})
    return out


def test_a_field_whose_bids_exceed_its_payout_withholds_its_premium():
    """KXF1TOP10-DUTGP26 (live): 22 legs, ask-sum 1109c, BID-sum 805c.

    A partition pays 100c total, so a bid-sum of 805c proves the legs are not
    mutually exclusive whatever the label says. Before this guard the event
    read `exclusive_field +1009c` with no note whenever the event flag had
    not been attached.
    """
    recs = _field(22, 1109.0, bid_sum=805.0)
    info = list(mf.ask_sums_by_event(recs).values())[0]
    assert info["structure"] == "exclusive_field"
    assert info["premium_cents"] is None
    assert info["note"] == mf.IMPLAUSIBLE_FIELD_NOTE


def test_a_wide_illiquid_partition_keeps_its_premium():
    """The false positive the college agent caught in the first version.

    KXNCAAFAPRANK-26W12R1 (live): 13 legs, ask-sum 219c -- more than twice
    par -- but bid-sum 41c. One 96c favourite and twelve zero-bid longshots
    quoted wide. It is a real AP-poll partition; width is illiquidity, not
    evidence against exclusivity. An ask-based rule flagged it. A bid-based
    one must not.
    """
    info = list(mf.ask_sums_by_event(_field(13, 219.0, bid_sum=41.0)).values())[0]
    assert info["premium_cents"] is not None
    assert info.get("note") != mf.IMPLAUSIBLE_FIELD_NOTE


def test_real_observed_fields_keep_their_premium():
    """Every field this repo has actually measured, with its real bid-sum.

    Vig scales with leg count -- 41-leg NASCAR grids ask 133c and 45-leg NFL
    MVP fields 138c, both above _VIG_BAND's 130c ceiling -- so no flat ask
    cap can work. All of these bid UNDER 100c, which is the invariant.
    """
    for legs, ask_sum, bid_sum in [(22, 115.0, 86.0),   # KXF1POLE   live
                                   (50, 143.0, 93.0),   # KXNCAAF    live
                                   (13, 219.0, 41.0),   # KXNCAAFAPRANK live
                                   (2, 102.0, 98.0), (11, 109.0, 91.0),
                                   (41, 133.0, 88.0), (45, 138.2, 84.0)]:
        info = list(mf.ask_sums_by_event(
            _field(legs, ask_sum, bid_sum=bid_sum)).values())[0]
        assert info["premium_cents"] is not None, (
            f"{legs} legs ask={ask_sum}c bid={bid_sum}c is a REAL field")
        assert info.get("note") != mf.IMPLAUSIBLE_FIELD_NOTE


def test_the_guard_is_symmetric_about_par():
    """Below-par and unsellable-above-par both get a note."""
    below = list(mf.ask_sums_by_event(_field(4, 88.0, bid_sum=80.0)).values())[0]
    above = list(mf.ask_sums_by_event(_field(4, 900.0, bid_sum=850.0)).values())[0]
    assert below["note"] == mf.SUB_100_FIELD_NOTE
    assert above["note"] == mf.IMPLAUSIBLE_FIELD_NOTE
    assert above["premium_cents"] is None


def test_a_settled_book_is_diagnosed_as_settled_not_as_implausible():
    """Guard ORDER: a settled 7-leg book sums to ~700c on both sides and trips

    the bid bound too. "Settled" is the true and more specific explanation.
    """
    recs = _field(7, 700.0, bid_sum=693.0)
    for r in recs:
        r["status"] = "finalized"
    info = list(mf.ask_sums_by_event(recs).values())[0]
    assert info["note"] == mf.SETTLED_BOOK_NOTE
    assert info["premium_cents"] is None


def _ladder(asks, bids, name="KXWINS-26X"):
    """A cumulative ladder with bare-integer strikes, flagged ME=False."""
    return [{"ticker": f"{name}-{i + 1}", "event_ticker": name,
             "yes_ask_dollars": f"{a / 100:.4f}",
             "yes_bid_dollars": f"{b / 100:.4f}",
             "mutually_exclusive": False}
            for i, (a, b) in enumerate(zip(asks, bids))]


def test_a_ladder_with_padded_asks_on_dead_rungs_is_still_a_ladder():
    """KXNCAAFWINS-26SCAR (live), "at least N wins".

    Asks run 85 70 49 36 36 18 63 96 -- the 11+ and 12+ rungs are quoted
    wide against a ZERO bid, so the ask side is not monotone. The bids run
    72 65 47 29 19 7 1 0. Testing asks alone demoted a textbook cumulative
    ladder to `independent_basket`, whose advice is "read each leg on its
    own" -- the precise misreading this function exists to prevent.
    """
    recs = _ladder([85, 70, 49, 36, 36, 18, 63, 96],
                   [72, 65, 47, 29, 19, 7, 1, 0])
    assert mf.is_threshold_ladder(recs)
    assert not mf._flag_only_ladder(recs)
    info = list(mf.ask_sums_by_event(recs).values())[0]
    assert info["structure"] == "threshold_ladder"
    assert info["premium_cents"] is None      # a ladder's sum is not vig


def test_a_long_ladder_tolerates_penny_noise_in_its_dead_tail():
    """KXCPIYOY-26AUG (live), 26 rungs -- the ladder the docstring cites.

    Its tail is quoted 2 3 2 3 3 3 1 2 2 2 1 1 1 1, which is three up-ticks
    in 25 steps. A fixed one-tick allowance cannot survive a ladder this
    long, so the canonical example was classified `independent_basket`.
    """
    asks = [100, 100, 100, 100, 100, 100, 99, 92, 69, 37, 13, 5, 2, 3,
            2, 3, 3, 3, 1, 2, 2, 2, 1, 1, 1, 1]
    bids = [97, 97, 98, 98, 98, 97, 98, 87, 64, 22, 9, 1, 0, 0,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    recs = _ladder(asks, bids, name="KXCPIYOY-26AUG")
    assert mf.is_threshold_ladder(recs)
    assert not mf._flag_only_ladder(recs), "26-rung ladder demoted to basket"
    info = list(mf.ask_sums_by_event(recs).values())[0]
    assert info["structure"] == "threshold_ladder"


def test_an_unordered_basket_is_not_rescued_by_the_looser_tolerance():
    """Loosening monotonicity must not turn KXRAIN-style baskets into ladders.

    20 independent cities carry non-numeric strikes, so the shape test bails
    before monotonicity is ever considered -- the flag alone decides.
    """
    recs = [{"ticker": f"KXRAIN-26AUG19-{city}", "event_ticker": "KXRAIN-26AUG19",
             "yes_ask_dollars": "0.5000", "yes_bid_dollars": "0.4500",
             "mutually_exclusive": False}
            for city in ("NYC", "LAX", "ORD", "DFW", "DEN", "SEA", "MIA")]
    assert mf._flag_only_ladder(recs), "unordered basket must not read as a ladder"
    info = list(mf.ask_sums_by_event(recs).values())[0]
    assert info["structure"] == "independent_basket"


def test_a_ladder_survives_a_non_numeric_ticker_tail():
    """Strikes come from `floor_strike` first, the ticker tail only as fallback.

    COSTCOHOTDOG classifies correctly today purely because its tails happen
    to be years (27/28/29/30) while `floor_strike` is null on every leg. Any
    series whose tail is a word would have dropped an 88c cumulative ladder
    into the exclusive-field branch and been handed a fabricated premium.
    """
    recs = [{"ticker": f"KXRIVNA-28JANDELIV-TIER{w}", "event_ticker": "KXRIVNA-28JAN",
             "floor_strike": strike, "mutually_exclusive": False,
             "yes_ask_dollars": f"{a / 100:.4f}", "yes_bid_dollars": f"{a / 100:.4f}"}
            for w, strike, a in [("ALPHA", 62000, 80), ("BRAVO", 64000, 61),
                                 ("CHARLIE", 66000, 40), ("DELTA", 68000, 22)]]
    assert mf.is_threshold_ladder(recs), "floor_strike must carry the ordering"
    info = list(mf.ask_sums_by_event(recs).values())[0]
    assert info["structure"] == "threshold_ladder"
    assert info["premium_cents"] is None


def test_a_null_floor_strike_falls_back_to_the_ticker_tail():
    """COSTCOHOTDOG's real shape: floor_strike null, numeric year tails."""
    recs = [{"ticker": f"COSTCOHOTDOG-{y}", "event_ticker": "COSTCOHOTDOG",
             "floor_strike": None, "mutually_exclusive": False,
             "yes_ask_dollars": f"{a / 100:.4f}", "yes_bid_dollars": f"{a / 100:.4f}"}
            for y, a in [(27, 10), (28, 20), (29, 28), (30, 30)]]
    assert mf.is_threshold_ladder(recs)


def test_a_placeholder_field_bidding_exactly_at_the_threshold_is_caught():
    """KXLPGAR3LEAD-CPKWO26 (live): 158 legs asking 71-74c, only FOUR legs

    bid and all four at exactly 5.0c. `max(bids) < 5.0` is false by one tick,
    so the quoteless guard did not fire and the event was published with
    premium_cents = +11,276.
    """
    recs = [{"ticker": f"KXLPGAR3LEAD-CPKWO26-L{i}",
             "event_ticker": "KXLPGAR3LEAD-CPKWO26",
             "yes_ask_dollars": "0.7200",
             "yes_bid_dollars": "0.0500" if i < 4 else "0.0000",
             "mutually_exclusive": True} for i in range(158)]
    info = list(mf.ask_sums_by_event(recs).values())[0]
    assert info["premium_cents"] is None, "a placeholder book has no readable vig"
    assert info["note"] == mf.QUOTELESS_BOOK_NOTE


def test_breadth_is_not_the_test_a_one_bid_field_can_be_genuine():
    """KXNCAAFAPRANK-26W12R1: a real AP-poll partition with ONE bid leg of

    thirteen -- but that leg bids 96c. Rejecting fields by how FEW legs carry
    a bid would kill it. The level of the best bid is what matters.
    """
    recs = [{"ticker": f"KXNCAAFAPRANK-26W12R1-L{i}",
             "event_ticker": "KXNCAAFAPRANK-26W12R1",
             "yes_ask_dollars": "0.9600" if i == 0 else "0.1000",
             "yes_bid_dollars": "0.9600" if i == 0 else "0.0000",
             "mutually_exclusive": True} for i in range(13)]
    info = list(mf.ask_sums_by_event(recs).values())[0]
    assert info["premium_cents"] is not None
    assert info.get("note") != mf.QUOTELESS_BOOK_NOTE


def test_a_null_collection_from_the_api_does_not_crash_the_sweep():
    """Kalshi sends `"series": null` for an empty category -- observed live on

    category="Culture". A `.get(key, [])` default fires only when the key is
    ABSENT, so it handed back None and `for s in None` raised TypeError,
    killing the entire multi-category sweep rather than skipping one category.
    """
    for payload in ({"series": None}, {"markets": None}, {"events": None}, {}):
        for key in ("series", "markets", "events"):
            assert (payload.get(key) or []) == [], f"{payload} / {key}"
            # the pattern that was wrong:
            if payload.get(key, "sentinel") is None:
                assert payload.get(key, []) is None, "get-default cannot fix null"


def _basket(n, ask_sum, bid_sum, name="KXBASKET-26", rules=""):
    a, b = ask_sum / n, bid_sum / n
    return [{"ticker": f"{name}-L{i}", "event_ticker": name,
             "yes_ask_dollars": f"{a / 100:.4f}", "yes_bid_dollars": f"{b / 100:.4f}",
             "rules_primary": rules, "mutually_exclusive": False}
            for i in range(n)]


def test_a_fixed_cardinality_basket_is_not_read_as_independent():
    """KXCHESSFIDERATINGTOP-26OCTWOMENT10 (live): 20 players listed for

    "Top 10 Rated", so exactly ten legs resolve yes by construction. Asks
    1003c, bids 920c. The legs are CONSTRAINED, and telling the reader to
    "read each leg on its own" -- the plain basket advice -- is wrong.
    """
    recs = _basket(20, 1003.0, 920.0,
                   rules="If Zhu Jiner is rated top 10 on the October 2026 "
                         "FIDE Top Women Players Standard Rating List")
    info = list(mf.ask_sums_by_event(recs).values())[0]
    assert info["structure"] == "independent_basket"
    assert "exactly 10" in info["note"]
    assert info["note"] != mf.BASKET_NOTE


def test_cardinality_is_bracketed_not_rounded():
    """KXF1TOP10-DUTGP26: 22 drivers, exactly 10 finish top-10. Earlier in the

    day it asked 1109c, which ROUNDS to 11 -- the wrong K. The two sides of
    the book bracket K instead: you cannot buy the basket below K x 100 nor
    sell it above, so bid 909 / ask 1005 admits only K = 10.
    """
    assert mf.fixed_cardinality_range(1005.0, 909.0) == (10, 10)
    # a wider book is honestly ambiguous rather than confidently wrong
    assert mf.fixed_cardinality_range(1109.0, 966.0) == (10, 11)


def test_a_genuine_independent_basket_keeps_the_basket_note():
    """KXRAIN-26AUG19: 20 different cities, asks 490c and bids 444c. No

    integer K sits between them, so nothing is constrained and the original
    advice stands.
    """
    info = list(mf.ask_sums_by_event(_basket(20, 490.0, 444.0)).values())[0]
    assert info["note"] == mf.BASKET_NOTE
    assert mf.fixed_cardinality_range(490.0, 444.0) is None


def test_cardinality_range_rejects_degenerate_books():
    assert mf.fixed_cardinality_range(0.0, 0.0) is None
    assert mf.fixed_cardinality_range(100.0, 200.0) is None   # bid above ask
    assert mf.fixed_cardinality_range(150.0, 120.0) is None   # K would be 1


def test_the_scanner_can_reach_every_live_category():
    """CATEGORIES listed 7 of the 13 categories the API serves, so 5,538

    series were unreachable by discovery -- Entertainment alone is 2,536, the
    largest block on the exchange. `--series-match` on any of them swept
    nothing regardless of what else was passed.
    """
    import find_momentum as fm
    for name in ("Entertainment", "Politics", "Companies", "World", "Health",
                 "Transportation"):
        assert name in fm.CATEGORIES, f"{name} unreachable by the scanner"
    # Elections and Politics are different live groupings, not synonyms
    assert "Elections" in fm.CATEGORIES and "Politics" in fm.CATEGORIES
    # Culture serves `"series": null` and is deliberately excluded
    assert "Culture" not in fm.CATEGORIES


def _dated(rows, name="KXIMPEACH"):
    """Legs whose ORDER exists only in the human label, not the ticker."""
    return [{"ticker": f"{name}-{tail}", "event_ticker": name,
             "yes_sub_title": label, "mutually_exclusive": False,
             "yes_ask_dollars": f"{a / 100:.4f}",
             "yes_bid_dollars": f"{max(a - 1, 0) / 100:.4f}"}
            for tail, label, a in rows]


def test_a_date_ladder_orders_by_its_label_when_the_ticker_cannot():
    """KXIMPEACH (live): a rising "before date D" ladder at 1.0 / 3.8 / 21.0 /

    59.0 cents. Its tails are SEP01 / JAN01 / MAR01 / JAN01 -- month-day
    fragments with no year, and TWO ARE IDENTICAL (Jan 1 2027 vs Jan 1 2028).
    No ticker rule can order that, so it was demoted to independent_basket,
    whose advice ("the ask-sum has NO meaning, read each leg on its own") is
    exactly wrong for a cumulative distribution.
    """
    recs = _dated([("SEP01", "Before Sep 1, 2026", 1.0),
                   ("JAN01", "Before Jan 1, 2027", 3.8),
                   ("MAR01", "Before Mar 1, 2027", 21.0),
                   ("JAN01", "Before Jan 1, 2028", 59.0)])
    assert mf.is_threshold_ladder(recs)
    assert not mf._flag_only_ladder(recs)
    info = list(mf.ask_sums_by_event(recs).values())[0]
    assert info["structure"] == "threshold_ladder"
    assert info["premium_cents"] is None


def test_heterogeneous_date_tails_still_order():
    """KXSCOTUSN (live) mixes 26OCT / 27 / 27MAY31 / 28 / 29JAN20 in one event."""
    recs = _dated([("26OCT", "Before Oct 1, 2026", 1.0),
                   ("27", "Before 2027", 10.0),
                   ("27MAY31", "Before June 2027", 24.0),
                   ("28", "Before 2028", 86.0),
                   ("29JAN20", "Before Jan 21, 2029", 82.0)], name="KXSCOTUSN-25DEC31")
    assert mf.is_threshold_ladder(recs)


def test_a_basket_of_people_is_not_turned_into_a_date_ladder():
    """KXFEDGOVNOM (live): 12 Fed nominees. Their labels are PERSON NAMES, so

    no date can be read from them and the event stays a genuine basket. This
    is what stops the subtitle rule from swallowing every ME=False event.
    """
    recs = _dated([("CWAL", "Christopher Waller", 3.0),
                   ("JSHE", "Judy Shelton", 9.1),
                   ("KHAS", "Kevin Hassett", 7.4),
                   ("SMIR", "Stephen Miran", 12.0)], name="KXFEDGOVNOM-27")
    assert all(mf._subtitle_date_ordinal(r) is None for r in recs)
    info = list(mf.ask_sums_by_event(recs).values())[0]
    assert info["structure"] == "independent_basket"


def test_subtitle_date_ordinals_sort_chronologically():
    o = mf._subtitle_date_ordinal
    seq = [o({"yes_sub_title": s}) for s in
           ("Before Sep 1, 2026", "Before Jan 1, 2027",
            "Before Mar 1, 2027", "Before Jan 1, 2028")]
    assert seq == sorted(seq) and len(set(seq)) == 4
    assert o({"yes_sub_title": "Christopher Waller"}) is None
    assert o({"yes_sub_title": ""}) is None
    assert o({}) is None


def test_an_expected_count_basket_is_not_called_fixed_cardinality():
    """The bracket alone is NOT evidence, and this is where it misled.

    On a genuine independent basket the ask-sum IS the expected number of
    legs that resolve yes, so it always brackets SOME integer. Live proof:
    KXMLBHR-26AUG191310SDNYM (35 players, "records 1+ home runs") asks 213c
    against 158c of bids and bracketed "exactly 2"; KXNFLSEASONPASSYDS-27C4000
    (30 quarterbacks, "records 4000+ passing yards") asks 1017c against 555c
    and bracketed "6-10". Any number of players can homer and any number of
    quarterbacks can pass for 4000 yards -- neither is constrained.
    """
    for legs, ask, bid, rules in [
            (35, 213.0, 158.0, "If Xander Bogaerts records 2+ home runs in "
                               "San Diego vs New York M professional baseball game"),
            (30, 1017.0, 555.0, "If Tyler Shough records 4000+ passing yards "
                                "during the 2026-27 Pro Football regular season")]:
        recs = _basket(legs, ask, bid, rules=rules)
        assert mf.fixed_cardinality_range(ask, bid) is not None, "bracket does fire"
        assert mf.stated_cardinality(recs) is None, "but no rank constraint is stated"
        info = list(mf.ask_sums_by_event(recs).values())[0]
        assert info["note"] == mf.BASKET_NOTE, f"{legs} legs wrongly constrained"


def test_a_rank_phrase_whose_book_disagrees_is_flagged_not_asserted():
    """Both signals must agree before a constraint is CLAIMED -- but a stated

    K that the book does not bracket is itself worth saying, not worth
    hiding behind "the ask-sum has no meaning".

    Live case: KXCHESSFIDERATINGTOP-26OCTWOMENT10 names ten places and asked
    998c against 920c of bids. On a ten-place partition the ask side has a
    floor near 1000c, so 998c is the interesting number -- 7 of its 8 sibling
    events bracketed their K cleanly and this one did not.
    """
    recs = _basket(20, 400.0, 300.0, rules="finishes in the top 10 of the race")
    assert mf.stated_cardinality(recs) == 10
    assert mf.fixed_cardinality_range(400.0, 300.0) == (3, 4)   # excludes 10
    info = list(mf.ask_sums_by_event(recs).values())[0]
    assert info["note"] != mf.BASKET_NOTE
    assert "10-place constraint" in info["note"]
    assert info["premium_cents"] is None


def test_stated_cardinality_reads_rank_phrases_only():
    assert mf.stated_cardinality([{"rules_primary": "is rated top 10 on the list"}]) == 10
    assert mf.stated_cardinality([{"rules_primary": "finishes in the top 3"}]) == 3
    assert mf.stated_cardinality([{"rules_primary": "records 2+ home runs"}]) is None
    assert mf.stated_cardinality([{"rules_primary": "4000+ passing yards"}]) is None
    assert mf.stated_cardinality([{"rules_primary": "top 1 seed"}]) is None   # K<2
    assert mf.stated_cardinality([{}]) is None


def test_empty_analog_detection_counts_the_section_not_the_file(tmp_path):
    """The count that drove backfill priority was wrong for days.

    A naive `grep -l "None recorded"` counts any file MENTIONING the phrase,
    including hubs and briefs that quote it while describing the schema. The
    real question is whether the ## Historical Analog SECTION still says it.
    """
    import backfill_probe as bp

    (tmp_path / "Market - Empty.md").write_text(
        'aliases:\n  - "KXTHING"\ntags:\n  - market\n\n'
        "## Historical Analog\n\nNone recorded.\n\n## Update Log\n- x\n",
        encoding="utf-8")
    (tmp_path / "Market - Filled.md").write_text(
        'aliases:\n  - "KXOTHER"\ntags:\n  - market\n\n'
        "## Historical Analog\n\nMeasured: 5 of 10.\n\n## Update Log\n- x\n",
        encoding="utf-8")
    # quotes the phrase OUTSIDE its own analog section -- a naive grep counts it
    (tmp_path / "Market - Quotes.md").write_text(
        'aliases:\n  - "KXQUOTE"\ntags:\n  - market\n\n'
        '## Resolution Rules\n\nWrite "None recorded." when nothing is known.\n\n'
        "## Historical Analog\n\nMeasured: 1 of 2.\n\n## Update Log\n- x\n",
        encoding="utf-8")

    found = bp.empty_analog_notes(tmp_path)
    assert set(found) == {"Market - Empty"}, found
    assert found["Market - Empty"] == ["KXTHING"]


def test_a_note_with_no_ticker_alias_is_not_probed(tmp_path):
    """Aliases are the only note -> ticker mapping; filenames carry archetype

    names, not tickers. A note naming no contract cannot be probed at all.
    """
    import backfill_probe as bp
    (tmp_path / "Market - Nameless.md").write_text(
        'aliases:\n  - "Market: Nameless"\ntags:\n  - market\n\n'
        "## Historical Analog\n\nNone recorded.\n\n## Update Log\n- x\n",
        encoding="utf-8")
    assert bp.empty_analog_notes(tmp_path) == {}


def test_fixed_cardinality_is_confirmed_by_settled_outcomes():
    """The constraint is not a heuristic -- the settled feed proves it.

    Across 20 settled KXNASCARTOP10 races, EXACTLY 10 legs resolved yes every
    single time (mean 10.00, zero variance) on fields of 33-39 drivers,
    because ten drivers finish in the top ten by construction. The genuine
    independent basket measured the same way, KXRAIN, averages 4.17 of 20
    cities and varies every day.

    This test pins the classifier to that observed difference: a RANK phrase
    plus a bracket containing its K is called constrained; a THRESHOLD phrase
    never is, however the arithmetic happens to fall.
    """
    top10 = _basket(38, 1050.0, 960.0,
                    rules="If D. L. Wilson finishes in the top 10 in the main "
                          "race at the 2026 NASCAR Team EJP 175")
    assert mf.stated_cardinality(top10) == 10
    info = list(mf.ask_sums_by_event(top10).values())[0]
    assert "exactly 10" in info["note"]

    rain = _basket(20, 490.0, 444.0,
                   rules="If the total precipitation at CLISFO in San "
                         "Francisco in Aug 20, 2026 is strictly greater than 0")
    assert mf.stated_cardinality(rain) is None
    info = list(mf.ask_sums_by_event(rain).values())[0]
    assert info["note"] == mf.BASKET_NOTE


def _handicap(margins, name="KXNFLSPREAD-26X"):
    """Both teams listed at each margin -- floor_strike is UNSIGNED."""
    recs = []
    for m in margins:
        for team in ("HOU", "LVR"):
            recs.append({"ticker": f"{name}-{team}{int(m)}", "event_ticker": name,
                         "floor_strike": m, "mutually_exclusive": False,
                         "yes_ask_dollars": "0.5000", "yes_bid_dollars": "0.4500"})
    return recs


def test_a_two_sided_handicap_is_neither_a_ladder_nor_a_basket():
    """KXNFL1QSPREAD / KXNFLSPREAD (live): both teams at the same margins.

    `threshold_ladder` claims one cumulative distribution, but HOU-over-3.5
    and LVR-over-3.5 cannot both win. `independent_basket` says "read each leg
    on its own", but rungs on the SAME team are strictly nested. The repo gave
    period spreads the first label and full-game spreads the second -- one
    archetype, two wrong answers, decided by which event you read.
    """
    recs = _handicap([2.5, 3.5, 6.5, 7.5, 10.5])
    assert mf.is_two_sided_handicap(recs)
    info = list(mf.ask_sums_by_event(recs).values())[0]
    assert info["structure"] == "two_sided_handicap"
    assert info["premium_cents"] is None
    assert info["note"] == mf.TWO_SIDED_HANDICAP_NOTE


def test_one_strike_repeated_many_times_is_a_basket_not_a_handicap():
    """The false positive the first version produced.

    KXRAIN lists 20 cities that ALL carry floor_strike 0.0 ("more than zero
    precipitation"). That is one strike twenty times over -- a genuine
    independent basket. A handicap has MANY margins each repeated EXACTLY
    twice, because there are exactly two sides.
    """
    # real cities carry DIFFERENT rain probabilities on the same strike
    asks = [9, 47, 12, 63, 8, 31, 55, 6, 22, 74,
            17, 41, 5, 68, 13, 29, 51, 7, 36, 19]
    recs = [{"ticker": f"KXRAIN-26AUG19-C{i}", "event_ticker": "KXRAIN-26AUG19",
             "floor_strike": 0.0, "mutually_exclusive": False,
             "yes_ask_dollars": f"{a / 100:.4f}",
             "yes_bid_dollars": f"{max(a - 3, 0) / 100:.4f}"}
            for i, a in enumerate(asks)]
    assert not mf.is_two_sided_handicap(recs)
    info = list(mf.ask_sums_by_event(recs).values())[0]
    assert info["structure"] == "independent_basket"


def test_a_one_sided_ladder_never_repeats_a_strike():
    """Totals, CPI, season wins: measured live, ZERO duplicated strikes."""
    recs = [{"ticker": f"KXMLBTOTAL-26X-{k}", "event_ticker": "KXMLBTOTAL-26X",
             "floor_strike": float(k), "mutually_exclusive": False,
             "yes_ask_dollars": f"{(100 - 7 * k) / 100:.4f}",
             "yes_bid_dollars": f"{(98 - 7 * k) / 100:.4f}"}
            for k in range(3, 12)]
    assert not mf.is_two_sided_handicap(recs)
    assert mf.is_threshold_ladder(recs)


def test_a_two_margin_handicap_is_still_a_handicap():
    """My first rule required >=3 distinct margins and MISSED the common case.

    Live evidence: KXMLSSPREAD, KXLALIGASPREAD, KXUCLSPREAD and KXMLBF5SPREAD
    are all 4 legs -- two teams at 1.5 and 2.5 -- and every one was being
    called a `threshold_ladder`. Soccer and first-five-innings books simply do
    not list deep margins.
    """
    assert mf.is_two_sided_handicap(_handicap([3.5, 6.5]))
    assert mf.is_two_sided_handicap(_handicap([3.5, 6.5, 9.5]))
    # ...and ONE margin per team is still two-sided. Twelve live first-half
    # soccer spreads (KXLALIGA1HSPREAD, KXUCL1HSPREAD, KXMLS1HSPREAD and nine
    # more) list exactly two legs -- "Vallecano wins the 1H by more than 1.5"
    # against its opponent -- and were the last books still mislabelled.
    assert mf.is_two_sided_handicap(_handicap([3.5]))


def test_a_two_leg_moneyline_is_not_a_handicap():
    """The floor is 2 legs, so the STRIKE guard is what protects moneylines.

    KXMLBGAME and KXNFLGAME are two legs with two sides and no floor_strike at
    all, so they never reach the handicap test.
    """
    recs = [{"ticker": f"KXMLBGAME-26X-{t}", "event_ticker": "KXMLBGAME-26X",
             "mutually_exclusive": True,
             "yes_ask_dollars": a, "yes_bid_dollars": b}
            for t, a, b in [("ATL", "0.5500", "0.5400"), ("MIL", "0.4700", "0.4600")]]
    assert not mf.is_two_sided_handicap(recs)
    info = list(mf.ask_sums_by_event(recs).values())[0]
    assert info["structure"] == "exclusive_field"


def test_an_asymmetric_handicap_is_caught_by_counting_sides():
    """KXATPGSPREAD quotes the two players at DIFFERENT margins -- Tiafoe at

    -1.5 against Auger-Aliassime at -2.5 and -5.5 -- so no strike repeats and
    a duplicate-counting rule cannot see it. Counting distinct subject tokens
    in the leg tickers does.
    """
    recs = [{"ticker": "KXATPGSPREAD-26AUG19TIAAUG-TIA2", "event_ticker": "E",
             "floor_strike": 1.5, "mutually_exclusive": False,
             "yes_ask_dollars": "0.5500", "yes_bid_dollars": "0.5000"},
            {"ticker": "KXATPGSPREAD-26AUG19TIAAUG-AUG3", "event_ticker": "E",
             "floor_strike": 2.5, "mutually_exclusive": False,
             "yes_ask_dollars": "0.3500", "yes_bid_dollars": "0.3000"},
            {"ticker": "KXATPGSPREAD-26AUG19TIAAUG-AUG6", "event_ticker": "E",
             "floor_strike": 5.5, "mutually_exclusive": False,
             "yes_ask_dollars": "0.1500", "yes_bid_dollars": "0.1000"}]
    assert mf.is_two_sided_handicap(recs)


def test_many_subjects_is_a_basket_not_two_sides():
    """A handicap has EXACTLY two sides. KXRAIN has twenty cities and

    KXNASCARTOP10 forty-one drivers -- many subjects, not two.
    """
    rain = [{"ticker": f"KXRAIN-26AUG19-CITY{i}", "event_ticker": "R",
             "floor_strike": 0.0, "mutually_exclusive": False,
             "yes_ask_dollars": "0.2000", "yes_bid_dollars": "0.1700"}
            for i in range(20)]
    assert not mf.is_two_sided_handicap(rain)
