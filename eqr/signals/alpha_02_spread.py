"""Alpha 2 -- spread as an adverse-selection proxy.  >>> YOURS <<<

HYPOTHESIS: a wide bid-ask spread on Kalshi signals an uninformed or thin
book. Whether that predicts return POSITIVELY or NEGATIVELY is exactly
what you do not know yet -- state your prior, then let the IC tell you,
and do NOT flip the sign afterwards and call it a discovery.
"""
from __future__ import annotations


class Alpha:
    name = "alpha_02_spread"

    def compute(self, rows: list[dict]) -> list[float | None]:
        raise NotImplementedError("Day 6: yours to write")
