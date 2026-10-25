"""Does Jev already know how resolved markets turned out?

The probe question asks Jev outright whether each market's YES outcome
happened. Jev was trained on text that may describe these outcomes, so on
resolved markets a strong probe means world knowledge leaks into backtests.
The TEXT features ask only what the contract says, but a model that knows the
answer could still lean on it, so this check gates how far the backtest can
be trusted.

Reported by close date (the leak should shrink for markets that closed after
Jev's training data ends) and against the market price a week before close:
  AUC(probe)        how well the probe alone sorts YES from NO
  AUC(mid)          the same for the market price
  dBrier            Brier of a logistic(mid, probe) fit minus Brier of mid, 5-fold by event

    python -m forecast.jev_contamination
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from forecast.estimators import logit
from forecast.jev_features import table
from forecast.snapshots import load

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def last_snap(snap):
    """Latest snapshot per market that is at least 7 days before the event closed."""
    s = snap[snap["T"] <= snap["event_close"] - 7 * 86400]
    return s.sort_values("T").groupby("ticker").tail(1)


def stats(d):
    y, mid, pr = d["outcome"].to_numpy(), d["mid"].to_numpy(), d["jev_probe_happened"].to_numpy()
    if len(np.unique(y)) < 2 or len(d) < 40:
        return None
    X = np.column_stack([logit(mid), logit(pr)])
    p = np.zeros(len(d))
    for tr, te in GroupKFold(5).split(X, y, d["event"]):
        p[te] = LogisticRegression(max_iter=1000).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    return {"n": len(d), "AUC_probe": round(roc_auc_score(y, pr), 3), "AUC_mid": round(roc_auc_score(y, mid), 3),
            "dBrier": round(float(np.mean((p - y) ** 2) - np.mean((mid - y) ** 2)), 5)}


def main():
    d = last_snap(load()).merge(table(), on="ticker").dropna(subset=["jev_probe_happened"])
    d["close_q"] = pd.to_datetime(d["event_close"], unit="s").dt.to_period("Q").astype(str)
    rows = [{"period": "all", **(stats(d) or {})}]
    for q, g in d.groupby("close_q"):
        s = stats(g)
        if s:
            rows.append({"period": q, **s})
    out = pd.DataFrame(rows)
    L = ["## Jev contamination probe", "",
         "`python -m forecast.jev_contamination`. The probe asks Jev whether each resolved market's YES outcome "
         "happened. Negative dBrier means price + probe beats the price alone, i.e. Jev knows something the market "
         "did not a week before close; on resolved markets that is most likely memorised outcomes, not foresight.", "",
         out.to_markdown(index=False)]
    with open(os.path.join(ROOT, "docs", "jev_contamination.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
