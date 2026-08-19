"""The four portfolio caps that could never bind before the ledger existed.

Each test builds a real Portfolio, projects it through risk_state(), and
asserts evaluate() rejects for the specific reason. Prior to agent/portfolio.py
these paths were dead code: load() always returned a blank PortfolioState
because save() was never called.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.config import RiskLimits
from agent.portfolio import Portfolio, Position
from agent.risk import evaluate

LIMITS = RiskLimits(total_capital_usd=100.0, max_position_usd=10.0,
                    max_daily_loss_usd=25.0, max_open_positions=5)

TICKER = "KXFLPRIMARY-22R26-CASK"
MARKET = {"ticker": TICKER, "yes_bid_cents": 60.0, "yes_ask_cents": 63.0,
          "book_depth_contracts": 1000.0}
JUDGMENT = {"should_trade": True, "side": "yes", "fair_value_cents": 75.0,
            "confidence": 0.90}


def _pos(ticker, cost=10.0):
    return Position(ticker=ticker, side="yes", size_contracts=16,
                    entry_price_cents=63.0, cost_usd=cost)


def _book(*positions, pnl=0.0):
    return Portfolio(positions=list(positions), realized_pnl_today_usd=pnl)


# ---------------------------------------------------------------- baseline
def test_empty_portfolio_approves_at_conf_090_edge_12c():
    """Control: without a cap binding, this exact setup is approved."""
    d = evaluate(JUDGMENT, MARKET, Portfolio().risk_state(), LIMITS)
    assert d["approved"] is True, d["reason"]
    assert d["size_contracts"] > 0
    assert d["limit_price_cents"] == 63.0


# ---------------------------------------------------------------- cap 1
def test_duplicate_position_cap_binds():
    book = _book(_pos(TICKER))
    assert book.risk_state().open_tickers == (TICKER,)
    d = evaluate(JUDGMENT, MARKET, book.risk_state(), LIMITS)
    assert d["approved"] is False
    assert "already hold" in d["reason"]


# ---------------------------------------------------------------- cap 2
def test_max_open_positions_cap_binds():
    book = _book(*[_pos(f"OTHER-{i}", cost=1.0) for i in range(5)])
    assert book.risk_state().open_positions == 5
    d = evaluate(JUDGMENT, MARKET, book.risk_state(), LIMITS)
    assert d["approved"] is False
    assert "max open positions" in d["reason"]


# ---------------------------------------------------------------- cap 3
def test_daily_loss_cap_binds():
    book = _book(pnl=-25.0)
    d = evaluate(JUDGMENT, MARKET, book.risk_state(), LIMITS)
    assert d["approved"] is False
    assert "daily loss cap hit" in d["reason"]


def test_daily_loss_cap_does_not_bind_one_cent_early():
    d = evaluate(JUDGMENT, MARKET, _book(pnl=-24.99).risk_state(), LIMITS)
    assert d["approved"] is True, d["reason"]


# ---------------------------------------------------------------- cap 4
def test_total_capital_cap_binds():
    book = _book(_pos("OTHER-A", cost=50.0), _pos("OTHER-B", cost=50.0))
    assert book.risk_state().deployed_usd == 100.0
    d = evaluate(JUDGMENT, MARKET, book.risk_state(), LIMITS)
    assert d["approved"] is False
    assert "no remaining capital" in d["reason"]


def test_partial_capital_shrinks_size_rather_than_rejecting():
    book = _book(_pos("OTHER-A", cost=98.0))
    d = evaluate(JUDGMENT, MARKET, book.risk_state(), LIMITS)
    assert d["approved"] is True, d["reason"]
    assert d["size_usd"] <= 2.0    # only $2 of the $100 ceiling is left


# ---------------------------------------------------------------- projection
def test_risk_state_projection_is_faithful():
    book = _book(_pos("A", cost=3.0), _pos("B", cost=4.5), pnl=-7.25)
    rs = book.risk_state()
    assert rs.open_positions == 2
    assert set(rs.open_tickers) == {"A", "B"}
    assert rs.deployed_usd == 7.5
    assert rs.realized_pnl_today_usd == -7.25
