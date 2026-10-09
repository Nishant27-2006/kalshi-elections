"""Forward paper-forecast ledger: the only leakage-free test there is.

Every row is a probability recorded BEFORE the market resolves, with a UTC
timestamp, the market's bid/ask at that moment, and the forecaster that made
it. Rows are append-only (git keeps the history), so nothing can be revised
after the fact. GET only; no orders anywhere.

    python -m forecast.ledger snapshot        # B0 + analog forecasts on covered open markets
    python -m forecast.ledger add FILE.jsonl  # append externally made forecasts (e.g. LLM agents)
    python -m forecast.ledger score           # grade every row whose market has settled

Forecasters:
  B0            old-plan estimator (archetype intercept + market slope), fit on ALL resolved history
  analog_lean   docs/analogs.md polls + lean model, D legs of 2026 Senate/governor markets only
  llm:<name>    subagent judgment from retrieved knowledge chunks + rules + price (forecast/ledger_llm.md)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from forecast.kalshi_data import _get
from forecast.retrieval import load_chunks
from forecast.snapshots import archetype

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "forecast", "ledger", "ledger.jsonl")
SCORES = os.path.join(ROOT, "forecast", "ledger", "scores.json")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def covered_events() -> list[str]:
    ms = set()
    for c in load_chunks():
        ms.update(m.upper() for m in c.markets)
    return sorted(ms)


def open_markets(prefixes: list[str]) -> list[dict]:
    """Expand note tickers (events or series) to open markets with a two-sided quote."""
    out, seen = [], set()
    for t in prefixes:
        d = _get(f"/events/{t}", {"with_nested_markets": "true"})
        evs = [d["event"]] if d.get("event") else []
        if not evs:
            d = _get("/events", {"series_ticker": t, "status": "open", "with_nested_markets": "true", "limit": 200})
            evs = d.get("events") or []
        for e in evs:
            for m in e.get("markets") or []:
                if m.get("status") not in ("active", "open") or m["ticker"] in seen:
                    continue
                b, a = float(m.get("yes_bid_dollars") or 0), float(m.get("yes_ask_dollars") or 0)
                if not (0 < b < a < 1):
                    continue
                seen.add(m["ticker"])
                out.append({"ticker": m["ticker"], "event": e["event_ticker"], "series": e.get("series_ticker"),
                            "title": m.get("title") or e.get("title"), "series_title": e.get("title"),
                            "rules": m.get("rules_primary", ""), "bid": b, "ask": a, "mid": (a + b) / 2,
                            "close_time": m.get("close_time")})
    return out


def _append(rows: list[dict]):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def snapshot():
    from forecast.estimators import ESTIMATORS
    from forecast.snapshots import load
    ts = _now()
    mk = open_markets(covered_events())
    df = pd.DataFrame(mk)
    df["archetype"] = [archetype(t or "", s or "", None) for t, s in zip(df["title"], df["series_title"])]
    hist = load()
    b0 = ESTIMATORS["old_plan"]().fit(hist)   # forward use: fit on every resolved market we have
    p = b0.predict(df)
    rows = [{"ts": ts, "forecaster": "B0", "ticker": r.ticker, "event": r.event, "p_yes": round(float(pi), 4),
             "bid": r.bid, "ask": r.ask, "mid": round(r.mid, 4), "close_time": r.close_time}
            for r, pi in zip(df.itertuples(), p)]
    ana = os.path.join(ROOT, "data_cache", "analogs_2026_vs_kalshi.json")
    if os.path.exists(ana):
        by = {r.ticker: r for r in df.itertuples()}
        for a in json.load(open(ana, encoding="utf-8")):
            r = by.get(a.get("leg"))
            if r is not None:
                rows.append({"ts": ts, "forecaster": "analog_lean", "ticker": r.ticker, "event": r.event,
                             "p_yes": a["p_lean"], "bid": r.bid, "ask": r.ask, "mid": round(r.mid, 4),
                             "close_time": r.close_time, "note": "polls + lean model, docs/analogs.md"})
    _append(rows)
    df.to_json(os.path.join(ROOT, "data_cache", "ledger_universe.json"), orient="records")
    print(f"{ts}: {len(rows)} rows ({len(df)} markets, {sum(r['forecaster'] == 'analog_lean' for r in rows)} analog)")


def add(path: str):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            assert r.get("forecaster", "").startswith("llm:") and 0 <= r["p_yes"] <= 1 and r.get("ts")
            rows.append(r)
    _append(rows)
    print(f"appended {len(rows)} rows from {path}")


def score():
    rows = [json.loads(l) for l in open(LEDGER, encoding="utf-8")]
    results = {}
    for t in sorted({r["ticker"] for r in rows}):
        m = (_get(f"/markets/{t}") or {}).get("market") or {}
        if m.get("result") in ("yes", "no"):
            results[t] = 1 if m["result"] == "yes" else 0
    graded = [dict(r, outcome=results[r["ticker"]]) for r in rows if r["ticker"] in results]
    summary = {"scored_at": _now(), "rows": len(rows), "graded": len(graded), "by_forecaster": {}}
    for f in sorted({r["forecaster"] for r in graded}):
        g = [r for r in graded if r["forecaster"] == f]
        bm = np.mean([(r["p_yes"] - r["outcome"]) ** 2 for r in g])
        bk = np.mean([(r["mid"] - r["outcome"]) ** 2 for r in g])
        summary["by_forecaster"][f] = {"n": len(g), "markets": len({r["ticker"] for r in g}),
                                       "brier": round(float(bm), 5), "brier_market": round(float(bk), 5),
                                       "skill": round(float(1 - bm / bk), 4) if bk else None}
    with open(SCORES, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "snapshot":
        snapshot()
    elif cmd == "add":
        add(sys.argv[2])
    elif cmd == "score":
        score()
