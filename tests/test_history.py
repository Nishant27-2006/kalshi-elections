"""Verified base rates from settled markets.

Every `## Historical Analog` slot in this vault said "None recorded", because
the alternative was writing remembered facts (invariant K). This module closes
that gap by counting markets Kalshi has already settled -- an observation, not
a memory. These tests use fixtures; the live pull is exercised by the notes'
Update Log commands.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent.history as h
from agent.history import (BaseRate, SettledEvent, fetch_settled,
                           group_settled, ladder_hit_rate, winner_frequency,
                           yes_rate)


def leg(event, sub, result, ticker=None):
    return {"event_ticker": event, "yes_sub_title": sub, "result": result,
            "ticker": ticker or f"{event}-{sub[:4].upper()}"}


def three_way(event, winner):
    """One settled soccer-style match: home / away / tie, one winner."""
    return [leg(event, s, "yes" if s == winner else "no")
            for s in ("Home", "Away", "Tie")]


# ---------------------------------------------------------------- grouping
def test_settled_legs_group_into_events():
    ms = three_way("E1", "Home") + three_way("E2", "Tie")
    evs = group_settled(ms)
    assert {e.event for e in evs} == {"E1", "E2"}
    assert all(e.legs == 3 for e in evs)


def test_a_decided_event_has_exactly_one_winner():
    e = group_settled(three_way("E1", "Tie"))[0]
    assert e.decided is True and e.winners == ["Tie"] and e.losers == 2


def test_an_event_with_no_winner_is_not_decided():
    """Voided or postponed fixtures resolve every leg no."""
    ms = [leg("E1", s, "no") for s in ("Home", "Away", "Tie")]
    assert group_settled(ms)[0].decided is False


def test_a_ladder_event_is_not_decided():
    """A cumulative ladder resolves many legs yes at once, so 'the winner' is
    not a meaningful question for it."""
    ms = [leg("L1", f"T{n}", "yes" if n <= 3 else "no") for n in range(1, 7)]
    e = group_settled(ms)[0]
    assert len(e.winners) == 3 and e.decided is False


def test_grouping_falls_back_to_the_ticker_when_no_event_field():
    ms = [{"ticker": "KXUCLGAME-26JUL29ABC-TIE", "result": "yes",
           "yes_sub_title": "Tie"}]
    assert group_settled(ms)[0].event == "KXUCLGAME-26JUL29ABC"


# ---------------------------------------------------------------- base rates
def test_winner_frequency_counts_only_decided_events():
    ms = sum([three_way(f"E{i}", "Tie") for i in range(3)], []) \
        + sum([three_way(f"F{i}", "Home") for i in range(3)], []) \
        + [leg("VOID", s, "no") for s in ("Home", "Away", "Tie")]
    rates = {b.label: b for b in winner_frequency(group_settled(ms))}
    assert rates["Tie"].hits == 3 and rates["Tie"].total == 6
    assert rates["Tie"].rate == pytest.approx(0.5)


def test_winner_frequency_refuses_a_sample_too_small():
    """Publishing a rate from 3 events would look like evidence."""
    ms = sum([three_way(f"E{i}", "Tie") for i in range(3)], [])
    assert winner_frequency(group_settled(ms)) == []


def test_yes_rate_is_the_share_of_legs_resolving_yes():
    ms = sum([three_way(f"E{i}", "Home") for i in range(4)], [])
    r = yes_rate(ms)
    assert r.hits == 4 and r.total == 12
    assert r.rate == pytest.approx(1 / 3)


def test_yes_rate_refuses_a_small_sample():
    assert yes_rate([leg("E1", "A", "yes")]) is None


def test_yes_rate_ignores_unresolved_legs():
    ms = sum([three_way(f"E{i}", "Home") for i in range(4)], [])
    ms.append(leg("E9", "Pending", ""))
    assert yes_rate(ms).total == 12


def test_ladder_hit_rate_asks_whether_the_field_resolved_at_all():
    evs = group_settled(
        sum([three_way(f"E{i}", "Home") for i in range(5)], [])
        + [leg("VOID", s, "no") for s in ("A", "B", "C")])
    r = ladder_hit_rate(evs)
    assert r.hits == 5 and r.total == 6


def test_base_rate_renders_with_its_sample():
    """A rate without its sample size invites over-reading."""
    assert BaseRate("Tie", 19, 76).render() == "Tie: 19/76 = 25.0%"


def test_a_zero_sample_does_not_divide_by_zero():
    assert BaseRate("x", 0, 0).rate == 0.0


# ---------------------------------------------------------------- pagination
class FakeClient:
    def __init__(self, total, page_size=200, endless=False):
        self.markets = [{"event_ticker": f"E{i}", "result": "no",
                         "ticker": f"E{i}-L"} for i in range(total)]
        self.page_size, self.endless, self.calls = page_size, endless, []

    def get(self, path, params=None):
        params = params or {}
        self.calls.append(params)
        start = int(params.get("cursor") or 0)
        page = self.markets[start:start + self.page_size]
        nxt = start + self.page_size
        cursor = str(nxt) if (self.endless or nxt < len(self.markets)) else None
        return {"markets": page, "cursor": cursor}


def test_settled_history_follows_the_cursor():
    c = FakeClient(total=450)
    assert len(fetch_settled(c, "KX", page_size=200)) == 450
    assert len(c.calls) == 3
    assert c.calls[0]["status"] == "settled"


def test_settled_history_announces_truncation(capsys):
    """Silently returning a short history would read as the whole record."""
    c = FakeClient(total=100000, endless=True)
    fetch_settled(c, "KX", max_pages=3, page_size=200)
    assert "more history remains" in capsys.readouterr().out


def _leg(ev, name, result):
    return {"event_ticker": ev, "ticker": f"{ev}-{name[:3].upper()}",
            "yes_sub_title": name, "result": result}


def test_a_scalar_leg_is_not_counted_as_a_loss():
    """`result` has THREE values. Tennis settles a walkover or a mid-match

    retirement at "Fair Market Price, as determined at the sole discretion of
    the Exchange", and the feed reports `scalar`. Folding that into `losers`
    overstates the loser tally and hides a whole settlement branch: 35 of 944
    ATP matches and 38 of 956 WTA matches settled this way.
    """
    events = h.group_settled([_leg("KXATPMATCH-26AUG18FONOCO", "Joao Fonseca", "scalar"),
                              _leg("KXATPMATCH-26AUG18FONOCO", "C O'Connell", "scalar")])
    ev = events[0]
    assert ev.voided == 2
    assert ev.losers == 0, "a Fair Market Price settlement is not a loss"
    assert ev.winners == []
    assert ev.abandoned
    assert not ev.decided


def test_a_normal_event_reports_no_voided_legs():
    events = h.group_settled([_leg("KXATPMATCH-26AUG19JODCOB", "Rafael Jodar", "yes"),
                              _leg("KXATPMATCH-26AUG19JODCOB", "Flavio Cobolli", "no")])
    ev = events[0]
    assert (ev.voided, ev.losers, ev.decided, ev.abandoned) == (0, 1, True, False)


def test_void_rate_counts_events_not_legs():
    """A 2-leg match that voids is ONE abandoned event, not two."""
    legs = []
    for i in range(6):
        ev = f"KXATPMATCH-26AUG{i:02d}XX"
        res = "scalar" if i < 2 else ("yes", "no")
        if res == "scalar":
            legs += [_leg(ev, "A", "scalar"), _leg(ev, "B", "scalar")]
        else:
            legs += [_leg(ev, "A", "yes"), _leg(ev, "B", "no")]
    rate = h.void_rate(h.group_settled(legs))
    assert (rate.hits, rate.total) == (2, 6)
