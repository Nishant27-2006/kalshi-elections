import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json

from book_recorder import SNAPSHOT_FIELDS, snapshot_from_market, append_snapshots, record_once


def _market(**over):
    m = {"ticker": "KXMLBGAME-26AUG22ATLMIL-MIL",
         "event_ticker": "KXMLBGAME-26AUG22ATLMIL",
         "yes_bid_dollars": "0.4500", "yes_ask_dollars": "0.4700",
         "open_interest_fp": "6460.04", "volume_24h_fp": "6923.25"}
    m.update(over)
    return m


def test_a_snapshot_carries_every_declared_field():
    snap = snapshot_from_market(_market(), ts=1_700_000_000)
    assert set(snap) == set(SNAPSHOT_FIELDS)


def test_prices_are_read_from_the_dollars_strings_and_stored_as_cents():
    """The payload has NO yes_bid/yes_ask keys -- only the _dollars strings."""
    snap = snapshot_from_market(_market(), ts=1)
    assert snap["yes_bid_c"] == 45.0
    assert snap["yes_ask_c"] == 47.0
    assert snap["spread_c"] == 2.0


def test_size_fields_are_read_from_the_fp_strings():
    """open_interest / volume_24h DO NOT EXIST; only the _fp string forms."""
    snap = snapshot_from_market(_market(), ts=1)
    assert snap["oi"] == 6460.04
    assert snap["v24"] == 6923.25


def test_the_plain_field_names_are_ignored_even_if_present():
    """Guards against a future payload where both exist and disagree."""
    snap = snapshot_from_market(
        _market(open_interest=1.0, volume_24h=2.0), ts=1)
    assert snap["oi"] == 6460.04


def test_a_market_with_no_quotes_is_dropped():
    """A book with no bid AND no ask carries no information to record."""
    assert snapshot_from_market(
        _market(yes_bid_dollars=None, yes_ask_dollars=None), ts=1) is None


def test_the_series_is_derived_from_the_ticker():
    snap = snapshot_from_market(_market(), ts=1)
    assert snap["series"] == "KXMLBGAME"


def test_snapshots_append_as_jsonl_without_rewriting(tmp_path):
    p = tmp_path / "book.jsonl"
    assert append_snapshots(p, [{"ts": 1, "ticker": "A"}]) == 1
    assert append_snapshots(p, [{"ts": 2, "ticker": "B"}]) == 1
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["ticker"] == "A"
    assert json.loads(lines[1])["ticker"] == "B"


def test_appending_nothing_creates_no_file(tmp_path):
    p = tmp_path / "book.jsonl"
    assert append_snapshots(p, []) == 0
    assert not p.exists()


def test_record_once_writes_one_row_per_quoted_market(tmp_path):
    class FakeClient:
        pass

    calls = []

    def fake_all_open(client, series):
        calls.append(series)
        return [{"ticker": f"{series}-X", "event_ticker": f"{series}-E",
                 "yes_bid_dollars": "0.4000", "yes_ask_dollars": "0.4200",
                 "open_interest_fp": "10", "volume_24h_fp": "5"}]

    import book_recorder
    original = book_recorder._all_open_markets
    book_recorder._all_open_markets = fake_all_open
    try:
        p = tmp_path / "book.jsonl"
        n = record_once(FakeClient(), ["KXA", "KXB"], p, ts=99)
    finally:
        book_recorder._all_open_markets = original

    assert n == 2
    assert calls == ["KXA", "KXB"]
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]
    assert {r["series"] for r in rows} == {"KXA", "KXB"}
    assert all(r["ts"] == 99 for r in rows)


def test_a_dead_series_does_not_abort_the_sweep(tmp_path):
    """Invariant J: announce, do not crash. One bad series must not lose the
    whole recording pass."""
    import book_recorder

    def fake_all_open(client, series):
        if series == "KXBAD":
            raise RuntimeError("boom")
        return [{"ticker": f"{series}-X", "event_ticker": "E",
                 "yes_bid_dollars": "0.4000", "yes_ask_dollars": "0.4200",
                 "open_interest_fp": "1", "volume_24h_fp": "1"}]

    original = book_recorder._all_open_markets
    book_recorder._all_open_markets = fake_all_open
    try:
        p = tmp_path / "book.jsonl"
        n = record_once(object(), ["KXBAD", "KXGOOD"], p, ts=1)
    finally:
        book_recorder._all_open_markets = original
    assert n == 1
