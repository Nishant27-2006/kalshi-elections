"""Alpha 1 -- short-horizon reversal.  >>> YOURS <<<

HYPOTHESIS (state it before you code it, and do not change it afterwards):
AGENT.md records that momentum-chasing lost at every trigger from 3c to 10c
over n=123, and lost MORE as the trigger rose. That is a mean-reversion
signature. This signal therefore scores a name POSITIVELY when its recent
move was DOWN, expecting reversion.

You need prior snapshots to compute a recent move. `compute` receives only
the current rows, so you must decide how the signal gets its history --
and whatever you decide, the Day 5 canary must still pass. Think about
that before you write anything.
"""
from __future__ import annotations


class Alpha:
    name = "alpha_01_reversal"

    def compute(self, rows: list[dict]) -> list[float | None]:
        raise NotImplementedError("Day 6: yours to write")
