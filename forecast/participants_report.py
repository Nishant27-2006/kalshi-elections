"""Workstream 4: do the sophistication submodels mean anything, and does our
edge concentrate where participants are least sophisticated?

    python -m forecast.participants_report      # writes docs/participants.md

1. Validate on TRAIN: a less sophisticated book should be worse calibrated,
   i.e. more Brier is recoverable by recalibrating its price.
2. On TEST: B0's Brier skill and P&L by tercile of the composite score and of
   each submodel separately (cut points from train).
3. Trade-size profile for a random sample of test markets, from trades
   printed BEFORE the market's first test snapshot (GET /markets/trades or
   /historical/trades): median size, share of fractional (<1 contract)
   prints, share of >=100-contract prints, and how they relate to the score.
"""
from __future__ import annotations

import os
import random
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from forecast.backtest import Config, brier, event_bootstrap, split, trades
from forecast.estimators import ESTIMATORS, PlattGlobal
from forecast.participants import Sophistication
from forecast.snapshots import load

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "participants.md")
B0 = Config(name="B0", estimator="old_plan")


def _w(df):
    return (1.0 / df.groupby("ticker")["ticker"].transform("count")).to_numpy()


def _skill_rows(test, p, groups, label):
    rows = []
    tr_all = trades(test, p, B0)
    for g in ["low", "mid", "high"]:
        m = groups == g
        part = test[m]
        if part.empty:
            continue
        pp = p[m]
        y, w = part["outcome"].to_numpy(), _w(part)
        bm, bk = brier(pp, y, w), brier(part["mid"].to_numpy(), y, w)
        sub = part.assign(_p=pp)
        ci = event_bootstrap(sub, lambda d: brier(d["_p"].to_numpy(), d["outcome"].to_numpy(), _w(d))
                             - brier(d["mid"].to_numpy(), d["outcome"].to_numpy(), _w(d)), n=300)
        tr = tr_all[tr_all["ticker"].isin(part.loc[:, "ticker"]) & tr_all.set_index(["ticker", "T"]).index.isin(
            part.set_index(["ticker", "T"]).index)]
        pci = event_bootstrap(tr, lambda d: d["pnl"].mean(), n=1000) if len(tr) >= 5 else None
        rows.append({"submodel": label, "tercile": g, "markets": part["ticker"].nunique(), "events": part["event"].nunique(),
                     "brier_market": round(bk, 5), "brier_B0": round(bm, 5), "skill": round(1 - bm / bk, 4),
                     "dBrier_ci95": [round(v, 5) for v in ci], "trades": len(tr),
                     "pnl": round(float(tr["pnl"].sum()), 3) if len(tr) else 0.0,
                     "pnl_per_trade": round(float(tr["pnl"].mean()), 4) if len(tr) else None,
                     "pnl_ci95": [round(v, 4) for v in pci] if pci else None})
    return rows


def _headroom(train, groups):
    """In-sample: Brier(mid) - Brier(Platt fit within the tercile)."""
    out = {}
    for g in ["low", "mid", "high"]:
        part = train[groups == g]
        y, w = part["outcome"].to_numpy(), _w(part)
        p = PlattGlobal().fit(part).predict(part)
        out[g] = {"markets": part["ticker"].nunique(), "brier_mid": round(brier(part["mid"].to_numpy(), y, w), 5),
                  "headroom": round(brier(part["mid"].to_numpy(), y, w) - brier(p, y, w), 5)}
    return out


def _trade_sizes(test, n=300, seed=3):
    from forecast.kalshi_data import _get
    first = test.sort_values("T").groupby("ticker", as_index=False).first()
    pick = first.sample(min(n, len(first)), random_state=seed)
    rows = []
    for _, r in pick.iterrows():
        sizes = []
        for path in ("/markets/trades", "/historical/trades"):
            d = _get(path, {"ticker": r["ticker"], "max_ts": int(r["T"]), "limit": 1000})
            sizes += [float(t.get("count_fp") or t.get("count") or 0) for t in d.get("trades") or []]
            if sizes:
                break
        if not sizes:
            continue
        s = np.array(sizes)
        rows.append({"ticker": r["ticker"], "n_prints": len(s), "median_size": float(np.median(s)),
                     "frac_share": float((s < 1).mean()), "big_share": float((s >= 100).mean()),
                     "T": r["T"]})
    return pd.DataFrame(rows)


def main():
    snap = load()
    train, test, cutoff = split(snap)
    soph = Sophistication().fit(train)
    est = ESTIMATORS["old_plan"]().fit(train)
    p = est.predict(test)

    comp_tr, comp_te = soph.tercile(train), soph.tercile(test)
    sub_tr, sub_te = soph.submodels(train), soph.submodels(test)
    rows = _skill_rows(test, p, comp_te, "composite")
    for name in sub_te.columns:
        cuts = np.nanpercentile(sub_tr[name], [100 / 3, 200 / 3])
        g = np.where(sub_te[name] <= cuts[0], "low", np.where(sub_te[name] <= cuts[1], "mid", "high"))
        rows += _skill_rows(test, p, g, name)
    res = pd.DataFrame(rows)
    head = _headroom(train, comp_tr)
    corr = sub_tr.corr().round(2)

    ts = _trade_sizes(test)
    if len(ts):
        ts = ts.merge(test.sort_values("T").groupby("ticker", as_index=False).first()[["ticker", "T", "spread", "vol_7d", "oi", "ac1", "reversal", "stale_days", "traded_days_30"]], on=["ticker", "T"])
        ts["composite"] = soph.score(ts)
        ts_corr = ts[["composite", "median_size", "frac_share", "big_share"]].corr(method="spearman").round(2)

    L = ["# Participant sophistication — submodels and where the edge sits", "",
         f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by `python -m forecast.participants_report`. "
         f"Same split as docs/backtests.md (cutoff {datetime.fromtimestamp(cutoff, timezone.utc).date()}); cut points and z-scores fit on TRAIN.", "",
         "## Submodels (all observable at decision time T)", "",
         "- **liquidity** = z(log 7-day volume) + z(log open interest) − z(spread)",
         "- **efficiency** = −z(|lag-1 autocorrelation of daily mid changes, last 30d|) − z(share of moves that reverse next day)",
         "  — a book where moves stick is pricing information; one where moves bounce back is noise or overreaction",
         "- **activity** = z(log days traded in last 30) − z(days since the last candle)",
         "- **composite** = mean of the three (each re-standardised). Depth is NOT in the score: there is no historical order-book",
         "  depth on the API, only current books, and using today's depth for a 2025 snapshot would leak.", "",
         "Correlation between submodels (train snapshots):", "", "| | " + " | ".join(corr.columns) + " |", "|---" * (len(corr.columns) + 1) + "|"]
    for i, r in corr.iterrows():
        L.append(f"| {i} | " + " | ".join(str(v) for v in r.values) + " |")
    L += ["", "## 1. Validation on train: is a low-score book worse calibrated?", "",
          "Headroom = Brier of the mid minus Brier after a Platt recalibration fit inside that tercile (in-sample, so an upper bound).", "",
          "| composite tercile | markets | Brier of mid | recalibration headroom |", "|---|---|---|---|"]
    for g, v in head.items():
        L.append(f"| {g} | {v['markets']} | {v['brier_mid']} | {v['headroom']} |")
    L += ["", "## 2. Held-out test: B0 (old-plan estimator) by tercile", "",
          "| submodel | tercile | markets | events | Brier mkt | Brier B0 | skill | ΔBrier CI95 | trades | P&L $ | P&L/trade | P&L/trade CI95 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in res.iterrows():
        L.append(f"| {r.submodel} | {r.tercile} | {r.markets} | {r.events} | {r.brier_market} | {r.brier_B0} | {r.skill:+.4f} | "
                 f"{r.dBrier_ci95} | {r.trades} | {r.pnl} | {r.pnl_per_trade} | {r.pnl_ci95} |")
    if len(ts):
        L += ["", f"## 3. Trade sizes ({len(ts)} random test markets, prints before the first test snapshot)", "",
              f"- median print size: median across markets {ts.median_size.median():.2f} contracts",
              f"- share of fractional (<1 contract) prints: median {ts.frac_share.median():.2f}",
              f"- share of >=100-contract prints: median {ts.big_share.median():.2f}", "",
              "Spearman correlation with the composite score:", "",
              "| | composite | median_size | frac_share | big_share |", "|---|---|---|---|---|"]
        for i, r in ts_corr.iterrows():
            L.append(f"| {i} | " + " | ".join(str(v) for v in r.values) + " |")
    with open(DOC, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    res.to_csv(os.path.join(ROOT, "data_cache", "participants_terciles.csv"), index=False)
    if len(ts):
        ts.to_csv(os.path.join(ROOT, "data_cache", "trade_sizes_sample.csv"), index=False)
    print(res[["submodel", "tercile", "markets", "skill", "dBrier_ci95", "trades", "pnl", "pnl_per_trade", "pnl_ci95"]].to_string(index=False))
    print(head)


if __name__ == "__main__":
    main()
