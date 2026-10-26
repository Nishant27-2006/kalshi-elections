"""Market-list pagination.

The scanner took one `limit=50` page per series and reported nothing about
the rest. On KXCPIYOY that page held 50 legs across three months with zero
24h volume and missed the liquid T3.4 leg, so the series scored nothing and
looked inactive. On the FL political series it dropped 75 of 122 markets --
every earlier scan result was an arbitrary 40% sample.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from find_momentum import MAX_MARKET_PAGES, _all_open_markets


class FakeClient:
    """Serves markets in pages, mimicking Kalshi's cursor contract."""

    def __init__(self, total, page_size=200, endless=False):
        self.markets = [{"ticker": f"KX-26-L{i}"} for i in range(total)]
        self.page_size = page_size
        self.endless = endless
        self.calls = []

    def get(self, path, params=None):
        params = params or {}
        self.calls.append(params)
        start = int(params.get("cursor") or 0)
        page = self.markets[start:start + self.page_size]
        nxt = start + self.page_size
        cursor = str(nxt) if (self.endless or nxt < len(self.markets)) else None
        return {"markets": page, "cursor": cursor}


def test_a_single_page_series_needs_one_call():
    c = FakeClient(total=12)
    assert len(_all_open_markets(c, "KX")) == 12
    assert len(c.calls) == 1


def test_every_page_is_followed_to_the_end():
    c = FakeClient(total=470, page_size=200)
    out = _all_open_markets(c, "KX", page_size=200)
    assert len(out) == 470, "cursor must be followed until exhausted"
    assert len(c.calls) == 3


def test_no_duplicate_markets_across_pages():
    c = FakeClient(total=450, page_size=200)
    out = _all_open_markets(c, "KX", page_size=200)
    assert len({m["ticker"] for m in out}) == len(out)


def test_the_cursor_is_actually_sent_on_later_calls():
    c = FakeClient(total=300, page_size=200)
    _all_open_markets(c, "KX", page_size=200)
    assert "cursor" not in c.calls[0]
    assert c.calls[1].get("cursor") == "200"


def test_only_open_markets_are_requested():
    c = FakeClient(total=5)
    _all_open_markets(c, "KX")
    assert c.calls[0]["status"] == "open"
    assert c.calls[0]["series_ticker"] == "KX"


def test_a_runaway_cursor_stops_at_the_page_cap(capsys):
    """A server that never clears the cursor must not loop forever, and the
    truncation must be announced rather than silently returned."""
    c = FakeClient(total=100000, page_size=200, endless=True)
    out = _all_open_markets(c, "KX", page_size=200)
    assert len(c.calls) == MAX_MARKET_PAGES
    assert len(out) == MAX_MARKET_PAGES * 200
    assert "more remain" in capsys.readouterr().out


def test_an_empty_series_returns_empty_not_an_error():
    assert _all_open_markets(FakeClient(total=0), "KX") == []


# ------------------------------------------------- event-level structure flag
class FlagClient:
    """Serves the ME flag on the EVENT, as Kalshi actually does."""

    def __init__(self, flags):
        self.flags, self.calls = flags, []

    def get_event(self, ev):
        self.calls.append(ev)
        if ev not in self.flags:
            raise RuntimeError("no such event")
        return {"event": {"mutually_exclusive": self.flags[ev]}}


def test_event_flags_are_attached_to_market_records():
    """The /markets payload has NO mutually_exclusive -- it is event-level.
    Without this the classifier only ever saw None and fell back to shape,
    which cannot recognise an unordered field: KXRAIN came out exclusive_field
    with a +176c 'premium' that means nothing."""
    from find_momentum import attach_event_flags
    recs = [{"ticker": "KXRAIN-26AUG19-NYC", "event_ticker": "KXRAIN-26AUG19"},
            {"ticker": "KXRAIN-26AUG19-SFO", "event_ticker": "KXRAIN-26AUG19"}]
    c = FlagClient({"KXRAIN-26AUG19": False})
    assert attach_event_flags(c, recs) == 2
    assert all(r["mutually_exclusive"] is False for r in recs)


def test_event_flags_are_fetched_once_per_event():
    from find_momentum import attach_event_flags
    recs = [{"ticker": f"KXRAIN-26AUG19-{c}", "event_ticker": "KXRAIN-26AUG19"}
            for c in ("NYC", "SFO", "PHX", "MIA")]
    c = FlagClient({"KXRAIN-26AUG19": False})
    attach_event_flags(c, recs)
    assert c.calls == ["KXRAIN-26AUG19"], "must cache per event"


def test_a_failed_flag_lookup_leaves_the_record_unguessed(capsys):
    from find_momentum import attach_event_flags
    recs = [{"ticker": "KXX-26-A", "event_ticker": "KXX-26"}]
    assert attach_event_flags(FlagClient({}), recs) == 0
    assert recs[0].get("mutually_exclusive") is None
    assert "lookup failed" in capsys.readouterr().out
