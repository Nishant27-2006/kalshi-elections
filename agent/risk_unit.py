"""The Risk Unit: position sizing for binary contracts.

"Risk 1% per trade" is meaningless here. Buying YES at 3c and at 60c with the
same dollars are entirely different risks: the first has 3c of downside and a
tiny chance of 97c, the second 60c down against 40c up. So the unit is
EXPECTED ADVERSE EXCURSION, not notional.

    1 RU = $1 of expected adverse move over the holding period.

Per contract, at price p (DOLLARS 0-1):

    RU = p * k * sqrt(p(1-p))        volatility-scaled capital at risk
       + (half-spread + fee)         certain round-trip cost
       + p * v                       abandonment haircut

See docs/superpowers/specs/2026-08-19-prediction-market-fund-design.md section 5.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

# The planned adverse traverse, in standard deviations. Tuned ONLY by the
# monthly offline re-fit (spec section 7.4), never by the online learner.
SIGMA_MULTIPLE: float = 2.0

# Placeholder until the real Kalshi schedule is read and encoded -- spec
# section 12, open question 2. Deliberately non-zero so sizing is never
# optimistic about costs.
FEE_PER_CONTRACT_USD: float = 0.01


def ru_per_contract(price: float, spread_cents: float, void_rate: float,
                    side: str = "yes") -> float:
    """Risk Units carried by ONE contract.

    price        entry price in DOLLARS 0-1 (not cents)
    spread_cents bid-ask spread in CENTS, as the API reports it
    void_rate    measured abandonment rate for the vertical, 0-1
    side         "yes" or "no" -- decides which end is capital at risk
    """
    if not 0.0 <= price <= 1.0:
        raise ValueError(f"price must be dollars 0-1, got {price!r} "
                         "(did you pass cents?)")
    if side not in ("yes", "no"):
        raise ValueError(f"side must be 'yes' or 'no', got {side!r}")
    if spread_cents < 0 or not 0.0 <= void_rate <= 1.0:
        raise ValueError("spread_cents must be >=0 and void_rate 0-1")

    capital = price if side == "yes" else (1.0 - price)
    sigma = math.sqrt(price * (1.0 - price))

    vol_term = capital * SIGMA_MULTIPLE * sigma
    cost_term = 0.5 * spread_cents / 100.0 + FEE_PER_CONTRACT_USD
    void_term = capital * void_rate
    return vol_term + cost_term + void_term


# Below this, a percentage stop is smaller than one tick, so the position
# cannot be managed -- only held to resolution. Matches the existing
# RiskLimits.min_price_cents = 3.0.
MIN_PRICE_DOLLARS: float = 0.03

# Structures whose true exposure is unknown. Refused, never sized.
UNSIZEABLE_STRUCTURES: frozenset[str] = frozenset({"disputed", "indeterminate"})


@dataclass(frozen=True)
class Sizing:
    """The result of sizing one candidate. `refused` is not an error --
    refusing is a normal, frequent outcome."""
    contracts: int
    ru_per_contract: float
    total_ru: float
    refused: bool
    reason: str


def size_position(ru_budget: float, price: float, spread_cents: float,
                  void_rate: float, structure: str = "threshold_ladder",
                  side: str = "yes") -> Sizing:
    """How many contracts fit inside `ru_budget` Risk Units.

    RU is linear in contract count, so sizing is a division -- but the two
    refusals below are checked FIRST and are not overridable by a larger
    budget.
    """
    if structure in UNSIZEABLE_STRUCTURES:
        return Sizing(0, 0.0, 0.0, True,
                      f"unknown structure: {structure!r} -- exposure is not "
                      "known well enough to size")

    capital = price if side == "yes" else (1.0 - price)
    if capital < MIN_PRICE_DOLLARS:
        return Sizing(0, 0.0, 0.0, True,
                      f"sub-{MIN_PRICE_DOLLARS * 100:.0f}c position: a "
                      "percentage stop would be sub-tick; hold-to-resolution "
                      "only")

    per = ru_per_contract(price, spread_cents, void_rate, side)
    contracts = int(ru_budget // per)
    if contracts < 1:
        return Sizing(0, per, 0.0, True,
                      f"budget {ru_budget:.4f} RU is below one contract "
                      f"at {per:.4f} RU")
    return Sizing(contracts, per, contracts * per, False, "")


def portfolio_ru(positions: list[tuple[str, str, float]]) -> float:
    """Total Risk Units across a book.

    positions: (event_ticker, settlement_source, ru) triples.

    Two positions join the same cluster if they share an EVENT or a
    SETTLEMENT SOURCE, and the relation is transitive -- so clusters are
    connected components, not key matches. Sum LINEARLY within a component
    (no diversification credit), ROOT-SUM-SQUARE across components.

    A key of the form f"{event}|{source}" would be a CONJUNCTION: two
    different matches settled by one authority would land in different
    clusters and be credited as diversified. Transitive grouping is the
    conservative direction -- it groups more and credits less.
    """
    if not positions:
        return 0.0

    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_a] = root_b

    for i, (event, source, _ru) in enumerate(positions):
        node = f"pos:{i}"
        find(node)
        # Normalise before keying: "ATP", "atp" and "ATP " must land in the
        # same cluster, or a caller typo silently buys diversification
        # credit and under-groups correlated risk -- the dangerous
        # direction. Blank fields must still not merge unrelated positions,
        # which is why the emptiness check runs on the normalised value.
        event_key = event.strip().upper() if event else event
        source_key = source.strip().upper() if source else source
        if event_key:
            union(node, f"event:{event_key}")
        if source_key:
            union(node, f"source:{source_key}")

    totals: dict[str, float] = defaultdict(float)
    for i, (_event, _source, ru) in enumerate(positions):
        totals[find(f"pos:{i}")] += ru
    return math.sqrt(sum(value * value for value in totals.values()))
