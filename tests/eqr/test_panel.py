"""Day 5. The panel is the ONLY place lookahead can enter. Guard it."""
import pytest

from eqr import panel, universe


def _rows():
    """Two tickers, three timestamps, hand-computable returns."""
    out = []
    for ts, (a, b) in [(100, (40.0, 60.0)), (200, (44.0, 57.0)), (300, (50.0, 50.0))]:
        out.append({"ts": ts, "ticker": "A", "event_ticker": "EA", "series": "S",
                    "yes_bid_c": a - 1, "yes_ask_c": a + 1, "spread_c": 2.0,
                    "oi": 100.0, "v24": 5000.0})
        out.append({"ts": ts, "ticker": "B", "event_ticker": "EB", "series": "S",
                    "yes_bid_c": b - 1, "yes_ask_c": b + 1, "spread_c": 2.0,
                    "oi": 100.0, "v24": 5000.0})
    return out


def test_exclude_combos_drops_cross_category_shards():
    rows = [{"ticker": "KXMVECROSSCATEGORY-SHARD1-XYZ"}, {"ticker": "KXBTCD-1-T2"}]
    assert [r["ticker"] for r in universe.exclude_combos(rows)] == ["KXBTCD-1-T2"]


def test_liquidity_screen_uses_only_rows_at_or_before_asof():
    rows = _rows()
    rows.append({"ts": 999, "ticker": "C", "event_ticker": "EC", "series": "S",
                 "yes_bid_c": 10.0, "yes_ask_c": 12.0, "spread_c": 2.0,
                 "oi": 1.0, "v24": 1e9})
    kept = universe.liquidity_screen(rows, asof_ts=300, min_v24=1000.0,
                                     max_spread_c=5.0)
    assert "C" not in {r["ticker"] for r in kept}


def test_liquidity_screen_rejects_wide_spreads():
    rows = _rows()
    rows[0]["spread_c"] = 40.0
    kept = universe.liquidity_screen(rows, asof_ts=100, min_v24=1000.0,
                                     max_spread_c=5.0)
    assert "A" not in {r["ticker"] for r in kept}


def test_forward_return_uses_a_strictly_later_snapshot():
    by = {r["ticker"]: r for r in panel.build(_rows(), asof_ts=100, horizon_s=100)}
    # A mid goes 40 -> 44 over the horizon; return in probability points.
    assert by["A"]["fwd_ret"] == pytest.approx(0.04, abs=1e-9)
    assert by["B"]["fwd_ret"] == pytest.approx(-0.03, abs=1e-9)


def test_forward_return_is_none_when_no_later_snapshot_exists():
    built = panel.build(_rows(), asof_ts=300, horizon_s=100)
    assert all(r["fwd_ret"] is None for r in built)


def test_panel_row_carries_no_future_fields():
    """Every value except fwd_ret must come from the asof snapshot."""
    by = {r["ticker"]: r for r in panel.build(_rows(), asof_ts=100, horizon_s=100)}
    assert by["A"]["yes_bid_c"] == 39.0      # the t=100 quote, not t=200
    assert by["A"]["ts"] == 100


def test_planted_lookahead_signal_scores_near_zero():
    """THE CANARY. No present field may equal the forward return."""
    built = panel.build(_rows(), asof_ts=100, horizon_s=100)
    rets = [r["fwd_ret"] for r in built]
    fields = {k for r in built for k, v in r.items()
              if k != "fwd_ret" and isinstance(v, (int, float))}
    for f in fields:
        assert [r[f] for r in built] != rets, f"field {f} leaks the forward return"


def test_resolution_contamination_is_flagged():
    rows = _rows()
    rows.append({"ts": 400, "ticker": "B", "event_ticker": "EB", "series": "S",
                 "yes_bid_c": 0.0, "yes_ask_c": 0.0, "spread_c": 0.0,
                 "oi": 0.0, "v24": 5000.0})
    by = {r["ticker"]: r for r in panel.build(rows, asof_ts=300, horizon_s=100)}
    assert by["B"]["resolves_in_window"] is True


def test_cross_section_returns_aligned_rows_and_returns():
    rows_, rets = panel.cross_section(_rows(), asof_ts=100, horizon_s=100)
    assert len(rows_) == len(rets) == 2
    assert all(r is not None for r in rets)
