"""Order translation. Pure functions, no network -- assert the wire format."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.config import ORDER_STP, ORDER_TIME_IN_FORCE
from agent.nodes import (build_exit_payload, build_order_payload,
                         translate_side)
from agent.portfolio import Position


# ---------------------------------------------------------------- translate
def test_open_yes_is_a_bid_at_face_price():
    assert translate_side("yes", 63.0, action="open") == ("bid", 63.0)


def test_open_no_is_an_ask_at_the_complement():
    # buying NO at 22c == selling YES at 78c; we still only pay 22c
    assert translate_side("no", 22.0, action="open") == ("ask", 78.0)


def test_close_yes_sells_the_yes_leg():
    assert translate_side("yes", 70.0, action="close") == ("ask", 70.0)


def test_close_no_buys_the_yes_leg_back():
    assert translate_side("no", 30.0, action="close") == ("bid", 70.0)


def test_side_none_refuses_to_build():
    with pytest.raises(ValueError):
        translate_side("none", 50.0)


@pytest.mark.parametrize("bad", ["", "YES", "buy", None, "yes "])
def test_unknown_sides_refuse_to_build(bad):
    with pytest.raises(ValueError):
        translate_side(bad, 50.0)


def test_bad_action_refuses():
    with pytest.raises(ValueError):
        translate_side("yes", 50.0, action="flatten")


def test_open_then_close_round_trips_to_the_same_yes_price():
    """A NO entry and its exit must sit on the same YES-leg price scale."""
    _, open_px = translate_side("no", 22.0, action="open")
    _, close_px = translate_side("no", 22.0, action="close")
    assert open_px == close_px == 78.0


# ---------------------------------------------------------------- payloads
def test_entry_payload_yes_matches_v2_schema():
    order = build_order_payload(
        {"ticker": "KXTEST-YES"},
        {"side": "yes"},
        {"limit_price_cents": 63.0, "size_contracts": 10, "size_usd": 6.30},
    )
    assert order["side"] == "bid"
    assert order["price"] == "0.6300"
    assert order["count"] == "10.00"
    assert order["ticker"] == "KXTEST-YES"
    assert order["time_in_force"] == ORDER_TIME_IN_FORCE == "immediate_or_cancel"
    assert order["self_trade_prevention_type"] == ORDER_STP
    assert order["client_order_id"].startswith("agent-")


def test_entry_payload_no_pays_22_cents():
    order = build_order_payload(
        {"ticker": "KXTEST-NO"},
        {"side": "no"},
        {"limit_price_cents": 22.0, "size_contracts": 5, "size_usd": 1.10},
    )
    assert order["side"] == "ask"
    assert order["price"] == "0.7800"
    # sanity: selling YES at 78c is a 22c NO entry
    assert round(100 - float(order["price"]) * 100, 4) == 22.0


def test_entry_payload_none_raises():
    with pytest.raises(ValueError):
        build_order_payload({"ticker": "X"}, {"side": "none"},
                            {"limit_price_cents": 50.0, "size_contracts": 1,
                             "size_usd": 0.5})


def test_exit_payload_mirrors_the_entry_side():
    pos = Position(ticker="KXTEST-NO", side="no", size_contracts=5,
                   entry_price_cents=22.0, cost_usd=1.10)
    entry = build_order_payload({"ticker": "KXTEST-NO"}, {"side": "no"},
                                {"limit_price_cents": 22.0,
                                 "size_contracts": 5, "size_usd": 1.10})
    exit_ = build_exit_payload(pos, 30.0)
    assert entry["side"] == "ask" and exit_["side"] == "bid"
    assert exit_["price"] == "0.7000"      # sell NO at 30c == buy YES at 70c
    assert exit_["count"] == "5.00"
