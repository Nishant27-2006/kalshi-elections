"""Ask Jev the questions in jev_questions.py about each market's contract text.

    python -m forecast.jev_features probe [N]   # N sample markets, prints answers (a few cents)
    python -m forecast.jev_features run         # every market in snapshots.parquet, cached
    python -m forecast.jev_features live        # open markets in data_cache/ledger_universe.json

Needs TYPESAFE_API_KEY in the environment. Kalshi data comes from the local
cache only; nothing is sent to Kalshi. Each market is asked once per
QSET_VERSION and cached in data_cache/jev_features.jsonl together with the
exact state sent, the model ID that answered and token usage, so any answer
can be re-run. A failed call is logged as an error and never treated as an
answer.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import numpy as np
import pandas as pd

from forecast.jev_questions import (FEATURES_CHOICE, FEATURES_NOUL, FEATURES_SCORE, MODEL, QSET_VERSION,
                                    PROBE_NOULS, WORLD_NOULS, questions)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data_cache", "jev_features.jsonl")
ERRORS = os.path.join(ROOT, "data_cache", "jev_errors.jsonl")
MARKETS = os.path.join(ROOT, "data_cache", "markets.jsonl")
CONCURRENCY = 8
# Image inputs and Box questions are "danger zone" features (docs.typesafe.ai/images); harmless on text-only calls.
HEADERS = {"TypeSafe-Danger-Zone-Images": "true"}
RULES_MAX = 2500   # characters; long rules are mostly boilerplate after this

# Fields that reveal how a market settled. Never sent.
_FORBIDDEN = ("result", "expiration_value", "settlement_value_dollars", "settlement_ts", "last_price_dollars")


def state_for(m: dict) -> dict:
    rules = (m.get("rules_primary") or "").strip()
    sec = (m.get("rules_secondary") or "").strip()
    if sec:
        rules = rules + "\n\n" + sec
    return {"market_question": m.get("title") or "",
            "yes_outcome": m.get("yes_sub_title") or m.get("subtitle") or "Yes",
            "series": m.get("_series_title") or m.get("series_title") or "",
            "rules": rules[:RULES_MAX]}


def load_markets(tickers: set[str] | None = None) -> dict[str, dict]:
    out = {}
    with open(MARKETS, encoding="utf-8") as fh:
        for line in fh:
            m = json.loads(line)
            t = m.get("ticker")
            if t and (tickers is None or t in tickers):
                out[t] = m
    return out


def cached() -> dict[str, dict]:
    out = {}
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                if r.get("qset") == QSET_VERSION:
                    out[r["ticker"]] = r
    return out


def _parse(resp) -> dict:
    a = {}
    for k, v in resp.answers.items():
        d = v.model_dump() if hasattr(v, "model_dump") else dict(v)
        if d["type"] == "noul":
            a[k] = float(d["noul"])
        elif d["type"] == "score":
            p = [float(x) for x in d["probabilities"]] if isinstance(d["probabilities"], list) \
                else [float(x) for x in d["probabilities"].values()]
            a[k] = float(np.dot(np.arange(len(p)), p) / max(len(p) - 1, 1))   # expected level in [0, 1]
            a[k + "__conf"] = d.get("confidence")
        elif d["type"] == "choice":
            for opt, pr in d["probabilities"].items():
                a[f"{k}={opt}"] = float(pr)
            a[k + "__conf"] = d.get("confidence")
    return a


async def _ask(client, sem, ticker, state, q, fh_ok, fh_err):
    async with sem:
        for f in _FORBIDDEN:
            assert f not in state
        try:
            r = await client.system_one(state=state, questions=q, model=MODEL)
        except Exception as e:   # an error is an error, never an answer
            fh_err.write(json.dumps({"ticker": ticker, "error": f"{type(e).__name__}: {e}"}) + "\n")
            fh_err.flush()
            return False
        row = {"ticker": ticker, "qset": QSET_VERSION, "model": r.model, "state": state,
               "answers": _parse(r), "usage": r.usage.model_dump() if r.usage else None}
        fh_ok.write(json.dumps(row) + "\n")
        fh_ok.flush()
        return True


async def run_async(markets: dict[str, dict], limit: int | None = None):
    from typesafe_sdk import AsyncTypeSafeClient
    done = cached()
    todo = [t for t in markets if t not in done]
    if limit:
        todo = todo[:limit]
    print(f"{len(done)} cached, {len(todo)} to ask (model {MODEL}, qset {QSET_VERSION})", flush=True)
    q = questions()
    sem = asyncio.Semaphore(CONCURRENCY)
    ok = 0
    async with AsyncTypeSafeClient(model=MODEL, headers=HEADERS) as client:
        with open(CACHE, "a", encoding="utf-8") as fh_ok, open(ERRORS, "a", encoding="utf-8") as fh_err:
            tasks = [_ask(client, sem, t, state_for(markets[t]), q, fh_ok, fh_err) for t in todo]
            for i, fut in enumerate(asyncio.as_completed(tasks), 1):
                ok += bool(await fut)
                if i % 250 == 0:
                    print(f"  {i}/{len(todo)} ({ok} ok)", flush=True)
    print(f"done: {ok}/{len(todo)} ok; errors in {ERRORS}")


def feature_columns(include_world: bool = False) -> list[str]:
    cols = list(FEATURES_NOUL) + list(FEATURES_SCORE)
    for k, opts in FEATURES_CHOICE.items():
        cols += [f"{k}={o}" for o in opts]
    if include_world:
        cols += list(WORLD_NOULS)
    return cols


def table(include_world: bool = False) -> pd.DataFrame:
    """One row per ticker: feature columns plus the probe (kept separate by name)."""
    rows = []
    for t, r in cached().items():
        a = r["answers"]
        row = {"ticker": t, "jev_model": r["model"]}
        for c in feature_columns(include_world) + list(PROBE_NOULS):
            row["jev_" + c] = a.get(c, np.nan)
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))   # TYPESAFE_API_KEY lives in the git-ignored .env
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if not os.environ.get("TYPESAFE_API_KEY"):
        sys.exit("TYPESAFE_API_KEY is not set")
    if cmd == "probe":
        from forecast.snapshots import load
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
        tick = load()["ticker"].drop_duplicates().sample(n, random_state=7)
        mk = load_markets(set(tick))
        asyncio.run(run_async(mk, limit=n))
        c = cached()
        for t in tick:
            if t in c:
                print(t, "|", c[t]["state"]["market_question"])
                print("   ", {k: round(v, 2) for k, v in c[t]["answers"].items() if isinstance(v, float)})
    elif cmd == "run":
        from forecast.snapshots import load
        mk = load_markets(set(load()["ticker"].unique()))
        asyncio.run(run_async(mk))
    elif cmd == "live":
        uni = json.load(open(os.path.join(ROOT, "data_cache", "ledger_universe.json"), encoding="utf-8"))
        mk = {}
        from forecast.kalshi_data import _get
        for u in uni:
            m = (_get(f"/markets/{u['ticker']}") or {}).get("market")
            if m:
                m["_series_title"] = u.get("series_title")
                mk[m["ticker"]] = m
        asyncio.run(run_async(mk))


if __name__ == "__main__":
    main()
