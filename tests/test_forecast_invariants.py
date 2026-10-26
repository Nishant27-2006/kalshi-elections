"""Leakage invariants for the forecasting backtest and retrieval."""
import numpy as np
import pandas as pd

from forecast.backtest import Config, split, taker_fee, trades
from forecast.retrieval import Chunk, Retriever, _date


def _snap(n_events=20, legs=2, weeks=4):
    rows = []
    for e in range(n_events):
        close = 1_000_000 + e * 10 * 86400
        for leg in range(legs):
            for w in range(weeks):
                T = close - (weeks - w) * 7 * 86400
                rows.append({"ticker": f"E{e}-{leg}", "event": f"E{e}", "event_close": close, "T": T,
                             "mid": 0.5, "bid": 0.48, "ask": 0.52, "spread": 0.04, "stale_days": 0,
                             "outcome": leg % 2, "fwd_lo": 0.4, "fwd_hi": 0.6})
    return pd.DataFrame(rows)


def test_split_has_no_event_overlap_and_test_is_after_cutoff():
    s = _snap()
    train, test, cutoff = split(s)
    assert set(train["event"]).isdisjoint(set(test["event"]))
    assert (test["T"] >= cutoff).all()
    assert (train["event_close"] <= cutoff).all()


def test_split_holds_out_most_recent_30pct_of_events():
    s = _snap(n_events=20)
    train, test, _ = split(s)
    test_events = s[s["event"].isin(test["event"])]["event"].unique()
    assert len(test_events) <= 6
    assert s[s["event"].isin(test_events)]["event_close"].min() > train["event_close"].max()


def test_taker_fee_formula():
    assert abs(taker_fee(0.5) - 0.0175) < 1e-12
    assert abs(taker_fee(0.9) - 0.0063) < 1e-12


def test_trades_enter_once_per_market_and_pay_fee():
    s = _snap(n_events=2, legs=1, weeks=3)
    p = np.full(len(s), 0.9)
    tr = trades(s, p, Config(name="t", min_edge=0.0))
    assert tr["ticker"].is_unique
    cost = 0.52 + taker_fee(0.52)
    assert np.allclose(tr["cost"], cost)
    assert np.allclose(tr["pnl"], tr["outcome"] - cost)


def test_retrieval_never_returns_future_chunks():
    chunks = [Chunk("a.md", "texas senate poll paxton talarico", _date("2026-09-01"), "claim"),
              Chunk("b.md", "texas senate poll paxton talarico", _date("2026-10-01"), "claim")]
    r = Retriever(chunks, expand=False, ticker_match=False)
    hits = r.search("Texas Senate winner", as_of=_date("2026-09-15"))
    assert [c.file for _, c in hits] == ["a.md"]
