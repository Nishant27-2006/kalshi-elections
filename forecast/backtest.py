"""Backtest forecasting strategies on resolved Kalshi political markets.

Protocol (fixed before any result was seen):
- Split by EVENT close time. The most recent 30% of events form the test set.
  Test snapshots must also have T >= the last train event's close, so no model
  is ever fit on an outcome that was unknown at its decision time.
- Every estimator and every tuned knob is fit on train snapshots only (tuning
  uses a time-ordered validation tail inside train). Test is scored once per
  run and reported whatever it says.
- Brier is market-weighted: each market counts once however many weekly
  snapshots it has.
- P&L: one entry per market at the first snapshot that triggers, held to
  settlement, 1 contract. Taker pays the ask (YES) or 1-bid (NO) plus the
  fee in force at T. Settlement carries no fee.
- Confidence intervals bootstrap by EVENT, because legs of one event are
  not independent.
"""
from __future__ import annotations

import dataclasses
import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "data_cache", "backtest_runs.jsonl")
TEST_FRACTION = 0.30
MAKER_FEE_START = datetime(2025, 4, 1, tzinfo=timezone.utc).timestamp()


# --- costs ---------------------------------------------------------------------

def taker_fee(p, rate=0.07):
    return rate * p * (1 - p)


def maker_fee(p, T, rate=0.0):
    """Political series checked on the live API (KXPRESPARTY, CONTROLH, CONTROLS,
    KXHOUSE) are fee_type=quadratic with no maker component, so resting orders
    pay nothing (knowledge/markets/how-prediction-markets-work.md). Series that
    do carry maker fees pay 0.0175*P*(1-P), switched on from 2025-10-04 at the
    earliest; pass rate=0.0175 to stress-test."""
    return np.where(T >= MAKER_FEE_START, rate * p * (1 - p), 0.0)


# --- split -----------------------------------------------------------------------

def split(snap: pd.DataFrame, test_fraction: float = TEST_FRACTION):
    ev = snap.groupby("event")["event_close"].max().sort_values()
    n_test = int(math.ceil(len(ev) * test_fraction))
    test_events = set(ev.index[-n_test:])
    train = snap[~snap["event"].isin(test_events)].copy()
    cutoff = float(ev[~ev.index.isin(test_events)].max())
    test = snap[snap["event"].isin(test_events) & (snap["T"] >= cutoff)].copy()
    return train, test, cutoff


def inner_split(train: pd.DataFrame, frac: float = 0.25):
    """Time-ordered validation tail inside train, same rule as the outer split."""
    return split(train, frac)


# --- metrics ---------------------------------------------------------------------

def _w(df):
    return 1.0 / df.groupby("ticker")["ticker"].transform("count")


def brier(p, y, w):
    return float(np.sum(w * (p - y) ** 2) / np.sum(w))


def calibration_table(p, y, w, edges=(0, .05, .1, .2, .3, .4, .5, .6, .7, .8, .9, .95, 1.0001)):
    rows = []
    b = np.digitize(p, edges) - 1
    for i in range(len(edges) - 1):
        m = b == i
        if m.sum() == 0:
            continue
        ww = w[m]
        rows.append({"bucket": f"{edges[i]:.2f}-{min(edges[i+1],1):.2f}", "n_snap": int(m.sum()),
                     "mean_pred": round(float(np.sum(ww * p[m]) / ww.sum()), 4),
                     "realized": round(float(np.sum(ww * y[m]) / ww.sum()), 4)})
    return rows


def event_bootstrap(df: pd.DataFrame, stat: Callable[[pd.DataFrame], float], n=1000, seed=0):
    rng = np.random.default_rng(seed)
    events = df["event"].unique()
    groups = {e: g for e, g in df.groupby("event")}
    vals = []
    for _ in range(n):
        pick = rng.choice(events, size=len(events), replace=True)
        vals.append(stat(pd.concat([groups[e] for e in pick], ignore_index=True)))
    lo, hi = np.nanpercentile(vals, [2.5, 97.5])
    return float(lo), float(hi)


# --- strategy ----------------------------------------------------------------------

@dataclass
class Config:
    name: str
    estimator: str = "platt_archetype"   # key into forecast.estimators.ESTIMATORS
    est_params: dict = field(default_factory=dict)
    min_edge: float = 0.05               # net of fee, in dollars per contract
    max_spread: float = 0.10
    min_price: float = 0.03              # old plan: refuse sub-3c positions
    max_price: float = 0.97
    execution: str = "taker"             # taker | maker
    sides: str = "both"                  # both | yes | no
    edge_space: str = "prob"             # prob | logit
    filter: str | None = None            # key into forecast.estimators.FILTERS
    fee_rate: float = 0.07
    notes: str = ""


def _entry(df: pd.DataFrame, p: np.ndarray, cfg: Config) -> pd.DataFrame:
    """Per snapshot: which side (if any) clears min_edge net of costs."""
    d = df.copy()
    d["p_hat"] = p
    if cfg.execution == "taker":
        yes_px, no_px = d["ask"], 1 - d["bid"]
        yes_fee, no_fee = taker_fee(yes_px, cfg.fee_rate), taker_fee(no_px, cfg.fee_rate)
        d["yes_fill"] = True
        d["no_fill"] = True
    else:  # join the best bid on our side; fill only if price traded THROUGH it within a week
        yes_px, no_px = d["bid"], 1 - d["ask"]
        yes_fee, no_fee = maker_fee(yes_px, d["T"]), maker_fee(no_px, d["T"])
        d["yes_fill"] = d["fwd_lo"] < d["bid"]
        d["no_fill"] = d["fwd_hi"] > d["ask"]
    d["yes_cost"], d["no_cost"] = yes_px + yes_fee, no_px + no_fee
    if cfg.edge_space == "logit":
        lg = lambda x: np.log(np.clip(x, 1e-4, 1 - 1e-4) / (1 - np.clip(x, 1e-4, 1 - 1e-4)))
        d["yes_edge"] = lg(d["p_hat"]) - lg(d["yes_cost"])
        d["no_edge"] = lg(1 - d["p_hat"]) - lg(d["no_cost"])
    else:
        d["yes_edge"] = d["p_hat"] - d["yes_cost"]
        d["no_edge"] = (1 - d["p_hat"]) - d["no_cost"]
    ok = (d["spread"] <= cfg.max_spread) & (d["stale_days"] <= 3)
    yes_ok = ok & (yes_px >= cfg.min_price) & (yes_px <= cfg.max_price) & (d["yes_edge"] > cfg.min_edge)
    no_ok = ok & (no_px >= cfg.min_price) & (no_px <= cfg.max_price) & (d["no_edge"] > cfg.min_edge)
    if cfg.sides == "yes":
        no_ok &= False
    if cfg.sides == "no":
        yes_ok &= False
    d["side"] = np.where(yes_ok & (d["yes_edge"] >= d["no_edge"]), "yes", np.where(no_ok, "no", ""))
    d.loc[(d["side"] == "") & yes_ok, "side"] = "yes"
    return d


def trades(df: pd.DataFrame, p: np.ndarray, cfg: Config) -> pd.DataFrame:
    d = _entry(df, p, cfg)
    d = d[d["side"] != ""].sort_values("T")
    filled = np.where(d["side"] == "yes", d["yes_fill"], d["no_fill"]).astype(bool)
    d = d[filled]
    d = d.groupby("ticker", as_index=False).first()  # first triggering snapshot, held to settlement
    cost = np.where(d["side"] == "yes", d["yes_cost"], d["no_cost"])
    payoff = np.where(d["side"] == "yes", d["outcome"], 1 - d["outcome"])
    d["cost"] = cost
    d["pnl"] = payoff - cost
    return d


def evaluate(cfg: Config, snap: pd.DataFrame, record: bool = True) -> dict:
    from forecast.estimators import ESTIMATORS, FILTERS

    train, test, cutoff = split(snap)
    if cfg.filter:
        flt = FILTERS[cfg.filter]
        train_f, test_f = flt(train, train), flt(test, train)
    else:
        train_f, test_f = train, test
    est = ESTIMATORS[cfg.estimator](**cfg.est_params)
    est.fit(train)
    out = {"name": cfg.name, "config": dataclasses.asdict(cfg),
           "split_cutoff": datetime.fromtimestamp(cutoff, timezone.utc).strftime("%Y-%m-%d"),
           "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}
    for label, part in (("train", train_f), ("test", test_f)):
        if part.empty:
            out[label] = {"n_snap": 0}
            continue
        p = np.clip(est.predict(part), 1e-4, 1 - 1e-4)
        y = part["outcome"].to_numpy()
        w = _w(part).to_numpy()
        mid = part["mid"].to_numpy()
        b_model, b_mkt = brier(p, y, w), brier(mid, y, w)
        tr = trades(part, p, cfg)
        res = {
            "n_snap": int(len(part)), "n_markets": int(part["ticker"].nunique()),
            "n_events": int(part["event"].nunique()),
            "brier_model": round(b_model, 5), "brier_market": round(b_mkt, 5),
            "brier_skill": round(1 - b_model / b_mkt, 4) if b_mkt > 0 else None,
            "n_trades": int(len(tr)),
            "pnl_total": round(float(tr["pnl"].sum()), 3) if len(tr) else 0.0,
            "pnl_per_trade": round(float(tr["pnl"].mean()), 4) if len(tr) else None,
            "return_on_cost": round(float(tr["pnl"].sum() / tr["cost"].sum()), 4) if len(tr) else None,
            "hit_rate": round(float((tr["pnl"] > 0).mean()), 3) if len(tr) else None,
            "n_trade_events": int(tr["event"].nunique()) if len(tr) else 0,
        }
        if label == "test":
            pp = pd.Series(p, index=part.index)
            sub = part.assign(_p=pp, _w=w)
            res["brier_diff_ci95"] = [round(v, 5) for v in event_bootstrap(
                sub, lambda g: brier(g["_p"].to_numpy(), g["outcome"].to_numpy(), (1 / g.groupby("ticker")["ticker"].transform("count")).to_numpy())
                - brier(g["mid"].to_numpy(), g["outcome"].to_numpy(), (1 / g.groupby("ticker")["ticker"].transform("count")).to_numpy()), n=300)]
            if len(tr) >= 5:
                res["pnl_per_trade_ci95"] = [round(v, 4) for v in event_bootstrap(tr, lambda g: g["pnl"].mean(), n=1000)]
                top = tr.groupby("event")["pnl"].sum().sort_values(ascending=False)
                res["top_event_pnl_share"] = round(float(top.iloc[0] / tr["pnl"].sum()), 3) if tr["pnl"].sum() > 0 else None
            res["calibration_model"] = calibration_table(p, y, w)
            res["calibration_market"] = calibration_table(mid, y, w)
        out[label] = res
    if record:
        os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
        with open(RESULTS, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(out) + "\n")
    return out
