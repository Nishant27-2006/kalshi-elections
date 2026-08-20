"""Tests for the backtester.

The point of most of these is not that the arithmetic is right -- it is that
the backtest cannot flatter itself. A backtest that marks at the mid, pools
correlated trades, or peeks one bar ahead will report a Sharpe that no order
could ever have earned.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from backtest import (Result, Trade, load_series_paths, momentum_signal,
                      run_strategy, split_by_time, tune_momentum, _norm_ppf)


def _row(ticker, ts, bid, ask, series="KXMLBGAME"):
    return {"ts": ts, "ticker": ticker, "series": series,
            "yes_bid_c": float(bid), "yes_ask_c": float(ask),
            "spread_c": float(ask) - float(bid), "oi": 1.0, "v24": 1.0}


def _path(ticker, prices, series="KXMLBGAME", spread=2):
    """prices are MIDs; bid/ask straddle them by spread/2."""
    return [_row(ticker, ts, p - spread / 2, p + spread / 2, series)
            for ts, p in enumerate(prices, start=1)]


# --------------------------------------------------------------- trade maths

def test_a_flat_market_still_loses_the_spread_and_both_fees():
    """THE CENTRAL FACT. Buying the ask and selling the bid on a market that
    never moved is a guaranteed loss, and it is the reason the null strategy
    is the bar every signal has to clear. A backtest that marks at the mid
    would report exactly zero here and be wrong by the whole spread."""
    t = Trade(ts=1, ticker="T", series="KXMLBGAME", entry_ask_c=51.0,
              exit_bid_c=49.0, spread_c=2.0, ru=0.5)
    assert t.gross_return < 0
    assert t.gross_return == pytest.approx((49.0 - 51.0) / 51.0)
    assert t.fee_drag > 0
    assert t.net_return < t.gross_return, "fees must make it strictly worse"


def test_fees_are_charged_on_both_legs_at_their_own_prices():
    """Entry and exit are at different prices, so they owe different fees --
    Kalshi's schedule is a parabola in price, not a flat charge."""
    from agent.risk_unit import fee_per_contract
    t = Trade(ts=1, ticker="T", series="KXMLBGAME", entry_ask_c=50.0,
              exit_bid_c=90.0, spread_c=2.0, ru=0.5)
    expected = (fee_per_contract(0.50) + fee_per_contract(0.90)) / 0.50
    assert t.fee_drag == pytest.approx(expected)
    assert fee_per_contract(0.50) != fee_per_contract(0.90)


def test_return_per_ru_is_not_return_on_capital():
    """A trade making 2% on capital while burning 3 RU is worse than one
    making 1% on 1 RU. Sizing is done in RU, so this is the number that
    decides which strategy gets the money."""
    cheap_risk = Trade(ts=1, ticker="A", series="S", entry_ask_c=50.0,
                       exit_bid_c=55.0, spread_c=2.0, ru=0.10)
    dear_risk = Trade(ts=1, ticker="B", series="S", entry_ask_c=50.0,
                      exit_bid_c=55.0, spread_c=2.0, ru=1.00)
    assert cheap_risk.net_return == pytest.approx(dear_risk.net_return)
    assert cheap_risk.return_per_ru > dear_risk.return_per_ru * 9


# ------------------------------------------------------- no-lookahead signal

def test_the_momentum_signal_cannot_see_the_bar_it_trades_on_or_later():
    """Peeking one bar ahead is how a backtest invents alpha it can never
    trade. The signal at i may read i and earlier, never i+1."""
    p = _path("T", [50, 50, 50, 90])
    # at i=2 the future spike to 90 is invisible, so no signal fires
    assert momentum_signal(p, 2, lookback=2, threshold_c=5.0) is False
    # only once the move is in the PAST does it fire
    assert momentum_signal(p, 3, lookback=1, threshold_c=5.0) is True


def test_a_signal_cannot_fire_before_it_has_enough_history():
    p = _path("T", [50, 60, 70])
    assert momentum_signal(p, 0, lookback=3, threshold_c=1.0) is False
    assert momentum_signal(p, 1, lookback=3, threshold_c=1.0) is False


# --------------------------------------------------- correlation / bucketing

def test_simultaneous_trades_are_averaged_into_one_portfolio_bucket():
    """Fifty tickers entered in the same second are ONE bet on a market-wide
    move, not fifty independent ones. Pooling them as independent inflates
    the Sharpe by roughly sqrt(names) -- the single most common way a
    backtest overstates itself."""
    by_ticker = {f"T{i}": _path(f"T{i}", [50, 52, 54]) for i in range(20)}
    res = run_strategy(by_ticker, horizon=1)
    assert res.n == 40, "20 tickers x 2 entry bars"
    assert len(res.buckets) == 2, "but only 2 distinct entry timestamps"


def test_sharpe_is_none_rather_than_infinite_when_every_bucket_is_identical():
    """Zero variance is an UNMEASURABLE Sharpe, not a perfect one. Returning
    a huge number here would make a degenerate run look like the best
    strategy in the grid."""
    r = Result(name="x", buckets=[0.01, 0.01, 0.01])
    assert r.sharpe_per_bucket is None


def test_sharpe_needs_at_least_two_buckets():
    assert Result(name="x", buckets=[0.01]).sharpe_per_bucket is None
    assert Result(name="x", buckets=[]).sharpe_per_bucket is None


def test_sharpe_is_mean_over_standard_deviation_of_the_buckets():
    import statistics
    b = [0.01, -0.02, 0.03, 0.00, -0.01]
    r = Result(name="x", buckets=b)
    assert r.sharpe_per_bucket == pytest.approx(
        statistics.fmean(b) / statistics.stdev(b))


# ------------------------------------------------------------ multiple tests

def test_the_deflated_sharpe_charges_for_every_configuration_tried():
    """The best of 40 random strategies has a positive Sharpe by
    construction. If the grid search is not charged for its own width, every
    tuning run 'discovers' a signal."""
    b = [0.02, -0.01, 0.03, 0.00, 0.01, 0.02, -0.02, 0.01]
    one = Result(name="x", buckets=b, n_configs_tried=1)
    many = Result(name="x", buckets=b, n_configs_tried=40)
    assert one.deflated_sharpe == pytest.approx(one.sharpe_per_bucket)
    assert many.deflated_sharpe < one.deflated_sharpe
    assert many.deflated_sharpe == pytest.approx(one.sharpe_per_bucket
                                                 - _expected_max(40))


def _expected_max(n):
    euler = 0.5772156649
    return ((1 - euler) * _norm_ppf(1 - 1.0 / n)
            + euler * _norm_ppf(1 - 1.0 / (n * math.e)))


def test_the_deflation_penalty_grows_with_the_grid():
    b = [0.02, -0.01, 0.03, 0.00, 0.01]
    small = Result(name="x", buckets=b, n_configs_tried=5)
    big = Result(name="x", buckets=b, n_configs_tried=500)
    assert big.deflated_sharpe < small.deflated_sharpe


def test_the_inverse_normal_matches_known_quantiles():
    assert _norm_ppf(0.5) == pytest.approx(0.0, abs=1e-9)
    assert _norm_ppf(0.975) == pytest.approx(1.959964, abs=1e-4)
    assert _norm_ppf(0.025) == pytest.approx(-1.959964, abs=1e-4)
    assert _norm_ppf(0.99) == pytest.approx(2.326348, abs=1e-4)


# ------------------------------------------------------------- train / test

def test_the_split_is_by_clock_not_by_ticker():
    """Splitting by ticker puts a ticker's early bars in train and its late
    bars in test, leaking its own regime across the boundary."""
    by_ticker = {"A": _path("A", [50, 51, 52, 53, 54]),
                 "B": _path("B", [30, 31, 32, 33, 34])}
    first, cut, last = split_by_time(by_ticker, train_fraction=0.6)
    assert first == 1 and last == 5
    assert first < cut < last
    # both tickers straddle the cut -- neither is confined to one side
    for t in ("A", "B"):
        ts = [r["ts"] for r in by_ticker[t]]
        assert any(x < cut for x in ts) and any(x >= cut for x in ts)


def test_a_time_window_actually_excludes_trades_outside_it():
    by_ticker = {"A": _path("A", [50] * 10)}
    everything = run_strategy(by_ticker, horizon=1)
    tail = run_strategy(by_ticker, horizon=1, ts_min=6)
    assert tail.n < everything.n
    assert all(t.ts >= 6 for t in tail.trades)


def test_tuning_never_selects_a_configuration_below_the_trade_floor():
    """A 3-trade Sharpe of 4.0 is not a finding. If the floor were ignored the
    grid would always crown its own smallest, noisiest cell."""
    by_ticker = {f"T{i}": _path(f"T{i}", [50, 51, 52, 53, 54, 55])
                 for i in range(3)}
    best, grid = tune_momentum(by_ticker, horizon=1, ts_min=1, ts_max=99,
                               lookbacks=(1,), thresholds=(1.0,),
                               min_trades=10_000)
    assert best == {}, "no cell can clear an impossible floor"
    assert grid, "but every cell is still reported"


# ------------------------------------------------------------- book hygiene

def test_an_untradeably_wide_book_is_skipped():
    """The exit assumption is 'lift the bid'. On a 60c-wide book nobody is
    quoting seriously and that assumption stops being credible."""
    wide = [_row("W", ts, 10, 80) for ts in range(1, 5)]
    res = run_strategy({"W": wide}, horizon=1)
    assert res.n == 0


def test_a_missing_quote_is_skipped_on_either_leg_not_scored_as_flat():
    """An unquoted book is MISSING DATA on both sides. Scoring a dark exit as
    a flat return would quietly improve the strategy every time liquidity
    vanished -- and liquidity vanishes precisely when it costs you."""
    path = _path("T", [50, 50, 50, 50])   # 4 bars -> entries at i=0,1,2
    path[1]["yes_bid_c"] = None
    res = run_strategy({"T": path}, horizon=1)
    assert res.n == 1, "i=0 loses its exit quote, i=1 loses its entry quote"
    assert res.trades[0].ts == 3
    assert res.skipped.get("no_bid") == 2


def test_a_zero_bid_book_is_never_scored_as_a_total_loss():
    """13% of recorded rows have NO BID. Marking those exits at 0 reports
    -100% per trade and drowns every other effect in the backtest -- it is
    the single largest distortion this data contains."""
    path = [_row("T", ts, 0, 5) for ts in range(1, 5)]
    res = run_strategy({"T": path}, horizon=1)
    assert res.n == 0
    assert res.skipped.get("no_bid", 0) > 0


def test_a_cheap_contract_the_sizer_would_refuse_is_not_traded():
    """MIN_PRICE_DOLLARS exists because a percentage stop below one tick is
    meaningless. A backtest that trades what the sizer refuses is measuring a
    strategy nobody can run."""
    path = [_row("T", ts, 1, 2) for ts in range(1, 5)]
    res = run_strategy({"T": path}, horizon=1)
    assert res.n == 0
    assert res.skipped.get("below_min_price", 0) > 0


def test_a_spread_that_is_small_in_cents_can_still_be_huge_in_percent():
    """An 11c contract quoted 7/11 is a 4c spread -- trivial in cents, a 36%
    round-trip haircut before the market moves. Absolute-cent limits miss
    this entirely, which is why the filter is fractional."""
    path = [_row("T", ts, 7, 11) for ts in range(1, 5)]
    res = run_strategy({"T": path}, horizon=1)
    assert res.n == 0, "4c on an 11c book is 36%, far past the 10% limit"
    assert res.skipped.get("spread_fraction", 0) > 0
    # the same 4c spread on a 90c book is fine
    ok = run_strategy({"T": [_row("T", ts, 88, 92) for ts in range(1, 5)]},
                      horizon=1)
    assert ok.n > 0


def test_the_mid_return_separates_direction_from_cost():
    """If mid_return is ~0 the signal has no direction; if it is positive
    while net_return is negative the signal is real but too small to pay for
    itself. Those need different fixes and the net number cannot tell them
    apart."""
    flat = Trade(ts=1, ticker="T", series="S", entry_ask_c=51.0,
                 exit_bid_c=49.0, spread_c=2.0, ru=0.5)
    assert flat.mid_return == pytest.approx(0.0), "market never moved"
    assert flat.net_return < 0, "but the round trip still cost money"

    up = Trade(ts=1, ticker="T", series="S", entry_ask_c=51.0,
               exit_bid_c=53.0, spread_c=2.0, ru=0.5)
    assert up.mid_return > 0


def test_load_groups_by_ticker_and_sorts_each_path_by_time(tmp_path):
    import json
    p = tmp_path / "rec.jsonl"
    rows = [_row("A", 3, 49, 51), _row("A", 1, 39, 41), _row("B", 2, 9, 11)]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    out = load_series_paths(p)
    assert set(out) == {"A", "B"}
    assert [r["ts"] for r in out["A"]] == [1, 3]


def test_the_null_strategy_on_a_rising_market_still_pays_the_spread():
    """Even when every tick goes your way, the round trip is not free. This
    is the whole reason the fund needs an edge, not just a direction."""
    by_ticker = {"T": _path("T", [50, 51, 52, 53])}
    res = run_strategy(by_ticker, horizon=1)
    assert res.n > 0
    # a 1c mid rise against a 2c spread is still a loss
    assert res.mean_return < 0


# --------------------------------------------------------------- cost table

def test_the_fee_dominates_the_spread_at_mid_prices():
    """The finding that changes where the fund should trade. On a 1c book at
    50c the spread costs about 2% and the fee about 7% -- so a strategy tuned
    to avoid wide spreads while ignoring the fee is optimising the smaller
    of the two costs."""
    from backtest import cost_table
    rows = {int(px): (sc, fd, tot) for px, sc, fd, tot in cost_table(1.0)}
    spread_50, fee_50, _ = rows[50]
    assert fee_50 > spread_50 * 3, "the fee is the dominant cost at 50c"


def test_round_trip_cost_is_lowest_on_heavy_favourites():
    """Because the fee is 0.07*P*(1-P) it nearly vanishes at the extremes,
    while the spread as a FRACTION of price also falls as price rises. Cost
    is therefore minimised on favourites -- the opposite of where a
    spread-only intuition sends you."""
    from backtest import cost_table
    rows = {int(px): tot for px, _, _, tot in cost_table(1.0)}
    assert rows[90] < rows[50] < rows[25] < rows[10]
    assert rows[5] > 0.25, "a 5c contract costs over 25% to round-trip"
    assert rows[90] < 0.03, "a 90c contract costs under 3%"


def test_the_cost_table_widens_with_the_spread():
    from backtest import cost_table
    tight = {int(px): tot for px, _, _, tot in cost_table(1.0)}
    wide = {int(px): tot for px, _, _, tot in cost_table(4.0)}
    for px in tight:
        assert wide[px] > tight[px]


# ------------------------------------------------------- PnL concentration

def test_a_result_driven_by_one_event_is_flagged_as_concentrated():
    """THE CHECK THAT KILLED THIS PROJECT'S FIRST APPARENT EDGE. A momentum
    configuration scored +15.9% per trade out of sample. Its top 5% -- twenty
    trades, every one on the SAME baseball game -- contributed 100% of the
    PnL, and the mean without them was -0.07%. Sharpe alone never says this.
    """
    flat = [Trade(1, "GAME-A", "S", 50.0, 49.0, 2.0, 0.5) for _ in range(38)]
    spike = [Trade(1, "GAME-A", "S", 17.0, 99.0, 2.0, 0.5) for _ in range(2)]
    r = Result(name="x", trades=flat + spike)
    assert r.top_5pct_pnl_share is not None
    assert r.top_5pct_pnl_share > 0.8, "the spike must dominate the PnL"
    assert r.mean_return_ex_top_5pct < 0, "strip it and the edge is gone"
    assert r.mean_return > 0, "...even though the headline mean is positive"


def test_a_broadly_earned_result_is_not_flagged():
    """The check must not condemn a strategy that wins evenly -- otherwise it
    rejects the very thing the fund is looking for."""
    # note the exit must clear the ~7% round-trip cost at 50c, or this is a
    # LOSING strategy and the metric correctly refuses to attribute it
    trades = [Trade(1, f"G{i}", "S", 50.0, 60.0, 2.0, 0.5) for i in range(40)]
    r = Result(name="x", trades=trades)
    assert r.mean_return > 0, "fixture must actually be profitable"
    assert r.top_5pct_pnl_share == pytest.approx(0.05, abs=0.02)


def test_distinct_events_counts_games_not_legs():
    """Fifty legs of one baseball game are ONE observation. Counting them as
    fifty is how a sample size gets inflated by an order of magnitude."""
    trades = ([Trade(1, "KXMLBTOTAL-26AUG19ATHKC-14", "S", 50, 51, 2, .5)] * 20
              + [Trade(1, "KXMLBTOTAL-26AUG19ATHKC-15", "S", 50, 51, 2, .5)] * 20
              + [Trade(1, "KXMLBGAME-26AUG19NYYBOS-NYY", "S", 50, 51, 2, .5)])
    r = Result(name="x", trades=trades)
    assert r.distinct_events == 2, "two games, not 41 trades"


def test_concentration_is_none_when_there_is_nothing_to_measure():
    assert Result(name="x", trades=[]).top_5pct_pnl_share is None
    assert Result(name="x", trades=[]).mean_return_ex_top_5pct is None


def test_concentration_is_not_reported_for_a_losing_strategy():
    """Dividing a top-5% sum by a NEGATIVE total gives values like -105%,
    which reads as a percentage and is not one. The metric answers 'is the
    PROFIT the work of a few trades'; a strategy with no profit has nothing
    to attribute."""
    losers = [Trade(1, f"G{i}", "S", 51.0, 49.0, 2.0, 0.5) for i in range(40)]
    r = Result(name="x", trades=losers)
    assert r.mean_return < 0
    assert r.top_5pct_pnl_share is None
