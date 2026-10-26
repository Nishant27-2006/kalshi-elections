"""Should you sell into a political price spike? Backtest on resolved markets.

A spike is found by code, from daily candles, using only data up to the end of
day d: the mid moved at least `jump` in one day on volume at least `vol_mult`
times its median over the prior 14 days. The decision is made at day d's
close; nothing after d is used except to settle or exit the trade.

Variants are fixed here BEFORE the held-out set is looked at, and the split is
the same as every other backtest (forecast/backtest.split: the most recent 30%
of events by close, scored only on spikes at or after the cutoff).

    python -m forecast.spike_fade          # writes docs/spike_fade.md

Jev's role (forecast/spike_jev.py) comes after: it reads the knowledge notes
dated before the spike and says whether they explain it. That can only help if
the plain fade has something to condition on, which this file measures.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from forecast.backtest import event_bootstrap, split
from forecast.kalshi_data import _candle_path
from forecast.snapshots import load, parse_candles

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "spike_fade.md")


def fee(p):
    return 0.07 * p * (1 - p)


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return np.nan


def daily(ticker: str) -> pd.DataFrame | None:
    p = _candle_path(ticker)
    if not os.path.exists(p):
        return None
    d = parse_candles(json.load(open(p, encoding="utf-8"))).rename(columns={"t": "ts"})
    if d.empty:
        return None
    d["two_sided"] = (d["bid"] > 0) & (d["ask"] < 1) & (d["ask"] > d["bid"])
    d["mid"] = np.where(d["two_sided"], (d["bid"] + d["ask"]) / 2, np.nan)
    return d


@dataclass
class Variant:
    name: str
    side: str = "fade"            # fade = bet against the move; follow = bet with it
    jump: float = 0.10
    vol_mult: float | None = 2.0  # None = no volume condition
    exit_days: int | None = None  # None = hold to settlement
    execution: str = "taker"      # taker | maker
    max_post_mid: float | None = None
    min_post_mid: float | None = None
    kg: str | None = None         # None | "none" (no knowledge note dated in the 7 days before) | "some"
    jev: str | None = None        # None | "unexplained" | "explained" (forecast/spike_jev.py decision table)
    notes: str = ""


VARIANTS = [
    Variant("S0 fade, taker, hold to settlement", notes="Base case."),
    Variant("S1 follow (momentum), taker, hold", side="follow", notes="The opposite bet."),
    Variant("S2 fade, exit after 7 days", exit_days=7, notes="Pays the spread and fee twice."),
    Variant("S3 fade, 15c spikes only", jump=0.15),
    Variant("S4 fade, no volume condition", vol_mult=None),
    Variant("S5 fade, maker limit order at the spike close", execution="maker",
            notes="Rest a sell at the spiked side's ask; filled only if the next day trades through it. No maker fee on political series."),
    Variant("S6 fade longshot spikes (post-spike mid <= 30c)", max_post_mid=0.30),
    Variant("S7 fade favourite spikes (post-spike mid >= 70c)", min_post_mid=0.70),
    # Added after S0-S7 were run, before either was evaluated: does the knowledge graph separate spikes?
    Variant("S8 maker fade, no knowledge note in prior 7 days", execution="maker", kg="none",
            notes="Code only: retrieval finds no note dated in the week before the spike."),
    Variant("S9 maker fade, knowledge note(s) in prior 7 days", execution="maker", kg="some",
            notes="Code only: at least one retrieved note is dated in the week before (may or may not be relevant)."),
    Variant("J1 maker fade, Jev says notes do NOT explain the spike", execution="maker", jev="unexplained",
            notes="Needs data_cache/spike_jev.jsonl."),
    Variant("J2 follow, taker, Jev says notes explain the spike", side="follow", jev="explained",
            notes="Needs data_cache/spike_jev.jsonl."),
]


def spikes(meta: pd.DataFrame, jump: float, vol_mult: float | None) -> pd.DataFrame:
    out = []
    for r in meta.itertuples():
        d = daily(r.ticker)
        if d is None or len(d) < 5:
            continue
        mid, vol = d["mid"].to_numpy(), d["vol"].to_numpy()
        for i in range(1, len(d) - 3):          # >= 3 more days of trading after the spike
            if np.isnan(mid[i]) or np.isnan(mid[i - 1]):
                continue
            mv = mid[i] - mid[i - 1]
            if abs(mv) < jump or d["ask"][i] - d["bid"][i] > 0.10 or not 0.05 <= mid[i] <= 0.95:
                continue
            if vol_mult is not None:
                base = np.median(vol[max(0, i - 14):i]) if i > 0 else 0
                if vol[i] < max(vol_mult * base, 10):
                    continue
            out.append({"ticker": r.ticker, "event": r.event, "outcome": r.outcome, "T": int(d["ts"][i]),
                        "i": i, "move": mv, "mid": mid[i], "bid": d["bid"][i], "ask": d["ask"][i]})
            break                                # first qualifying spike per market only
    return pd.DataFrame(out)


def pnl(s: pd.Series, v: Variant) -> float | None:
    up = s["move"] > 0
    buy_yes = (not up) if v.side == "fade" else up
    d = daily(s["ticker"])
    j = s["i"]
    if v.execution == "maker":
        # Selling the spiked side = buying the other side at a resting price.
        # Up-spike fade: sell YES at the ask -> long NO at cost 1 - ask. Fill needs a trade at >= ask next day.
        if buy_yes:
            px = s["bid"]
            filled = d["lo"][j + 1] <= px if not np.isnan(d["lo"][j + 1]) else False
            cost = px
        else:
            px = s["ask"]
            filled = d["hi"][j + 1] >= px if not np.isnan(d["hi"][j + 1]) else False
            cost = 1 - px
        if not filled:
            return None
    else:
        cost = s["ask"] + fee(s["ask"]) if buy_yes else (1 - s["bid"]) + fee(1 - s["bid"])
    if v.exit_days is not None and j + v.exit_days < len(d) and d["two_sided"][j + v.exit_days]:
        k = j + v.exit_days
        exit_px = d["bid"][k] if buy_yes else 1 - d["ask"][k]
        return float(exit_px - fee(exit_px) - cost)
    pay = s["outcome"] if buy_yes else 1 - s["outcome"]
    return float(pay - cost)


def evaluate(v: Variant, sp: pd.DataFrame) -> dict:
    sp = sp.copy()
    if v.max_post_mid is not None:
        sp = sp[sp["mid"] <= v.max_post_mid]
    if v.min_post_mid is not None:
        sp = sp[sp["mid"] >= v.min_post_mid]
    if v.kg is not None:
        sp = sp[(sp["n_recent7"] > 0) == (v.kg == "some")]
    if v.jev is not None:
        sp = sp[sp["jev_label"] == v.jev]
    sp["pnl"] = [pnl(r, v) for _, r in sp.iterrows()]
    tr = sp.dropna(subset=["pnl"])
    if len(tr) < 5:
        return {"n": len(tr)}
    ci = event_bootstrap(tr, lambda d: d["pnl"].mean(), n=1000)
    return {"n": int(len(tr)), "events": int(tr["event"].nunique()), "pnl": round(float(tr["pnl"].sum()), 2),
            "per_trade": round(float(tr["pnl"].mean()), 4), "ci95": [round(ci[0], 4), round(ci[1], 4)],
            "hit": round(float((tr["pnl"] > 0).mean()), 3)}


def main():
    snap = load()
    train, test, cut = split(snap)
    meta = snap.groupby("ticker").agg(event=("event", "first"), outcome=("outcome", "first"),
                                      event_close=("event_close", "max")).reset_index()
    test_events = set(test["event"])
    cache = {}
    rows = []
    for v in VARIANTS:
        key = (v.jump, v.vol_mult)
        if key not in cache:
            cache[key] = spikes(meta, v.jump, v.vol_mult)
            print(f"spikes jump={v.jump} vol={v.vol_mult}: {len(cache[key])}", flush=True)
        sp = cache[key]
        if (v.kg or v.jev) and "n_recent7" not in sp:
            kg = pd.read_parquet(os.path.join(ROOT, "data_cache", "spikes.parquet"))[["ticker", "T", "n_recent7"]]
            sp = cache[key] = sp.merge(kg, on=["ticker", "T"], how="left")
        if v.jev:
            from forecast.spike_jev import labels
            lab = labels()
            if lab.empty:
                rows.append({"variant": v.name, "train": {"n": 0}, "test": {"n": 0}, "notes": v.notes + " NOT RUN: no Jev answers yet."})
                continue
            sp = sp.drop(columns=["jev_label"], errors="ignore").merge(lab, on=["ticker", "T"], how="left")
        tr_sp = sp[~sp["event"].isin(test_events)]
        te_sp = sp[sp["event"].isin(test_events) & (sp["T"] >= cut)]
        r = {"variant": v.name, "train": evaluate(v, tr_sp), "test": evaluate(v, te_sp), "notes": v.notes}
        rows.append(r)
        print(json.dumps(r), flush=True)

    def cell(x):
        if x.get("n", 0) < 5:
            return f"n={x.get('n', 0)} (too few)", "", ""
        return f"{x['n']} ({x['events']} ev)", f"{x['per_trade']*100:+.1f}c [{x['ci95'][0]*100:+.1f}, {x['ci95'][1]*100:+.1f}]", f"{x['hit']:.0%}"

    L = ["# Spike fade backtest", "",
         "`python -m forecast.spike_fade`. Daily candles of resolved political markets. A spike = one-day mid move "
         ">= the threshold, spread <= 10c, mid 5-95c after the move, volume >= 2x its 14-day median (unless stated), "
         "first spike per market. Decision at the spike day's close. P&L per $1 contract, net of the taker fee "
         "0.07*P*(1-P) and the spread; CI = event bootstrap. Train = events closing before the held-out cutoff; "
         "test = the locked most recent 30% (spikes on or after the cutoff). Variants were fixed before the test "
         "set was read.", "",
         "| variant | train trades | train P&L/trade [CI95] | train hit | TEST trades | TEST P&L/trade [CI95] | TEST hit | notes |",
         "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        a, b = cell(r["train"]), cell(r["test"])
        L.append(f"| {r['variant']} | {a[0]} | {a[1]} | {a[2]} | {b[0]} | {b[1]} | {b[2]} | {r['notes']} |")
    with open(DOC, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    json.dump(rows, open(os.path.join(ROOT, "data_cache", "spike_fade.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
