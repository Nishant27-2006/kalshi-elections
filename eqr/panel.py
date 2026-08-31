"""The point-in-time cross-sectional panel.

>>> THE AUTHOR WRITES THE BODIES. <<<

This is the ONLY module permitted to know about time, and therefore the
only place lookahead bias can enter the system. Everything downstream is
pure arithmetic on what this returns.

Mid price is (yes_bid_c + yes_ask_c) / 2 / 100, in probability units.
Forward return is a DIFFERENCE of probabilities, not a log return -- a
contract at 2c going to 4c has doubled, but as a probability it moved two
points, and probability points are what you get paid in.
"""
from __future__ import annotations


def build(rows: list[dict], asof_ts: int, horizon_s: int) -> list[dict]:
    """One row per ticker live at asof_ts, plus fwd_ret and
    resolves_in_window.

    fwd_ret = mid(first snapshot at ts >= asof_ts + horizon_s) - mid(asof).
    None when no such snapshot exists. resolves_in_window is True when the
    forward snapshot's mid is exactly 0.0 or 1.0.

    Every other field on the returned row MUST be copied from the asof
    snapshot. Copying anything from the forward snapshot is the bug the
    canary test exists to catch.
    """
    raise NotImplementedError("Day 5: yours to write")


def cross_section(rows: list[dict], asof_ts: int,
                  horizon_s: int) -> tuple[list[dict], list[float]]:
    """(rows, forward_returns) with rows lacking fwd_ret dropped, aligned."""
    raise NotImplementedError("Day 5: yours to write")
