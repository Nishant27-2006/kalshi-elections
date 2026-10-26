"""Jev reads the knowledge graph and judges whether a price spike is explained by news.

Jev answers three narrow questions; code owns the decision and the order price.

State sent per spike (only information that existed at the spike's close):
  market_question, yes_outcome, rules     contract text
  price_move                              the move, in words, computed by code
  recent_notes                            knowledge-graph claims dated in the 7 days before the spike
                                          (code does the date filter: Jev is weak at comparing dates)

Decision table (code):
  decided >= 0.7                                     -> "decided"      never trade against it
  news >= 0.7 and Jev's direction agrees with move    -> "explained"    the move has a reason
  news <= 0.3, or no recent notes                     -> "unexplained"  candidate to fade
  anything else                                       -> "unclear"      no trade

    python -m forecast.spike_jev backtest     # ask Jev about every historical spike that has recent notes
    python -m forecast.spike_jev live         # scan open covered markets now; print limit-order PROPOSALS

Proposals are never sent to Kalshi. This module only makes GET requests.
Backtest caveat: the knowledge notes were written in 2026 with dated claims.
A claim dated before the spike was public at the spike, but which claims got
written down was chosen with hindsight, so the explained/unexplained split is
likely cleaner in the backtest than it will be live.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from typesafe_sdk import Choice, Noul

from forecast.jev_features import HEADERS, load_markets
from forecast.jev_questions import MODEL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data_cache", "spike_jev.jsonl")
QSET = "s1"
WINDOW_DAYS = 7
YES, NO = 0.7, 0.3

QUESTIONS = {
    "news": Noul(
        instructions="Does a note in `recent_notes` report a new development about the subject of `market_question`?",
        criteria={"true": "At least one note reports something that happened recently to the people, race, bill, or event the market is about.",
                  "false": "The notes are about other subjects, or only repeat background facts that were already known."}),
    "direction": Choice(
        instructions="Does the newest development in `recent_notes` make the YES outcome of `market_question` more likely or less likely?",
        criteria={"more_likely": "The development helps the YES outcome happen.",
                  "less_likely": "The development hurts the YES outcome's chances.",
                  "no_clear_effect": "The development does not clearly change the YES outcome's chances."}),
    "decided": Noul(
        instructions="Do `recent_notes` say the outcome of `market_question` has effectively been decided already?",
        criteria={"true": "The notes report a result, a withdrawal, a concession, or a final vote that settles the question.",
                  "false": "The question is still open according to the notes."}),
}


def describe_move(before: float, after: float) -> str:
    d = "rose" if after > before else "fell"
    return f"Over one day the market's YES price {d} from about {round(before * 100)} cents to about {round(after * 100)} cents."


def state_for(m: dict, before: float, after: float, notes: list[dict]) -> dict:
    rules = (m.get("rules_primary") or "")[:1500]
    return {"market_question": m.get("title") or "", "yes_outcome": m.get("yes_sub_title") or "Yes", "rules": rules,
            "price_move": describe_move(before, after),
            "recent_notes": [{"source_note": n["file"], "text": n["text"][:800]} for n in notes]}


def recent_notes(retriever, m: dict, ticker: str, T: float, k: int = 8) -> list[dict]:
    hits = retriever.search(f"{m.get('title', '')} {m.get('_series_title', '')}", "", ticker, as_of=T, k=k)
    return [{"file": c.file, "text": c.text, "as_of": c.as_of} for _, c in hits if c.as_of >= T - WINDOW_DAYS * 86400]


def decide(a: dict, move: float, has_notes: bool) -> str:
    if not has_notes:
        return "unexplained"
    if a["decided"] >= YES:
        return "decided"
    agrees = a["direction=more_likely"] if move > 0 else a["direction=less_likely"]
    if a["news"] >= YES and agrees >= 0.5:
        return "explained"
    if a["news"] <= NO:
        return "unexplained"
    return "unclear"


def _parse(resp) -> dict:
    out = {}
    for k, v in resp.answers.items():
        d = v.model_dump()
        if d["type"] == "noul":
            out[k] = float(d["noul"])
        else:
            out.update({f"{k}={o}": float(p) for o, p in d["probabilities"].items()})
    return out


async def _ask_all(items: list[dict]):
    from typesafe_sdk import AsyncTypeSafeClient
    sem = asyncio.Semaphore(8)
    async with AsyncTypeSafeClient(model=MODEL, headers=HEADERS) as client:
        async def one(it):
            async with sem:
                try:
                    r = await client.system_one(state=it["state"], questions=QUESTIONS, model=MODEL)
                    return {**it, "answers": _parse(r), "model": r.model, "qset": QSET}
                except Exception as e:   # a failed call is an error, never an answer
                    return {**it, "error": f"{type(e).__name__}: {e}", "qset": QSET}
        return await asyncio.gather(*(one(it) for it in items))


def _done() -> set:
    if not os.path.exists(CACHE):
        return set()
    return {(r["ticker"], r["T"]) for r in map(json.loads, open(CACHE, encoding="utf-8")) if r.get("qset") == QSET and "answers" in r}


def backtest():
    from forecast.retrieval import Retriever
    sp = pd.read_parquet(os.path.join(ROOT, "data_cache", "spikes.parquet"))
    sp = sp[sp["n_recent7"] > 0]
    done = _done()
    mk = load_markets(set(sp["ticker"]))
    R = Retriever(per_file_cap=2)
    items = []
    for r in sp.itertuples():
        if (r.ticker, int(r.T)) in done or r.ticker not in mk:
            continue
        m = mk[r.ticker]
        notes = recent_notes(R, m, r.ticker, r.T)
        if notes:
            items.append({"ticker": r.ticker, "T": int(r.T), "move": float(r.move),
                          "state": state_for(m, r.mid - r.move, r.mid, notes)})
    print(f"{len(items)} spikes to ask Jev about ({len(done)} cached)")
    res = asyncio.run(_ask_all(items))
    with open(CACHE, "a", encoding="utf-8") as fh:
        for r in res:
            fh.write(json.dumps(r) + "\n")
    print(f"ok {sum('answers' in r for r in res)}, errors {sum('error' in r for r in res)}")


def labels() -> pd.DataFrame:
    """jev_label per (ticker, T). Spikes with no recent notes are 'unexplained' by rule, without asking Jev."""
    sp_path = os.path.join(ROOT, "data_cache", "spikes.parquet")
    if not os.path.exists(CACHE) or not os.path.exists(sp_path):
        return pd.DataFrame(columns=["ticker", "T", "jev_label"])
    sp = pd.read_parquet(sp_path)
    asked = {(r["ticker"], r["T"]): r for r in map(json.loads, open(CACHE, encoding="utf-8"))
             if r.get("qset") == QSET and "answers" in r}
    rows = []
    for r in sp.itertuples():
        key = (r.ticker, int(r.T))
        if r.n_recent7 == 0:
            rows.append({"ticker": r.ticker, "T": int(r.T), "jev_label": "unexplained"})
        elif key in asked:
            rows.append({"ticker": r.ticker, "T": int(r.T), "jev_label": decide(asked[key]["answers"], r.move, True)})
    return pd.DataFrame(rows)


def live(jump: float = 0.10, vol_mult: float = 2.0):
    """Open markets covered by the knowledge notes: is there a spike at the latest daily close, and what would we do?"""
    from forecast.kalshi_data import _get
    from forecast.ledger import covered_events, open_markets
    from forecast.retrieval import Retriever
    from forecast.snapshots import parse_candles
    now = int(datetime.now(timezone.utc).timestamp())
    R = Retriever(per_file_cap=2)
    items, quotes = [], {}
    for m in open_markets(covered_events()):
        d = _get(f"/series/{m['series']}/markets/{m['ticker']}/candlesticks",
                 {"start_ts": now - 30 * 86400, "end_ts": now, "period_interval": 1440})
        c = parse_candles((d or {}).get("candlesticks") or [])
        if len(c) < 3:
            continue
        c = c[(c["bid"] > 0) & (c["ask"] < 1)]
        if len(c) < 3:
            continue
        mid = ((c["bid"] + c["ask"]) / 2).to_numpy()
        mv = mid[-1] - mid[-2]
        base = np.median(c["vol"].to_numpy()[-16:-1])
        if abs(mv) < jump or c["vol"].iloc[-1] < max(vol_mult * base, 10):
            continue
        full = (_get(f"/markets/{m['ticker']}") or {}).get("market") or {}
        full["_series_title"] = m.get("series_title")
        notes = recent_notes(R, full, m["ticker"], now)
        quotes[m["ticker"]] = m
        items.append({"ticker": m["ticker"], "T": now, "move": float(mv), "has_notes": bool(notes),
                      "state": state_for(full, mid[-2], mid[-1], notes)})
    print(f"{len(items)} spikes on covered open markets")
    res = asyncio.run(_ask_all([i for i in items if i["has_notes"]])) if any(i["has_notes"] for i in items) else []
    by = {r["ticker"]: r for r in res}
    props = []
    for it in items:
        r = by.get(it["ticker"])
        if it["has_notes"] and (r is None or "answers" not in r):
            print(it["ticker"], "Jev call failed:", (r or {}).get("error"))
            continue
        lab = decide(r["answers"], it["move"], True) if it["has_notes"] else "unexplained"
        q = quotes[it["ticker"]]
        if lab != "unexplained":
            props.append({"ticker": it["ticker"], "label": lab, "action": "none"})
            continue
        # Fade with a resting limit order at the spiked side's touch (S5/J1 in docs/spike_fade.md).
        if it["move"] > 0:
            props.append({"ticker": it["ticker"], "label": lab, "action": "SELL YES (= buy NO) limit",
                          "yes_limit_price": q["ask"], "no_cost": round(1 - q["ask"], 2)})
        else:
            props.append({"ticker": it["ticker"], "label": lab, "action": "BUY YES limit", "yes_limit_price": q["bid"]})
    out = os.path.join(ROOT, "data_cache", "spike_proposals.json")
    json.dump({"ts": now, "proposals": props}, open(out, "w"), indent=1)
    for p in props:
        print(p)
    print("PROPOSALS ONLY - nothing was sent to Kalshi.")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
    if not os.environ.get("TYPESAFE_API_KEY"):
        sys.exit("TYPESAFE_API_KEY is not set (add it to the git-ignored .env)")
    {"backtest": backtest, "live": live}[sys.argv[1]]()
