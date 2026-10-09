"""Re-test leads on EARLIER periods, never touching the locked test set.

Two leads came out of the held-out test set: V18 (trade only tight books) and
the low-efficiency tercile. Leads picked by looking at a test set must be
re-tested on data that played no part in picking them. Until post-2026-10-09
settlements exist, the only such data is the earlier history inside TRAIN.

Folds: train events sorted by close and cut into N+1 equal blocks. Fold i
fits on blocks 1..i and scores block i+1, with the same rule as the outer
split (scored snapshots have T >= the last fitting event's close).

    python -m forecast.walkforward
"""
from __future__ import annotations

import dataclasses
import json
import math
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from forecast.backtest import Config, brier, event_bootstrap, split, trades
from forecast.estimators import ESTIMATORS, FILTERS
from forecast.run_backtests import B0
from forecast.snapshots import load

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data_cache", "walkforward.json")

LEADS = [
    Config(name="B0 old plan Stage A", **B0),
    Config(name="V18 tight books only (spread<=4c)", **{**B0, "filter": "liquid"}),
    Config(name="L1 low-efficiency tercile", **{**B0, "filter": "eff_low"}),
]


def _w(df):
    return (1.0 / df.groupby("ticker")["ticker"].transform("count")).to_numpy()


def folds(train: pd.DataFrame, n: int = 4):
    ev = train.groupby("event")["event_close"].max().sort_values()
    blocks = np.array_split(ev.index.to_numpy(), n + 1)
    for i in range(1, n + 1):
        fit_ev = set(np.concatenate(blocks[:i]))
        score_ev = set(blocks[i])
        cutoff = float(ev[list(fit_ev)].max())
        fit = train[train["event"].isin(fit_ev)]
        score = train[train["event"].isin(score_ev) & (train["T"] >= cutoff)]
        yield i, fit, score, cutoff


def score_fold(cfg: Config, fit, score):
    part = FILTERS[cfg.filter](score, fit) if cfg.filter else score
    est = ESTIMATORS[cfg.estimator](**cfg.est_params).fit(fit)
    if part.empty:
        return {"n_markets": 0}
    p = np.clip(est.predict(part), 1e-4, 1 - 1e-4)
    y, w = part["outcome"].to_numpy(), _w(part)
    bm, bk = brier(p, y, w), brier(part["mid"].to_numpy(), y, w)
    sub = part.assign(_p=p)
    ci = event_bootstrap(sub, lambda d: brier(d["_p"].to_numpy(), d["outcome"].to_numpy(), _w(d))
                         - brier(d["mid"].to_numpy(), d["outcome"].to_numpy(), _w(d)), n=300)
    tr = trades(part, p, cfg)
    pci = event_bootstrap(tr, lambda d: d["pnl"].mean(), n=1000) if len(tr) >= 5 else None
    return {"n_markets": int(part["ticker"].nunique()), "n_events": int(part["event"].nunique()),
            "brier_skill": round(1 - bm / bk, 4), "dBrier_ci95": [round(v, 5) for v in ci],
            "n_trades": int(len(tr)), "pnl": round(float(tr["pnl"].sum()), 3) if len(tr) else 0.0,
            "pnl_per_trade": round(float(tr["pnl"].mean()), 4) if len(tr) else None,
            "pnl_ci95": [round(v, 4) for v in pci] if pci else None}


def main():
    snap = load()
    train, _test, outer_cut = split(snap)   # the test set is discarded here, by design
    rows = []
    for i, fit, score, cut in folds(train):
        for cfg in LEADS:
            r = score_fold(cfg, fit, score)
            r.update({"fold": i, "lead": cfg.name,
                      "scored_from": datetime.fromtimestamp(cut, timezone.utc).strftime("%Y-%m-%d")})
            rows.append(r)
            print(json.dumps(r), flush=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"outer_cutoff": datetime.fromtimestamp(outer_cut, timezone.utc).strftime("%Y-%m-%d"),
                   "rows": rows}, fh, indent=1)


if __name__ == "__main__":
    main()
