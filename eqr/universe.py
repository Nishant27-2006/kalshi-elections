"""Universe construction.

>>> THE AUTHOR WRITES THE BODIES. <<<

Measured 2026-08-30: paging /markets returns ONLY KXMVECROSSCATEGORY combo
shards -- 15,000 of them, all with zero candlesticks. Sorting a universe by
volume without excluding them selects entirely untradeable synthetics.
"""
from __future__ import annotations

COMBO_PREFIX = "KXMVECROSSCATEGORY"


def exclude_combos(rows: list[dict]) -> list[dict]:
    """Drop every row whose ticker starts with COMBO_PREFIX."""
    raise NotImplementedError("Day 5: yours to write")


def liquidity_screen(rows: list[dict], asof_ts: int, min_v24: float,
                     max_spread_c: float) -> list[dict]:
    """Latest snapshot per ticker AT OR BEFORE asof_ts, passing the screen.

    POINT-IN-TIME IS THE WHOLE POINT. A row dated after asof_ts must never
    influence the result, not even to decide membership. Screen on the
    v24 and spread_c recorded in the asof snapshot itself.
    """
    raise NotImplementedError("Day 5: yours to write")
