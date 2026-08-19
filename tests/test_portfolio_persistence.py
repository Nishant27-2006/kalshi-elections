"""save()/load() round trip. The bug this closes: save() existed but was
called zero times, so every cycle started from a blank portfolio."""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.portfolio import Portfolio, Position


@pytest.fixture
def ledger(tmp_path):
    return tmp_path / "positions.json"


def _pos(ticker="KXTEST", **kw):
    d = dict(ticker=ticker, side="yes", size_contracts=10,
             entry_price_cents=63.0, cost_usd=6.30)
    d.update(kw)
    return Position(**d)


def test_open_position_writes_the_file(ledger):
    assert not ledger.exists()
    Portfolio().open_position(_pos(), path=ledger)
    assert ledger.exists(), "open_position must persist"
    raw = json.loads(ledger.read_text())
    assert raw["positions"][0]["ticker"] == "KXTEST"


def test_reload_sees_the_position(ledger):
    Portfolio().open_position(_pos(), path=ledger)
    back = Portfolio.load(ledger)
    assert back.risk_state().open_tickers == ("KXTEST",)
    assert back.deployed_usd == 6.30


def test_duplicate_open_is_refused(ledger):
    book = Portfolio()
    book.open_position(_pos(), path=ledger)
    with pytest.raises(ValueError, match="already hold"):
        book.open_position(_pos(), path=ledger)


def test_close_books_realized_pnl_and_persists(ledger):
    book = Portfolio()
    book.open_position(_pos(), path=ledger)
    trade = book.close_position("KXTEST", 70.0, "take_profit", path=ledger)
    # 10 contracts, 63c -> 70c = $0.70
    assert trade.realized_usd == pytest.approx(0.70)
    back = Portfolio.load(ledger)
    assert back.positions == []
    assert back.realized_pnl_today_usd == pytest.approx(0.70)


def test_close_a_losing_no_position(ledger):
    book = Portfolio()
    book.open_position(_pos("KXNO", side="no", entry_price_cents=22.0,
                            size_contracts=100, cost_usd=22.0), path=ledger)
    trade = book.close_position("KXNO", 11.0, "stop_loss", path=ledger)
    assert trade.realized_usd == pytest.approx(-11.0)
    assert Portfolio.load(ledger).realized_pnl_today_usd == pytest.approx(-11.0)


def test_closing_an_unheld_ticker_raises(ledger):
    with pytest.raises(ValueError, match="no open position"):
        Portfolio().close_position("NOPE", 50.0, "x", path=ledger)


def test_new_day_resets_daily_pnl_but_keeps_positions(ledger):
    book = Portfolio()
    book.open_position(_pos(), path=ledger)
    book.close_position("KXTEST", 40.0, "stop_loss", path=ledger)
    book.open_position(_pos("KXCARRY"), path=ledger)

    # rewrite the stored date as yesterday
    raw = json.loads(ledger.read_text())
    raw["date"] = (date.today() - timedelta(days=1)).isoformat()
    ledger.write_text(json.dumps(raw))

    fresh = Portfolio.load(ledger)
    assert fresh.realized_pnl_today_usd == 0.0, "daily loss counter must reset"
    assert fresh.closed_today == []
    assert fresh.risk_state().open_tickers == ("KXCARRY",), "positions carry over"


def test_corrupt_ledger_fails_loud_instead_of_looking_empty(ledger):
    ledger.write_text("{not json")
    with pytest.raises(ValueError, match="corrupt"):
        Portfolio.load(ledger)


def test_missing_ledger_is_an_empty_portfolio(ledger):
    p = Portfolio.load(ledger)
    assert p.positions == [] and p.realized_pnl_today_usd == 0.0
