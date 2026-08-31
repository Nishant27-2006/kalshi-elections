"""The contract every alpha satisfies. Delivered -- do not modify."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Signal(Protocol):
    name: str

    def compute(self, rows: list[dict]) -> list[float | None]:
        """One score per row, same order, same length.

        None means "no opinion on this name" and is excluded from the IC
        rather than treated as zero. A signal that returns 0.0 where it
        means None will have its IC diluted toward zero and you will
        conclude it does not work when in fact you never asked it.

        MUST be a pure function of the CURRENT rows. Reading a forward
        return here is the cardinal sin; the Day 5 canary exists because
        this contract is easy to violate by accident.
        """
        ...
