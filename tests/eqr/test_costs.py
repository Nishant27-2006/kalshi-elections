"""Day 7. The arithmetic that kills strategies."""
import pytest

from agent import risk_unit
from eqr import costs


def test_round_trip_cost_includes_spread_and_both_fee_legs():
    price, spread_c = 0.5, 2.0
    expected = (spread_c / 100.0) + risk_unit.FEE_LEGS * risk_unit.fee_per_contract(price)
    assert costs.round_trip_cost(price, spread_c) == pytest.approx(expected, abs=1e-12)


def test_fee_is_maximised_at_fifty_cents():
    """Drill Q1 made executable."""
    at_50 = costs.round_trip_cost(0.50, 0.0)
    assert at_50 > costs.round_trip_cost(0.20, 0.0)
    assert at_50 > costs.round_trip_cost(0.80, 0.0)
    assert at_50 == pytest.approx(2 * 0.07 * 0.25, abs=1e-12)


def test_cheap_longshots_cost_less_than_coinflips():
    assert costs.round_trip_cost(0.03, 2.0) < costs.round_trip_cost(0.50, 2.0)


def test_net_edge_subtracts_the_round_trip():
    assert costs.net_edge(0.10, 0.5, 2.0) == pytest.approx(
        0.10 - costs.round_trip_cost(0.5, 2.0), abs=1e-12)


def test_breakeven_edge_is_exactly_the_round_trip_cost():
    for p in (0.05, 0.25, 0.5, 0.9):
        assert costs.breakeven_edge(p, 2.0) == pytest.approx(
            costs.round_trip_cost(p, 2.0), abs=1e-12)


def test_a_two_point_edge_does_not_survive_a_coinflip_round_trip():
    """The headline result: 2 probability points is NOT enough at 50c."""
    assert costs.net_edge(0.02, 0.50, 2.0) < 0


def test_capacity_curve_turns_negative_at_high_turnover():
    # cost at 50c over a 2c spread = 0.02 + 2*0.07*0.25 = 0.055, so a
    # 0.03 gross edge is NET NEGATIVE and more turnover only loses faster.
    curve = costs.capacity_curve(gross_edge=0.03, price=0.5, spread_c=2.0,
                                 turnovers=[1.0, 10.0, 100.0, 1000.0])
    assert len(curve) == 4
    annuals = [a for _, a in curve]
    assert all(a < 0 for a in annuals)
    assert annuals == sorted(annuals, reverse=True)
    assert annuals[0] == pytest.approx(-0.025, abs=1e-12)


def test_capacity_curve_is_positive_when_edge_beats_cost():
    curve = costs.capacity_curve(gross_edge=0.20, price=0.5, spread_c=2.0,
                                 turnovers=[1.0, 10.0])
    assert all(a > 0 for _, a in curve)
