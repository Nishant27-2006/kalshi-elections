"""Exit logic. Nothing in this repo sold anything before agent/exits.py."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.config import ExitLimits
from agent.exits import default_levels, evaluate_exit
from agent.portfolio import Position

LIM = ExitLimits(take_profit_multiple=2.0, stop_loss_fraction=0.5,
                 time_exit_buffer_hours=6.0, min_stoppable_entry_cents=3.0)
NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)


def _yes(entry=20.0, **kw):
    tp, sl, hold = default_levels(entry, LIM)
    d = dict(ticker="KXYES", side="yes", size_contracts=100,
             entry_price_cents=entry, cost_usd=entry,
             take_profit_cents=tp, stop_loss_cents=sl, hold_to_resolution=hold)
    d.update(kw)
    return Position(**d)


def _no(entry=22.0, **kw):
    tp, sl, hold = default_levels(entry, LIM)
    d = dict(ticker="KXNO", side="no", size_contracts=100,
             entry_price_cents=entry, cost_usd=entry,
             take_profit_cents=tp, stop_loss_cents=sl, hold_to_resolution=hold)
    d.update(kw)
    return Position(**d)


def q(bid, ask):
    return {"yes_bid_cents": bid, "yes_ask_cents": ask}


# ---------------------------------------------------------------- marking
def test_yes_position_marks_at_the_yes_bid():
    """We exit by hitting the bid, never by marking our own ask."""
    assert _yes().mark_price_cents(q(31, 35)) == 31.0


def test_no_position_marks_at_100_minus_the_yes_ask():
    assert _no().mark_price_cents(q(31, 35)) == 65.0


def test_unrealized_pnl_uses_the_hittable_price():
    pos = _yes(entry=20.0)                      # 100 contracts @ 20c
    assert pos.unrealized_usd(q(31, 35)) == pytest.approx(11.0)


# ---------------------------------------------------------------- levels
def test_default_levels_are_2x_up_and_half_down():
    assert default_levels(20.0, LIM) == (40.0, 10.0, False)


def test_take_profit_is_capped_below_100():
    tp, _, _ = default_levels(60.0, LIM)
    assert tp == 97.0, "a 2x on 60c would be 120c, which is not a price"


def test_sub_tick_stop_becomes_hold_to_resolution():
    """A 50% stop on a 1.3c longshot is 0.65c -- not a quotable price.

    This is the Fishback case. The honest handling is no stop at all, not a
    stop that silently rounds to 1c and calls a 23% loss a 50% one.
    """
    tp, sl, hold = default_levels(1.3, LIM)
    assert sl is None
    assert hold is True
    assert tp == 2.6


# ---------------------------------------------------------------- triggers
def test_take_profit_fires_on_a_yes_position():
    d = evaluate_exit(_yes(entry=20.0), q(41, 45), now=NOW, limits=LIM)
    assert d["should_exit"] and d["kind"] == "take_profit"
    assert d["exit_price_cents"] == 41.0


def test_stop_loss_fires_on_a_yes_position():
    d = evaluate_exit(_yes(entry=20.0), q(9, 12), now=NOW, limits=LIM)
    assert d["should_exit"] and d["kind"] == "stop_loss"


def test_stop_loss_fires_on_a_no_position():
    # NO entered at 22c; stop is 11c; NO mark = 100 - ask
    d = evaluate_exit(_no(entry=22.0), q(85, 92), now=NOW, limits=LIM)
    assert d["should_exit"] and d["kind"] == "stop_loss"
    assert d["exit_price_cents"] == 8.0


def test_stop_wins_when_a_gap_crosses_both_levels():
    """Impossible in one quote for a sane book, but a crossed/stale book can
    do it. Booking the win would be the optimistic read; take the stop."""
    pos = _yes(entry=20.0, take_profit_cents=5.0, stop_loss_cents=10.0)
    d = evaluate_exit(pos, q(4, 6), now=NOW, limits=LIM)
    assert d["kind"] == "stop_loss"


def test_no_trigger_holds():
    d = evaluate_exit(_yes(entry=20.0), q(25, 28), now=NOW, limits=LIM)
    assert d["should_exit"] is False and d["kind"] == "hold"


# ---------------------------------------------------------------- time exit
def test_time_exit_fires_inside_the_buffer():
    close = (NOW + timedelta(hours=5)).isoformat()
    d = evaluate_exit(_yes(entry=20.0, close_ts=close), q(25, 28),
                      now=NOW, limits=LIM)
    assert d["should_exit"] and d["kind"] == "time"


def test_time_exit_does_not_fire_outside_the_buffer():
    close = (NOW + timedelta(hours=7)).isoformat()
    d = evaluate_exit(_yes(entry=20.0, close_ts=close), q(25, 28),
                      now=NOW, limits=LIM)
    assert d["should_exit"] is False


def test_hold_to_resolution_survives_the_time_exit():
    close = (NOW + timedelta(hours=1)).isoformat()
    pos = _yes(entry=1.3, close_ts=close)          # sub-tick -> hold flag set
    assert pos.hold_to_resolution
    d = evaluate_exit(pos, q(2, 3), now=NOW, limits=LIM)
    assert d["should_exit"] is False
    assert "hold to resolution" in d["reason"]


def test_hold_to_resolution_still_takes_profit():
    """Holding to resolution is not the same as never taking a 2x."""
    pos = _yes(entry=1.3, close_ts=(NOW + timedelta(hours=1)).isoformat())
    d = evaluate_exit(pos, q(4, 6), now=NOW, limits=LIM)
    assert d["should_exit"] and d["kind"] == "take_profit"


def test_unparseable_close_ts_does_not_crash_or_exit():
    d = evaluate_exit(_yes(entry=20.0, close_ts="not-a-date"), q(25, 28),
                      now=NOW, limits=LIM)
    assert d["should_exit"] is False


def test_naive_close_ts_is_treated_as_utc():
    close = (NOW + timedelta(hours=5)).replace(tzinfo=None).isoformat()
    d = evaluate_exit(_yes(entry=20.0, close_ts=close), q(25, 28),
                      now=NOW, limits=LIM)
    assert d["should_exit"] and d["kind"] == "time"


# ---------------------------------------------------------------- degenerate
def test_one_sided_book_cannot_be_exited():
    d = evaluate_exit(_yes(entry=20.0), q(0, 45), now=NOW, limits=LIM)
    assert d["should_exit"] is False
    assert "no two-sided quote" in d["reason"]


def test_missing_quote_fields_hold():
    d = evaluate_exit(_yes(entry=20.0), {}, now=NOW, limits=LIM)
    assert d["should_exit"] is False
