"""Live read-only scan of open political markets: arbitrage first, model edges second.

GET only. Prints candidates; places nothing.

    python -m forecast.scan_now            # writes docs/scan_<date>.md and data_cache/scan_now.json

Arbitrage (payoff guaranteed by the rules, net of the 0.07*P*(1-P) taker fee, at top-of-book size):
  A. Field over-round: in a mutually-exclusive event at most one leg pays YES, so buying NO on every leg
     pays at least n-1. Profitable when the sum over legs of (1 - yes_bid + fee) < n - 1.
  B. Field under-round: buying YES on every leg pays exactly 1 ONLY if some leg must win (exhaustive). Kalshi does not
     flag exhaustiveness, so these are listed as conditional and are not called arbitrage.
  C. Threshold-ladder inversion: for "above X" strikes P(above high) <= P(above low). If the high strike's bid
     exceeds the low strike's ask, buy YES low + NO high: pays >= 1 in every state.
Model edges (NOT arbitrage; backtests found no statistically significant profit, see docs/backtests.md):
  B0 (old-plan estimator), analog_lean and LLM forecasts from the ledger, against current ask/bid net of fee.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from forecast.kalshi_data import CACHE, _get, _paginate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fee(p):
    return 0.07 * p * (1 - p)


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def fetch_open():
    evs = _paginate("/events", {"status": "open", "with_nested_markets": "true"}, "events", limit=200)
    return [e for e in evs if e.get("category") in ("Elections", "Politics")]


def legs(e):
    out = []
    for m in e.get("markets") or []:
        if m.get("status") not in ("active", "open"):
            continue
        out.append({"ticker": m["ticker"], "bid": f(m.get("yes_bid_dollars")), "ask": f(m.get("yes_ask_dollars")),
                    "bid_sz": f(m.get("yes_bid_size_fp")), "ask_sz": f(m.get("yes_ask_size_fp")),
                    "strike_type": m.get("strike_type"), "floor": m.get("floor_strike"), "cap": m.get("cap_strike"),
                    "sub": m.get("yes_sub_title") or m.get("subtitle") or ""})
    return out


def field_arbs(e, L):
    if not e.get("mutually_exclusive") or len(L) < 2:
        return []
    out = []
    # A: buy NO on every leg. NO ask = 1 - yes_bid; needs a YES bid on every leg.
    if all(l["bid"] > 0 for l in L):
        cost = sum((1 - l["bid"]) + fee(1 - l["bid"]) for l in L)
        edge = (len(L) - 1) - cost
        size = min(l["bid_sz"] for l in L)
        if edge > 0:
            out.append({"type": "A field over-round (buy NO on all legs)", "event": e["event_ticker"], "title": e.get("title"),
                        "n_legs": len(L), "sum_yes_bids": round(sum(l["bid"] for l in L), 4),
                        "edge_per_set": round(edge, 4), "max_sets_at_top": size, "guaranteed": True})
    # B: buy YES on every leg; only safe if the field is exhaustive (not verifiable from the API)
    if all(0 < l["ask"] < 1 for l in L):
        cost = sum(l["ask"] + fee(l["ask"]) for l in L)
        if cost < 1:
            out.append({"type": "B field under-round (buy YES on all legs) — ONLY if some leg must win", "event": e["event_ticker"],
                        "title": e.get("title"), "n_legs": len(L), "sum_yes_asks": round(sum(l["ask"] for l in L), 4),
                        "edge_per_set_if_exhaustive": round(1 - cost, 4),
                        "max_sets_at_top": min(l["ask_sz"] for l in L), "guaranteed": False})
    return out


def ladder_arbs(e, L):
    up = [l for l in L if l["strike_type"] in ("greater", "greater_or_equal") and l["floor"] is not None]
    out = []
    up.sort(key=lambda l: float(l["floor"]))
    for i, lo in enumerate(up):
        for hi in up[i + 1:]:
            if lo["ask"] <= 0 or hi["bid"] <= 0:
                continue
            cost = lo["ask"] + fee(lo["ask"]) + (1 - hi["bid"]) + fee(1 - hi["bid"])
            if cost < 1:
                out.append({"type": "C ladder inversion (buy YES low strike + NO high strike)", "event": e["event_ticker"],
                            "title": e.get("title"), "low": lo["ticker"], "low_ask": lo["ask"], "high": hi["ticker"],
                            "high_bid": hi["bid"], "edge_per_pair": round(1 - cost, 4),
                            "max_pairs_at_top": min(lo["ask_sz"], hi["bid_sz"]), "guaranteed": True})
    return out


def model_edges(live: dict, min_edge=0.05, max_spread=0.10):
    rows = []
    led = os.path.join(ROOT, "forecast", "ledger", "ledger.jsonl")
    if not os.path.exists(led):
        return rows
    latest = {}
    for line in open(led, encoding="utf-8"):
        r = json.loads(line)
        latest[(r["forecaster"], r["ticker"])] = r
    for (fc, t), r in latest.items():
        q = live.get(t)
        if not q or not (0 < q["bid"] < q["ask"] < 1) or q["ask"] - q["bid"] > max_spread:
            continue
        p = r["p_yes"]
        ey = p - q["ask"] - fee(q["ask"])
        en = (1 - p) - (1 - q["bid"]) - fee(1 - q["bid"])
        side, e, px, sz = ("YES", ey, q["ask"], q["ask_sz"]) if ey >= en else ("NO", en, 1 - q["bid"], q["bid_sz"])
        if e > min_edge and 0.03 <= px <= 0.97:
            rows.append({"forecaster": fc, "ticker": t, "side": side, "price": round(px, 4), "p_model": p,
                         "forecast_ts": r["ts"], "edge_net_fee": round(e, 4), "spread": round(q["ask"] - q["bid"], 4),
                         "size_at_top": sz, "reasoning": r.get("reasoning", "")})
    rows.sort(key=lambda x: -x["edge_net_fee"])
    return rows


def main():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    evs = fetch_open()
    arbs, live = [], {}
    for e in evs:
        L = legs(e)
        for l in L:
            live[l["ticker"]] = l
        arbs += field_arbs(e, L) + ladder_arbs(e, L)
    edges = model_edges(live)
    json.dump({"ts": ts, "n_events": len(evs), "n_markets": len(live), "arbs": arbs, "edges": edges},
              open(os.path.join(CACHE, "scan_now.json"), "w", encoding="utf-8"), indent=1)
    print(f"{ts}: {len(evs)} open political events, {len(live)} markets")
    for k in ("A", "B", "C"):
        print(k, sum(a["type"].startswith(k) for a in arbs))
    print("model edges", len(edges), {fc: sum(e["forecaster"] == fc for e in edges) for fc in {e["forecaster"].split(":")[0] for e in edges}})


if __name__ == "__main__":
    main()
