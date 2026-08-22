"""Tests for reassembling a recorded event into a strike ladder.

The defect this module exists to prevent is recorded in its docstring: a
first pass at arbitrage scanning applied the PARTITION invariant to
CUMULATIVE ladders and reported 16 violations, every one false. Several
tests below pin that distinction directly.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent.ladder import (Ladder, Rung, ladders_from_rows, parse_expiry_ts,
                          parse_strike)


def _rows(strikes_and_mids, event="KXBTCD-26AUG2017", ts=100, spread=2):
    """`mid` is given as a PROBABILITY (0-1); the recorder stores CENTS."""
    out = []
    for k, mid in strikes_and_mids:
        c = mid * 100.0
        out.append({"ts": ts, "event_ticker": event,
                    "ticker": f"{event}-T{k}",
                    "yes_bid_c": c - spread / 2, "yes_ask_c": c + spread / 2})
    return out


# ------------------------------------------------------------- parsing

def test_the_strike_is_recovered_from_the_ticker():
    """The recorder saves quotes, not strikes, so a historical ladder is only
    rebuildable if the ticker carries the strike."""
    assert parse_strike("KXBTCD-26AUG2017-T73749.99") == 73749.99
    assert parse_strike("KXBTCD-26AUG2201-T69100") == 69100.0


def test_a_ticker_with_no_strike_yields_none():
    """Game moneylines are not ladder legs and must not be forced into one."""
    assert parse_strike("KXMLBGAME-26AUG231910ATLMIL-MIL") is None
    assert parse_strike("") is None
    assert parse_strike("garbage") is None


def test_the_expiry_is_recovered_including_the_hour():
    """26AUG2017 is 2026-08-20 17:00 UTC -- year, month, day, then hour. An
    off-by-one here silently rescales every implied vol through sqrt(T)."""
    import datetime as dt
    ts = parse_expiry_ts("KXBTCD-26AUG2017-T69100")
    got = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
    assert (got.year, got.month, got.day, got.hour) == (2026, 8, 20, 17)


def test_a_dateonly_event_expires_at_end_of_day():
    import datetime as dt
    ts = parse_expiry_ts("KXCPIYOY-26NOV-T3.4")
    assert ts is None or dt.datetime.fromtimestamp(ts, dt.timezone.utc).hour == 23


def test_an_unparseable_expiry_yields_none_not_a_guess():
    assert parse_expiry_ts("KXBTCD-ZZZZZZ-T100") is None


# --------------------------------------------------- cumulative, not partition

def test_a_cumulative_ladders_legs_sum_far_above_one_and_that_is_correct():
    """THE 16 FALSE POSITIVES. Legs of a `greater` ladder are NESTED, not
    disjoint: P(X>=68.5k) + P(X>=69.1k) + ... exceeds 1 by construction. Any
    scanner that reads that as arbitrage is measuring its own confusion."""
    lad = ladders_from_rows(_rows([(1, 0.90), (2, 0.70), (3, 0.50),
                                   (4, 0.30), (5, 0.10)]))[
        ("KXBTCD-26AUG2017", 100)]
    assert sum(lad.mids) == pytest.approx(2.5)
    assert not lad.monotonicity_violations(), "a nested ladder is still valid"


def test_the_density_sums_to_the_mass_the_ladder_actually_spans():
    """First difference of a cumulative ladder. It does NOT sum to 1 -- only
    to the probability between the lowest and highest strike."""
    lad = ladders_from_rows(_rows([(1, 0.90), (2, 0.70), (3, 0.50),
                                   (4, 0.30), (5, 0.10)]))[
        ("KXBTCD-26AUG2017", 100)]
    assert sum(p for _, p in lad.density()) == pytest.approx(0.80)
    assert lad.mass_captured() == pytest.approx(0.80)


def test_a_ladder_spanning_little_of_the_distribution_is_flagged():
    """A narrow window pins the forward inside itself whatever the market
    believes, so its moments are meaningless and callers must be able to
    refuse it."""
    narrow = ladders_from_rows(_rows([(1, 0.55), (2, 0.52), (3, 0.50),
                                      (4, 0.48), (5, 0.45)]))[
        ("KXBTCD-26AUG2017", 100)]
    assert narrow.mass_captured() == pytest.approx(0.10)


# ------------------------------------------------------------ violations

def test_a_rising_price_with_strike_is_reported():
    """P(X>=K) must fall as K rises. This one really is impossible."""
    lad = ladders_from_rows(_rows([(1, 0.50), (2, 0.60), (3, 0.40),
                                   (4, 0.30), (5, 0.10)]))[
        ("KXBTCD-26AUG2017", 100)]
    v = lad.monotonicity_violations()
    assert len(v) == 1 and v[0][0] == 0


def test_negative_density_mass_is_reported_not_clipped():
    """A negative mass is EVIDENCE about the book. Clipping it to zero would
    delete the very signal an arbitrage scanner looks for."""
    lad = ladders_from_rows(_rows([(1, 0.50), (2, 0.60), (3, 0.10)]),
                            min_rungs=3)[("KXBTCD-26AUG2017", 100)]
    masses = [p for _, p in lad.density()]
    assert any(m < 0 for m in masses)


# --------------------------------------------------------------- moments

def test_the_forward_is_the_probability_weighted_mean_strike():
    lad = Ladder("E", 0, None, [Rung(100, 99, 101), Rung(200, 49, 51),
                                Rung(300, -1, 1)])
    # masses: 1.00-0.50 = 0.50 at midpoint 150; 0.50-0.00 = 0.50 at 250
    assert lad.forward() == pytest.approx(200.0)


def test_a_wider_distribution_has_a_larger_standard_deviation():
    tight = Ladder("E", 0, None, [Rung(90, 99, 101), Rung(100, 49, 51),
                                  Rung(110, -1, 1)])
    wide = Ladder("E", 0, None, [Rung(10, 99, 101), Rung(100, 49, 51),
                                 Rung(190, -1, 1)])
    assert wide.stdev() > tight.stdev() * 5


def test_moments_return_none_when_the_ladder_carries_no_mass():
    flat = Ladder("E", 0, None, [Rung(1, 50, 50), Rung(2, 50, 50)])
    assert flat.forward() is None
    assert flat.stdev() is None
    assert flat.skew() is None
    assert flat.kurtosis() is None


def test_excess_kurtosis_is_zero_for_a_flat_two_point_distribution():
    """Excess, not raw: 0 means normal-tailed. Reporting raw kurtosis would
    make every symmetric distribution look fat-tailed by 3."""
    lad = Ladder("E", 0, None, [Rung(0, 100, 100), Rung(100, 50, 50),
                                Rung(200, 0, 0)])
    k = lad.kurtosis()
    assert k is not None and k < 0, "a two-point mass is thin-tailed"


# --------------------------------------------------------------- assembly

def test_rows_group_into_one_ladder_per_event_and_timestamp():
    rows = _rows([(1, 0.9), (2, 0.5), (3, 0.1)], ts=100)
    rows += _rows([(1, 0.8), (2, 0.4), (3, 0.1)], ts=200)
    out = ladders_from_rows(rows, min_rungs=3)
    assert set(out) == {("KXBTCD-26AUG2017", 100), ("KXBTCD-26AUG2017", 200)}


def test_rungs_come_back_sorted_by_strike_whatever_order_they_arrived():
    rows = _rows([(3, 0.1), (1, 0.9), (2, 0.5)])
    lad = ladders_from_rows(rows, min_rungs=3)[("KXBTCD-26AUG2017", 100)]
    assert lad.strikes == [1.0, 2.0, 3.0]


def test_a_ladder_too_short_to_mean_anything_is_dropped():
    assert ladders_from_rows(_rows([(1, 0.9), (2, 0.5)]), min_rungs=5) == {}


def test_rows_without_quotes_are_skipped():
    rows = _rows([(1, 0.9), (2, 0.5), (3, 0.1)])
    rows[1]["yes_bid_c"] = None
    lad = ladders_from_rows(rows, min_rungs=2)[("KXBTCD-26AUG2017", 100)]
    assert len(lad.rungs) == 2


def test_time_to_expiry_is_positive_before_expiry_and_zero_after():
    lad = Ladder("E", ts=0.0, expiry_ts=365 * 24 * 3600.0, rungs=[])
    assert lad.t_years == pytest.approx(1.0)
    expired = Ladder("E", ts=1000.0, expiry_ts=500.0, rungs=[])
    assert expired.t_years == 0.0
