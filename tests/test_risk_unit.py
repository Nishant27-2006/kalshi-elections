import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent.risk_unit import (FEE_PER_CONTRACT_USD, MIN_PRICE_DOLLARS,
                             SIGMA_MULTIPLE, Sizing, ru_per_contract,
                             size_position, UNSIZEABLE_STRUCTURES,
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


def test_the_no_side_capital_at_risk_is_pinned_to_10c_not_90c():
    """Ordering alone (no_at_90 < yes_at_90) does not pin the NO-side capital
    magnitude -- it would pass just as well if capital were mistakenly halved
    or otherwise scaled down. By hand, at price=0.90 side='no':

        capital   = 1 - 0.90                        = 0.10
        sigma     = sqrt(0.90 * 0.10)                = 0.3
        vol_term  = capital * SIGMA_MULTIPLE * sigma = 0.10 * 2.0 * 0.3  = 0.06
        cost_term = 0.5 * 2 / 100 + FEE_PER_CONTRACT_USD (0.01)         = 0.02
        void_term = capital * void_rate (0.005)                        = 0.0005
        RU        = 0.06 + 0.02 + 0.0005                                = 0.0805
    """
    no_at_90 = ru_per_contract(0.90, spread_cents=2.0, void_rate=0.005, side="no")
    assert no_at_90 == pytest.approx(0.0805)


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


def test_the_sub_three_cent_refusal_applies_to_the_no_side_too():
    """Buying NO at 98c risks 2c -- the same sub-tick-stop problem."""
    s = size_position(10.0, price=0.98, spread_cents=1.0, void_rate=0.0, side="no")
    assert s.refused
    assert s.contracts == 0


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


def test_positions_on_one_event_get_no_diversification_credit():
    """Alcaraz at 61c to compete and 19c to win is ONE position, not two."""
    assert portfolio_ru([("E1", "SRC-A", 3.0), ("E1", "SRC-B", 4.0)]) == pytest.approx(7.0)


def test_positions_sharing_a_settlement_source_also_cluster():
    """Two different events settled by one authority share that authority's
    failure mode. The previous AND-keyed implementation silently credited
    this pair as diversified."""
    assert portfolio_ru([("E1", "ATP", 3.0), ("E2", "ATP", 4.0)]) == pytest.approx(7.0)


def test_unrelated_positions_are_root_sum_squared():
    assert portfolio_ru([("E1", "SRC-A", 3.0), ("E2", "SRC-B", 4.0)]) == pytest.approx(5.0)


def test_clustering_is_transitive():
    """A shares an event with B; B shares a source with C. All three are one
    cluster -- conservative by design, because under-grouping understates
    correlated risk."""
    chain = [("E1", "SRC-A", 1.0), ("E1", "SRC-B", 2.0), ("E2", "SRC-B", 3.0)]
    assert portfolio_ru(chain) == pytest.approx(6.0)


def test_blank_fields_do_not_merge_unrelated_positions():
    """Two positions with no event and no source are not thereby related."""
    assert portfolio_ru([("", "", 3.0), ("", "", 4.0)]) == pytest.approx(5.0)


def test_labels_that_differ_only_in_case_or_whitespace_still_cluster():
    """A caller typo ("atp" vs "ATP", or a trailing space) must not silently
    buy diversification credit -- under-grouping understates correlated
    risk, which is the dangerous direction."""
    assert portfolio_ru([("E1", "ATP", 3.0), ("E2", "atp", 4.0)]) == pytest.approx(7.0)
    assert portfolio_ru([("E1", "ATP", 3.0), ("E2", "ATP ", 4.0)]) == pytest.approx(7.0)


def test_an_empty_book_carries_no_risk():
    assert portfolio_ru([]) == 0.0
