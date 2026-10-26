"""
Exit logic. Deterministic, pure, no network -- same discipline as risk.py.

Before this module the system could only open positions: `grep -rn "sell"
agent/` returned nothing but comments, and every "24/7" claim quietly assumed
someone would close by hand. Three exits are supported:

  take_profit -- mark reaches a multiple of entry
  stop_loss   -- mark falls to a fraction of entry
  time        -- market close is near and we are not holding to resolution

The LLM has no say here. Levels come from ExitLimits and the position record.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, TypedDict

from .config import EXITS, ExitLimits
from .portfolio import Position

ExitKind = Literal["take_profit", "stop_loss", "time", "hold"]


class ExitDecision(TypedDict):
    should_exit: bool
    kind: ExitKind
    reason: str
    exit_price_cents: float


def _hold(reason: str, mark: float | None = None) -> ExitDecision:
    return {"should_exit": False, "kind": "hold", "reason": reason,
            "exit_price_cents": float(mark) if mark is not None else 0.0}


def default_levels(entry_price_cents: float,
                   limits: ExitLimits | None = None) -> tuple[float | None, float | None, bool]:
    """(take_profit, stop_loss, hold_to_resolution) for a fresh position.

    Sub-tick stops are the interesting case. A 50% stop on a 1.3c contract is
    0.65c, which is not a quotable price -- the position would either never
    stop or stop at 1c, i.e. a 23% loss dressed up as a 50% one. Those
    positions get no stop at all and are flagged hold_to_resolution, which is
    an honest description of what a sub-3c lottery ticket actually is.
    """
    lim = limits or EXITS
    entry = float(entry_price_cents)
    tp = min(lim.max_exit_price_cents, round(entry * lim.take_profit_multiple, 1))
    if entry < lim.min_stoppable_entry_cents:
        return tp, None, True
    sl = max(lim.min_exit_price_cents, round(entry * lim.stop_loss_fraction, 1))
    return tp, sl, False


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def evaluate_exit(pos: Position, market: dict, *, now: datetime | None = None,
                  limits: ExitLimits | None = None) -> ExitDecision:
    """Should this position be closed right now, and at what price?

    Checks run most-fatal-first: stop loss before take profit, so a position
    that gapped through both in one poll exits at the stop rather than
    booking an imaginary win.
    """
    lim = limits or EXITS
    now = now or datetime.now(timezone.utc)

    mark = pos.mark_price_cents(market)
    if mark is None:
        # No two-sided quote means no exit price we could actually hit.
        return _hold("no two-sided quote; cannot mark position")

    if pos.stop_loss_cents is not None and mark <= pos.stop_loss_cents:
        return {"should_exit": True, "kind": "stop_loss",
                "reason": (f"stop: mark {mark:.1f}c <= stop {pos.stop_loss_cents:.1f}c "
                           f"(entry {pos.entry_price_cents:.1f}c)"),
                "exit_price_cents": mark}

    if pos.take_profit_cents is not None and mark >= pos.take_profit_cents:
        return {"should_exit": True, "kind": "take_profit",
                "reason": (f"target: mark {mark:.1f}c >= target "
                           f"{pos.take_profit_cents:.1f}c (entry {pos.entry_price_cents:.1f}c)"),
                "exit_price_cents": mark}

    close_dt = _parse_ts(pos.close_ts)
    if close_dt is not None and not pos.hold_to_resolution:
        deadline = close_dt - timedelta(hours=lim.time_exit_buffer_hours)
        if now >= deadline:
            return {"should_exit": True, "kind": "time",
                    "reason": (f"time exit: within {lim.time_exit_buffer_hours:g}h of "
                               f"close {pos.close_ts}"),
                    "exit_price_cents": mark}

    if pos.hold_to_resolution:
        return _hold(f"hold to resolution (mark {mark:.1f}c)", mark)
    return _hold(f"no exit trigger (mark {mark:.1f}c)", mark)
