"""Alpha 3 -- your best signal, group-neutralized.  >>> YOURS <<<

Take whichever of alpha_01 / alpha_02 survived Day 6, then demean within
series and z-score, using eqr/neutralize.py. Report the IC before and
after. If it collapses, that is the finding, and it is a more valuable
thing to say in an interview than a large unneutralized IC.
"""
from __future__ import annotations


class Alpha:
    name = "alpha_03_neutral"

    def compute(self, rows: list[dict]) -> list[float | None]:
        raise NotImplementedError("Day 8: yours to write")
