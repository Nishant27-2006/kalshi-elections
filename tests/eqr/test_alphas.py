"""The author's alphas must satisfy the Signal contract."""
from eqr.signals import base


def _rows():
    return [
        {"ticker": "A", "yes_bid_c": 39.0, "yes_ask_c": 41.0, "spread_c": 2.0,
         "v24": 5000.0, "oi": 100.0, "ts": 100},
        {"ticker": "B", "yes_bid_c": 59.0, "yes_ask_c": 61.0, "spread_c": 2.0,
         "v24": 4000.0, "oi": 90.0, "ts": 100},
        {"ticker": "C", "yes_bid_c": 4.0, "yes_ask_c": 8.0, "spread_c": 4.0,
         "v24": 100.0, "oi": 10.0, "ts": 100},
    ]


def test_alpha_01_satisfies_the_signal_protocol():
    from eqr.signals import alpha_01_reversal as a
    s = a.Alpha()
    assert isinstance(s, base.Signal)
    assert isinstance(s.name, str) and s.name


def test_alpha_01_returns_one_value_per_row():
    from eqr.signals import alpha_01_reversal as a
    assert len(a.Alpha().compute(_rows())) == 3


def test_alpha_02_satisfies_the_signal_protocol():
    from eqr.signals import alpha_02_spread as a
    assert isinstance(a.Alpha(), base.Signal)


def test_alpha_02_returns_one_value_per_row():
    from eqr.signals import alpha_02_spread as a
    assert len(a.Alpha().compute(_rows())) == 3


def test_alphas_are_pure_and_do_not_mutate_input():
    from eqr.signals import alpha_01_reversal as a1
    from eqr.signals import alpha_02_spread as a2
    rows = _rows()
    snapshot = [dict(r) for r in rows]
    a1.Alpha().compute(rows)
    a2.Alpha().compute(rows)
    assert rows == snapshot
