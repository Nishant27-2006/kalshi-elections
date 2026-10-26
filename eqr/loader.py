"""Reads the book recorder's JSONL into memory.

A malformed line is SKIPPED, not fatal. The recorder appends while this
reads, so a torn final line is normal and must never abort a research run.
"""
from __future__ import annotations

import json
from pathlib import Path


def load_snapshots(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def latest_by_ticker(rows: list[dict]) -> dict[str, dict]:
    """Newest snapshot per ticker. Ties resolve to the later occurrence."""
    out: dict[str, dict] = {}
    for r in rows:
        t = r.get("ticker")
        if t is None:
            continue
        prev = out.get(t)
        if prev is None or r.get("ts", 0) > prev.get("ts", 0):
            out[t] = r
    return out
