"""Transaction costs.

>>> THE AUTHOR WRITES THE BODIES. <<<

Everything here is in PROBABILITY POINTS (dollars per contract, 0-1), the
same units as panel.fwd_ret, so edges and costs are directly comparable.
That is the whole reason this module exists as its own file: unit
confusion between cents and probability is the most common way a
prediction-market backtest reports a profit it never had.

Reuse agent/risk_unit.fee_per_contract. Do NOT re-derive 0.07*P*(1-P) here.
"""
from __future__ import annotations


def round_trip_cost(price: float, spread_c: float) -> float:
    """Spread (converted to dollars) plus FEE_LEGS fee charges at `price`.

    Charging the whole spread rather than half is deliberate and
    conservative: a marketable order crosses it, and assuming you get filled
    at the mid is the second most common way a backtest lies.
    """
    raise NotImplementedError("Day 7: yours to write")


def net_edge(gross_edge: float, price: float, spread_c: float) -> float:
    """gross_edge minus the round trip. May be negative; do not clamp."""
    raise NotImplementedError("Day 7: yours to write")


def breakeven_edge(price: float, spread_c: float) -> float:
    """The gross edge at which net_edge is exactly zero."""
    raise NotImplementedError("Day 7: yours to write")


def capacity_curve(gross_edge: float, price: float, spread_c: float,
                   turnovers: list[float]) -> list[tuple[float, float]]:
    """(turnover, annual_return) for each turnover, in probability points.

    annual_return = net_edge * turnover. The shape is the lesson: with a
    fixed per-trade edge, return is LINEAR in turnover and flips sign the
    moment cost exceeds edge. There is no turnover that rescues a strategy
    whose net edge is negative.
    """
    raise NotImplementedError("Day 7: yours to write")
