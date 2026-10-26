"""Execution gate and the full open -> manage -> close cycle, offline.

No network: KalshiClient is never constructed because is_live() is False, and
the test asserts exactly that.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent.portfolio as portfolio_mod
from agent import nodes
from agent.portfolio import Portfolio

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    """Point the module-level ledger at a temp file for the whole test."""
    p = tmp_path / "positions.json"
    monkeypatch.setattr(portfolio_mod, "POSITIONS_PATH", p)
    return p


@pytest.fixture
def no_network(monkeypatch):
    """Explode if anything tries to build a Kalshi client."""
    def boom(*a, **k):
        raise AssertionError("network client constructed while not live")
    monkeypatch.setattr("kalshi_client.KalshiClient.from_env", boom)


APPROVED = {"approved": True, "reason": "ok", "size_contracts": 16,
            "size_usd": 10.08, "limit_price_cents": 63.0}
MARKET = {"ticker": "KXFL-TEST", "yes_bid_cents": 60.0, "yes_ask_cents": 63.0,
          "book_depth_contracts": 1000.0,
          "close_time": (NOW + timedelta(days=30)).isoformat()}
JUDGMENT = {"should_trade": True, "side": "yes", "fair_value_cents": 75.0,
            "confidence": 0.90}


def test_dry_run_does_not_execute_and_never_touches_the_network(ledger, no_network):
    out = nodes.execute_node({"risk": APPROVED, "market": MARKET,
                              "judgment": JUDGMENT})
    assert out["executed"] is False
    assert out["execution_result"]["status"] == "DRY_RUN"
    assert "is_live=False" in out["execution_result"]["detail"]


def test_dry_run_still_shows_the_order_it_would_have_sent(ledger, no_network):
    out = nodes.execute_node({"risk": APPROVED, "market": MARKET,
                              "judgment": JUDGMENT})
    would = out["execution_result"]["would_send"]
    assert would["side"] == "bid" and would["price"] == "0.6300"
    assert would["time_in_force"] == "immediate_or_cancel"


def test_paper_fill_lands_in_the_ledger_so_the_caps_bind(ledger, no_network):
    nodes.execute_node({"risk": APPROVED, "market": MARKET, "judgment": JUDGMENT})
    book = Portfolio.load()
    assert book.risk_state().open_tickers == ("KXFL-TEST",)
    pos = book.get("KXFL-TEST")
    assert pos.paper is True
    assert pos.entry_price_cents == 63.0
    assert pos.take_profit_cents == 97.0     # 2x63 capped
    assert pos.stop_loss_cents == 31.5


def test_a_rejected_decision_records_nothing(ledger, no_network):
    out = nodes.execute_node({"risk": {"approved": False, "reason": "no"},
                              "market": MARKET, "judgment": JUDGMENT})
    assert out["executed"] is False
    assert Portfolio.load().positions == []


def test_second_signal_on_the_same_ticker_is_blocked_by_the_risk_gate(ledger, no_network):
    """The cap that was previously dead: open once, then the gate refuses."""
    nodes.execute_node({"risk": APPROVED, "market": MARKET, "judgment": JUDGMENT})
    out = nodes.risk_node({"judgment": JUDGMENT, "market": MARKET})
    assert out["risk"]["approved"] is False
    assert "already hold" in out["risk"]["reason"]


# ---------------------------------------------------------------- exits
def test_manage_positions_holds_when_nothing_triggers(ledger, no_network):
    nodes.execute_node({"risk": APPROVED, "market": MARKET, "judgment": JUDGMENT})
    res = nodes.manage_positions({"KXFL-TEST": {"yes_bid_cents": 64.0,
                                                "yes_ask_cents": 66.0}}, now=NOW)
    assert res[0]["action"] == "hold"
    assert Portfolio.load().positions != []


def test_manage_positions_closes_on_a_stop_and_books_the_loss(ledger, no_network):
    nodes.execute_node({"risk": APPROVED, "market": MARKET, "judgment": JUDGMENT})
    res = nodes.manage_positions({"KXFL-TEST": {"yes_bid_cents": 30.0,
                                                "yes_ask_cents": 33.0}}, now=NOW)
    assert res[0]["action"] == "exit_dry_run"
    assert res[0]["kind"] == "stop_loss"
    # 16 contracts, 63c -> 30c
    assert res[0]["realized_usd"] == pytest.approx(16 * (30 - 63) / 100.0)
    book = Portfolio.load()
    assert book.positions == []
    assert book.realized_pnl_today_usd == pytest.approx(-5.28)


def test_the_exit_order_it_would_send_is_a_sell_of_the_yes_leg(ledger, no_network):
    nodes.execute_node({"risk": APPROVED, "market": MARKET, "judgment": JUDGMENT})
    res = nodes.manage_positions({"KXFL-TEST": {"yes_bid_cents": 30.0,
                                                "yes_ask_cents": 33.0}}, now=NOW)
    would = res[0]["would_send"]
    assert would["side"] == "ask", "exiting a long YES means selling YES"
    assert would["price"] == "0.3000"
    assert would["count"] == "16.00"


def test_a_realized_loss_then_feeds_the_daily_loss_cap(ledger, no_network):
    """Closing the loop: an exit's P&L is what later trips the daily cap."""
    nodes.execute_node({"risk": APPROVED, "market": MARKET, "judgment": JUDGMENT})
    nodes.manage_positions({"KXFL-TEST": {"yes_bid_cents": 30.0,
                                          "yes_ask_cents": 33.0}}, now=NOW)
    assert Portfolio.load().risk_state().realized_pnl_today_usd < 0


def test_position_with_no_quote_this_cycle_is_left_alone(ledger, no_network):
    nodes.execute_node({"risk": APPROVED, "market": MARKET, "judgment": JUDGMENT})
    res = nodes.manage_positions({}, now=NOW)
    assert res[0]["action"] == "hold"
    assert "no quote" in res[0]["reason"]
    assert Portfolio.load().positions != []


def test_backoff_is_jittered_so_concurrent_workers_do_not_resynchronise():
    """Without jitter every worker throttled in the same instant backs off for

    the SAME interval and they all return together, recreating the burst that
    caused the 429. A parallel 6-worker sweep still lost 7 requests after all
    retries; those same 7 re-run serially succeeded immediately.
    """
    from kalshi_client import KalshiClient
    c = KalshiClient(base_url="https://example.invalid")
    for attempt in range(4):
        ceiling = KalshiClient.BACKOFF_BASE_SECONDS * (2 ** attempt)
        floor = ceiling * (1.0 - KalshiClient.BACKOFF_JITTER)
        delays = {c._backoff_seconds(attempt) for _ in range(40)}
        assert len(delays) > 1, "backoff must not be constant"
        for d in delays:
            assert floor <= d <= ceiling, f"{d} outside [{floor}, {ceiling}]"


def test_backoff_still_grows_and_stays_positive():
    from kalshi_client import KalshiClient
    c = KalshiClient(base_url="https://example.invalid")
    assert min(c._backoff_seconds(3) for _ in range(40)) > 0.0
    # later attempts wait strictly longer even at their most jittered
    assert (KalshiClient.BACKOFF_BASE_SECONDS * 2 ** 3
            * (1 - KalshiClient.BACKOFF_JITTER)
            > KalshiClient.BACKOFF_BASE_SECONDS * 2 ** 0)
