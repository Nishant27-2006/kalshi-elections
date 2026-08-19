import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent.risk_unit import (FEE_PER_CONTRACT_USD, MIN_PRICE_DOLLARS,
                             SIGMA_MULTIPLE, Sizing, ru_per_contract,
                             size_position, UNSIZEABLE_STRUCTURES, cluster_key,
                             portfolio_ru)


def test_ru_is_the_sum_of_its_three_terms():
    """Spec section 5: RU = volatility-scaled capital + certain cost + void haircut."""
    p, spread, v = 0.50, 4.0, 0.037
    got = ru_per_contract(p, spread_cents=spread, void_rate=v)
    sigma = math.sqrt(p * (1 - p))
    expected = (p * SIGMA_MULTIPLE * sigma
                + (0.5 * spread / 100.0 + FEE_PER_CONTRACT_USD)
                + p * v)
    assert got == pytest.approx(expected)


def test_a_mid_priced_contract_carries_more_risk_than_a_cheap_one():
    """sigma peaks at 50c. This is why 'risk 1% per trade' is meaningless on
    a binary: 3c and 60c with equal dollars are different risks."""
    mid = ru_per_contract(0.50, spread_cents=2.0, void_rate=0.0)
    cheap = ru_per_contract(0.05, spread_cents=2.0, void_rate=0.0)
    assert mid > cheap * 5


def test_the_no_side_uses_its_own_capital_at_risk():
    """Buying NO at 90c risks 10c, not 90c."""
    yes_at_90 = ru_per_contract(0.90, spread_cents=2.0, void_rate=0.05, side="yes")
    no_at_90 = ru_per_contract(0.90, spread_cents=2.0, void_rate=0.05, side="no")
    assert no_at_90 < yes_at_90


def test_on_a_cheap_contract_a_wide_book_costs_more_than_the_position_moves():
    """Measured spreads run 5-9c on deep futures books and 23-79c on illiquid
    court rungs. On a cheap contract the round-trip cost EXCEEDS the whole
    volatility term: the trade pays more to get in and out than the position
    is expected to move. That is the condition that makes a book untradeable,
    and it is why the cost term is in the RU at all.
    """
    p, spread = 0.10, 60.0
    vol_term = p * SIGMA_MULTIPLE * math.sqrt(p * (1 - p))
    cost_term = 0.5 * spread / 100.0 + FEE_PER_CONTRACT_USD
    assert cost_term > vol_term

    # and the wide book is materially more expensive than a tight one
    tight = ru_per_contract(p, spread_cents=2.0, void_rate=0.0)
    wide = ru_per_contract(p, spread_cents=spread, void_rate=0.0)
    assert wide > tight * 3


def test_the_void_term_scales_with_the_measured_rate():
    """The same edge in esports must clear a ~10% chance of not being paid
    on the thesis at all."""
    mlb = ru_per_contract(0.50, spread_cents=2.0, void_rate=0.005)
    esports = ru_per_contract(0.50, spread_cents=2.0, void_rate=0.099)
    assert esports > mlb


def test_prices_outside_zero_to_one_are_rejected():
    """Cents leaking in where dollars are expected is the likeliest caller bug."""
    with pytest.raises(ValueError):
        ru_per_contract(50.0, spread_cents=2.0, void_rate=0.0)
    with pytest.raises(ValueError):
        ru_per_contract(-0.1, spread_cents=2.0, void_rate=0.0)


def test_an_unknown_side_is_rejected():
    with pytest.raises(ValueError):
        ru_per_contract(0.5, spread_cents=2.0, void_rate=0.0, side="none")


def test_sizing_spends_the_budget_in_risk_units_not_dollars():
    s = size_position(ru_budget=10.0, price=0.50, spread_cents=2.0,
                      void_rate=0.0)
    assert not s.refused
    assert s.contracts >= 1
    assert s.total_ru <= 10.0 + 1e-9
    # one more contract would breach the budget
    assert (s.contracts + 1) * s.ru_per_contract > 10.0


def test_a_wide_book_gets_a_smaller_position_for_the_same_budget():
    tight = size_position(10.0, 0.50, spread_cents=2.0, void_rate=0.0)
    wide = size_position(10.0, 0.50, spread_cents=40.0, void_rate=0.0)
    assert wide.contracts < tight.contracts


def test_a_high_void_vertical_gets_a_smaller_position():
    """Esports at 9.9% must be sized smaller than MLB at 0.5% for the same
    budget, automatically."""
    mlb = size_position(10.0, 0.50, spread_cents=2.0, void_rate=0.005)
    esports = size_position(10.0, 0.50, spread_cents=2.0, void_rate=0.099)
    assert esports.contracts < mlb.contracts


def test_sub_three_cent_positions_are_refused_not_sized():
    """A percentage stop is sub-tick there: 50% of 1.3c is not a price level.
    These are hold-to-resolution, premium spent -- not a position managed."""
    s = size_position(10.0, price=0.013, spread_cents=1.0, void_rate=0.0)
    assert s.refused
    assert s.contracts == 0
    assert "sub" in s.reason.lower()
    assert MIN_PRICE_DOLLARS == 0.03


def test_unknown_structure_is_refused_not_sized():
    """If the exposure is not known it cannot be sized. Spec section 5."""
    for structure in ("disputed", "indeterminate"):
        s = size_position(10.0, 0.50, spread_cents=2.0, void_rate=0.0,
                          structure=structure)
        assert s.refused, structure
        assert s.contracts == 0
        assert "structure" in s.reason.lower()
    assert UNSIZEABLE_STRUCTURES == frozenset({"disputed", "indeterminate"})


def test_a_known_structure_is_sized_normally():
    for structure in ("threshold_ladder", "exclusive_field",
                      "two_sided_handicap", "independent_basket",
                      "fixed_cardinality", "standalone_binary"):
        s = size_position(10.0, 0.50, spread_cents=2.0, void_rate=0.0,
                          structure=structure)
        assert not s.refused, structure


def test_a_budget_too_small_for_one_contract_is_refused():
    s = size_position(ru_budget=0.001, price=0.50, spread_cents=2.0,
                      void_rate=0.0)
    assert s.refused
    assert s.contracts == 0


def test_positions_in_one_cluster_get_no_diversification_credit():
    """Alcaraz at 61c to compete and 19c to win is ONE position, not two."""
    same = [("c1", 3.0), ("c1", 4.0)]
    assert portfolio_ru(same) == pytest.approx(7.0)


def test_positions_across_clusters_are_root_sum_squared():
    across = [("c1", 3.0), ("c2", 4.0)]
    assert portfolio_ru(across) == pytest.approx(5.0)


def test_clustering_is_by_event_or_by_settlement_source():
    """Two contracts on one event are correlated; so are two contracts that
    depend on the same authority publishing."""
    assert cluster_key("KXATP-26USO", "ATP") == cluster_key("KXATP-26USO", "ATP")
    assert cluster_key("KXATP-26USO", "ATP") != cluster_key("KXNFL-27", "ATP")


def test_an_empty_book_carries_no_risk():
    assert portfolio_ru([]) == 0.0


def test_aggregation_never_exceeds_the_linear_sum():
    """Sanity: sqrt-combining across clusters cannot invent risk."""
    positions = [("a", 2.0), ("b", 3.0), ("c", 6.0)]
    assert portfolio_ru(positions) <= sum(ru for _, ru in positions)
