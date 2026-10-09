"""Holm and Benjamini-Hochberg across every held-out test we looked at.

The run log stores event-bootstrap 95% CIs, not p-values. Each p-value is
recovered with a normal approximation: se = (hi - lo) / 3.92, z = est / se,
two-sided p. Bootstrap CIs on P&L are skewed, so these p-values are
approximate. Two families are corrected separately:
  Brier: model minus market Brier (negative = model better)
  P&L:   mean P&L per trade (positive = profitable)
Members: the 26 full-data held-out runs (latest log entry per name) plus the
12 sophistication tercile cuts from docs/participants.md. Walk-forward folds
are a separate robustness check and are not in the families.

    python -m forecast.multiple_testing
"""
from __future__ import annotations

import json
import math
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def p_from_ci(est, ci):
    if est is None or not ci or ci[1] == ci[0]:
        return None
    se = (ci[1] - ci[0]) / 3.92
    z = est / se
    return math.erfc(abs(z) / math.sqrt(2))


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    m, out, run = len(ps), [None] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * ps[i]))
        out[i] = run
    return out


def bh(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i], reverse=True)
    m, out, run = len(ps), [None] * len(ps), 1.0
    for k, i in enumerate(order):
        rank = m - k
        run = min(run, ps[i] * m / rank)
        out[i] = min(1.0, run)
    return out


def collect():
    runs = {}
    with open(os.path.join(ROOT, "data_cache", "backtest_runs.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            runs[r["name"]] = r
    brier, pnl = [], []
    for name, r in runs.items():
        t = r["test"]
        d = (t["brier_model"] - t["brier_market"]) if t.get("brier_model") is not None else None
        p = p_from_ci(d, t.get("brier_diff_ci95"))
        if p is not None:
            brier.append({"test": name, "est": round(d, 5), "ci": t["brier_diff_ci95"], "p": p})
        p = p_from_ci(t.get("pnl_per_trade"), t.get("pnl_per_trade_ci95"))
        if p is not None:
            pnl.append({"test": name, "est": t["pnl_per_trade"], "ci": t["pnl_per_trade_ci95"], "p": p})
    terc = pd.read_csv(os.path.join(ROOT, "data_cache", "participants_terciles.csv"))
    for _, r in terc.iterrows():
        label = f"tercile {r.submodel}/{r.tercile}"
        ci = json.loads(r.dBrier_ci95)
        d = r.brier_B0 - r.brier_market
        p = p_from_ci(d, ci)
        if p is not None:
            brier.append({"test": label, "est": round(d, 5), "ci": ci, "p": p})
        if isinstance(r.pnl_ci95, str):
            ci = json.loads(r.pnl_ci95)
            p = p_from_ci(r.pnl_per_trade, ci)
            if p is not None:
                pnl.append({"test": label, "est": r.pnl_per_trade, "ci": ci, "p": p})
    return brier, pnl


def table(rows, title):
    ps = [r["p"] for r in rows]
    for r, h, b in zip(rows, holm(ps), bh(ps)):
        r["holm"], r["bh"] = h, b
    rows.sort(key=lambda r: r["p"])
    L = [f"### {title} ({len(rows)} tests)", "",
         "| test | estimate | CI95 | p (approx) | Holm-adjusted | BH-adjusted | survives Holm 5%? | survives BH 5%? |",
         "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['test']} | {r['est']} | {r['ci']} | {r['p']:.4f} | {r['holm']:.4f} | {r['bh']:.4f} | "
                 f"{'yes' if r['holm'] < 0.05 else 'no'} | {'yes' if r['bh'] < 0.05 else 'no'} |")
    return L, sum(r["holm"] < 0.05 for r in rows), sum(r["bh"] < 0.05 for r in rows)


def main():
    brier, pnl = collect()
    Lb, hb, bb = table(brier, "Brier family: model minus market (negative = model better)")
    Lp, hp, bp = table(pnl, "P&L family: mean P&L per trade")
    L = ["## Multiple-comparisons correction", "",
         "`python -m forecast.multiple_testing`. p-values are approximated from the event-bootstrap CIs (normal "
         "approximation; P&L CIs are skewed, so treat as rough). Families are corrected separately.", "",
         f"- Brier: {hb} of {len(brier)} survive Holm, {bb} survive BH (5%).",
         f"- P&L: {hp} of {len(pnl)} survive Holm, {bp} survive BH (5%).", ""] + Lb + [""] + Lp
    out = os.path.join(ROOT, "docs", "multiple_testing.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L[:7]))


if __name__ == "__main__":
    main()
