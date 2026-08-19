import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from book_recorder import SNAPSHOT_FIELDS, snapshot_from_market


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
