"""Turn resolved markets + daily candles into leakage-safe decision snapshots.

A snapshot is (market, decision time T) with only what was observable at T:
the last daily candle that ENDED at or before T (bid/ask/last/volume/OI), the
price path before T, and static fields fixed at listing (title, rules, open
time, event size). Nothing derived from close_time, settlement, or final
volume enters a feature.

Decision times sit on a fixed weekly grid (Mondays, 04:00 UTC = the end of
Kalshi's daily candle). A grid anchored to each market's close would leak the
timing of early-closing markets (a dropout market closes when the dropout
happens), so the grid is anchored to the calendar instead.
"""
from __future__ import annotations

import math
import os
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from forecast.kalshi_data import CACHE, load_candles, ts, universe

WEEK = 7 * 86400
GRID_ANCHOR = int(datetime(2021, 1, 4, 4, 0, tzinfo=timezone.utc).timestamp())  # a Monday 04:00 UTC
STALE_SECONDS = 3 * 86400
SNAP_PATH = os.path.join(CACHE, "snapshots.parquet")


def _f(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _field(c: dict, group: str, key: str):
    g = c.get(group) or {}
    v = g.get(key + "_dollars")
    if v is None:
        v = g.get(key)
    return _f(v)


def parse_candles(cs: list[dict]) -> pd.DataFrame:
    rows = []
    for c in cs or []:
        rows.append({
            "t": int(c["end_period_ts"]),
            "bid": _field(c, "yes_bid", "close"),
            "ask": _field(c, "yes_ask", "close"),
            "last": _field(c, "price", "close"),
            "hi": _field(c, "price", "high"),
            "lo": _field(c, "price", "low"),
            "vol": _f(c.get("volume_fp", c.get("volume"))) or 0.0,
            "oi": _f(c.get("open_interest_fp", c.get("open_interest"))) or 0.0,
        })
    df = pd.DataFrame(rows)
    return df.sort_values("t").reset_index(drop=True) if len(df) else df


# --- archetypes: from listing-time text only ---------------------------------

ARCH_RULES = [
    ("mention", r"\b(say|says|said|mention|tweet|post on truth)\b"),
    ("approval", r"approval|approve rating|favorab"),
    ("court_ruling", r"supreme court|scotus|rule (unanimously )?in favor|ruling| v\. "),
    ("placement", r"finish (\d|1st|2nd|3rd|4th|5th|first|second|third)|\b(2nd|3rd|4th|5th) place|outright|place in"),
    ("referendum", r"referend|proposition|ballot measure|initiative|vote to (end|ban|approve|exempt|repeal)"),
    ("legislative_vote", r"vote (for|on|against)|voting for|confirm|pass(es)? the (senate|house)|cloture|filibuster|expel"),
    ("margin_threshold", r"margin|vote percent|vote share|turnout|by more than|at least \d|how many|seats|above|below|between|\d+-\d+"),
    ("primary", r"primary|nominee|nomination|runoff"),
    ("appointment", r"next .*(secretary|chair|press|justice|attorney)|join the .*admin|nominate|appoint|endorse"),
    ("visit_meet", r"\bvisit|\bmeet|attend|talk to|trip"),
    ("party_winner", r"\bparty\b|democrat|republican|which party|control"),
    ("person_winner", r"winner|win the|elected|next .*(leader|prime minister|president|mayor|pope|pm)"),
    ("policy_event", r"law|bill|sign|pardon|impeach|resign|leave|out as|tariff|executive order|indict|arrest|charged|"
                     r"release|sanction|eliminat|issue|agree|prohibit|exit|recogni|get rid|ban|reduce|remove|announce|act\b"),
]


def archetype(title: str, series_title: str, strike_type: str | None) -> str:
    text = f"{title} || {series_title}".lower()
    for name, pat in ARCH_RULES:
        if re.search(pat, text):
            return name
    if strike_type in ("greater", "less", "between", "greater_or_equal", "less_or_equal"):
        return "margin_threshold"
    return "other"


def build(min_life_days: float = 3.0) -> pd.DataFrame:
    uni = universe()
    event_size: dict[str, int] = {}
    event_close: dict[str, float] = {}
    for m in uni:
        e = m["event_ticker"]
        event_size[e] = event_size.get(e, 0) + 1
        event_close[e] = max(event_close.get(e, 0.0), ts(m["close_time"]))
    out = []
    for m in uni:
        cs = load_candles(m["ticker"])
        if not cs:
            continue
        df = parse_candles(cs)
        if df.empty:
            continue
        o, c = ts(m["open_time"]), ts(m["close_time"])
        first = GRID_ANCHOR + math.ceil((o + 86400 - GRID_ANCHOR) / WEEK) * WEEK
        arch = archetype(m.get("title") or "", m.get("_series_title") or "", m.get("strike_type"))
        tvals = df["t"].to_numpy()
        for T in range(int(first), int(c), WEEK):
            i = int(np.searchsorted(tvals, T, side="right")) - 1
            if i < 0:
                continue
            row = df.iloc[i]
            bid, ask = row["bid"], row["ask"]
            if bid is None or ask is None or not (0 < bid < ask < 1) or pd.isna(bid) or pd.isna(ask):
                continue
            hist = df.iloc[: i + 1]
            last7 = hist[hist["t"] > T - WEEK]
            prev = hist[hist["t"] <= T - WEEK]
            mid = (bid + ask) / 2
            mid_prev = None
            if len(prev):
                pb, pa = prev.iloc[-1]["bid"], prev.iloc[-1]["ask"]
                if pb is not None and pa is not None and not pd.isna(pb) and not pd.isna(pa) and 0 < pb < pa < 1:
                    mid_prev = (pb + pa) / 2
            lasts = hist["last"].dropna().tail(15).to_numpy()
            # forward window: used ONLY to simulate whether a resting order would
            # have filled, never as a feature
            fut = df[(df["t"] > T) & (df["t"] <= T + WEEK)]
            out.append({
                "ticker": m["ticker"], "event": m["event_ticker"], "series": m["_series"],
                "category": m.get("_category"), "title": m.get("title"),
                "series_title": m.get("_series_title"), "archetype": arch,
                "T": T, "open_ts": o, "event_close": event_close[m["event_ticker"]],
                "age_days": (T - o) / 86400, "bid": bid, "ask": ask, "mid": mid,
                "spread": ask - bid, "stale_days": (T - row["t"]) / 86400,
                "vol_7d": float(last7["vol"].sum()), "vol_cum": float(hist["vol"].sum()),
                "oi": float(row["oi"]), "n_candles": len(hist),
                "d_mid_7d": (mid - mid_prev) if mid_prev is not None else np.nan,
                "realized_vol": float(np.std(np.diff(lasts))) if len(lasts) > 3 else np.nan,
                "event_size": event_size[m["event_ticker"]],
                "fwd_lo": float(fut["lo"].min()) if len(fut) and fut["lo"].notna().any() else np.nan,
                "fwd_hi": float(fut["hi"].max()) if len(fut) and fut["hi"].notna().any() else np.nan,
                "outcome": 1 if m["result"] == "yes" else 0,
            })
    snap = pd.DataFrame(out)
    from forecast.participants import add_features
    snap = add_features(snap)
    snap.to_parquet(SNAP_PATH)
    return snap


def load() -> pd.DataFrame:
    return pd.read_parquet(SNAP_PATH)


if __name__ == "__main__":
    s = build()
    print(len(s), "snapshots,", s["ticker"].nunique(), "markets,", s["event"].nunique(), "events")
    print(s["archetype"].value_counts())
