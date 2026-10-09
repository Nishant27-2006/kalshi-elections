"""Run the backtest suite and regenerate docs/backtests.md from the run log.

    python -m forecast.run_backtests            # run every config not yet logged
    python -m forecast.run_backtests --report   # only rebuild the markdown

Each variation changes ONE thing relative to the old-plan baseline (B0) and
is judged against two bars on the held-out test set:
  - forecast: Brier below the market's (and the event-bootstrap CI of the
    difference excludes zero for a "clear" win)
  - money: P&L net of fee and spread above zero, the do-nothing null
"""
from __future__ import annotations

import argparse
import json
import os

from forecast.backtest import RESULTS, Config, evaluate
from forecast.snapshots import load

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "backtests.md")

B0 = dict(estimator="old_plan", min_edge=0.05, max_spread=0.10, min_price=0.03, max_price=0.97)

CONFIGS = [
    Config(name="B0 old plan Stage A", **B0,
           notes="Archetype base rate + market-price slope (fit on train); trade when edge > 5c net; spread <= 10c; refuse <3c."),
    Config(name="V01 market price only", **{**B0, "estimator": "market"},
           notes="Sanity row: the market as its own forecast. Brier skill must be 0 and no trades."),
    Config(name="V02 global Platt (no archetype)", **{**B0, "estimator": "platt"},
           notes="Drop the archetype intercepts; one recalibration curve for all markets."),
    Config(name="V03 archetype slope too", **{**B0, "estimator": "platt_arch_slope"},
           notes="Archetype-specific slope as well as intercept."),
    Config(name="V04 isotonic recalibration", **{**B0, "estimator": "isotonic"},
           notes="Non-parametric calibration of mid."),
    Config(name="V05 paper FLB prior (no fit)", **{**B0, "estimator": "paper_flb"},
           notes="Burgi et al. Table 8 politics coefficients applied as-is."),
    Config(name="V06 microstructure logistic", **{**B0, "estimator": "rich"},
           notes="Adds spread, volume, OI, age, 7d drift, field size."),
    Config(name="V07 reversion term", **{**B0, "estimator": "reversion"},
           notes="Adds last week's mid change (tests momentum vs mean reversion)."),
    Config(name="V08 blend with market", **{**B0, "estimator": "blend"},
           notes="w*old_plan + (1-w)*market, w picked on a validation tail inside train."),
    Config(name="V09 sum-to-one normalisation", **{**B0, "estimator": "sum_to_one"},
           notes="Normalise exclusive fields to sum 1 before recalibrating."),
    Config(name="V10 recency: last 365d of train", **{**B0, "est_params": {"recency_days": 365}},
           notes="Fit only on the most recent year of train (bias may be fading, Burgi Table 9)."),
    Config(name="V11 min_edge 2c", **{**B0, "min_edge": 0.02}, notes="Lower trade threshold."),
    Config(name="V12 min_edge 10c", **{**B0, "min_edge": 0.10}, notes="Higher trade threshold."),
    Config(name="V13 edge in logit space", **{**B0, "edge_space": "logit", "min_edge": 0.25},
           notes="Require 0.25 logit units of edge instead of cents."),
    Config(name="V14 YES side only", **{**B0, "sides": "yes"}, notes="Only buy YES."),
    Config(name="V15 NO side only", **{**B0, "sides": "no"}, notes="Only buy NO (longshot-fade direction)."),
    Config(name="V16 favourites only (>=50c)", **{**B0, "min_price": 0.50}, notes="Entry price >= 50c."),
    Config(name="V17 tails excluded (15-85c)", **{**B0, "min_price": 0.15, "max_price": 0.85},
           notes="Trade only the middle of the price range."),
    Config(name="V18 tight books only (spread<=4c)", **{**B0, "filter": "liquid"}, notes="Universe filter."),
    Config(name="V19 mature markets (age>=30d)", **{**B0, "filter": "mature"}, notes="Universe filter."),
    Config(name="V20 maker execution", **{**B0, "execution": "maker"},
           notes="Join the best bid; filled only if price trades through within a week; no maker fee on political series (verified on API)."),
    Config(name="V21 low-sophistication markets", **{**B0, "filter": "soph_low"},
           notes="Bottom tercile of the composite sophistication score (train cut points)."),
    Config(name="V22 mid-sophistication markets", **{**B0, "filter": "soph_mid"}, notes="Middle tercile."),
    Config(name="V23 high-sophistication markets", **{**B0, "filter": "soph_high"}, notes="Top tercile."),
    Config(name="V24 zero-fee counterfactual", **{**B0, "fee_rate": 0.0},
           notes="Not tradeable; shows how much of the result the fee decides."),
    Config(name="V25 knowledge-file prior", **{**B0, "estimator": "kg_prior"},
           notes="Adds the best retrieved base-rate line (as_of < T) as a logit feature: does the knowledge layer earn its place?"),
]


def run(names: set | None = None):
    snap = load()
    done = set()
    if os.path.exists(RESULTS):
        with open(RESULTS, encoding="utf-8") as fh:
            done = {json.loads(l)["name"] for l in fh}
    for cfg in CONFIGS:
        if cfg.name in done and not (names and cfg.name in names):
            continue
        r = evaluate(cfg, snap)
        t = r["test"]
        print(f"{cfg.name:<40} test brier {t.get('brier_model')} vs mkt {t.get('brier_market')} "
              f"trades {t.get('n_trades')} pnl {t.get('pnl_total')}", flush=True)


def _fmt(v):
    return "–" if v is None else (f"{v:+.4f}" if isinstance(v, float) else str(v))


def report():
    runs = {}
    with open(RESULTS, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            runs[r["name"]] = r          # last run of a name wins
    order = [c.name for c in CONFIGS] + [n for n in runs if n not in {c.name for c in CONFIGS}]
    rows = [runs[n] for n in order if n in runs]
    if not rows:
        return
    first = rows[0]
    L = ["# Backtests — Kalshi political markets", "",
         "Generated by `python -m forecast.run_backtests --report` from `data_cache/backtest_runs.jsonl`.",
         "Do not hand-edit numbers; rerun instead.", "",
         "## Protocol", "",
         f"- Universe: settled binary markets in Kalshi's Elections + Politics categories (live and /historical endpoints), daily candles, weekly decision snapshots (Monday 04:00 UTC).",
         f"- Split: most recent 30% of events by close = TEST (never used for fitting or tuning). Split cutoff: **{first['split_cutoff']}**; test snapshots all have T >= cutoff.",
         f"- Train: {first['train']['n_markets']} markets / {first['train']['n_events']} events / {first['train']['n_snap']} snapshots. "
         f"Test: {first['test']['n_markets']} markets / {first['test']['n_events']} events / {first['test']['n_snap']} snapshots.",
         "- Brier is market-weighted (each market counts once). Baseline = the market mid at the same snapshot.",
         "- P&L: 1 contract, first triggering snapshot per market, held to settlement; taker pays ask (or 1-bid) + 0.07·P·(1−P). The money baseline is 0 (do nothing).",
         "- CIs: 95%, bootstrapped by event.",
         f"- Trial count: {len(rows)} configurations so far. With this many looks at one test set, a single 'win' at 95% is expected by chance about once in 20; treat isolated wins accordingly.",
         "",
         "## Summary (held-out test set)", "",
         "| run | Brier model | Brier market | skill | Δ CI95 | trades | P&L $ | P&L/trade | P&L/trade CI95 | beat market Brier? | beat $0? |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        t = r["test"]
        ci = t.get("brier_diff_ci95")
        beat_b = "–"
        if t.get("brier_model") is not None:
            if ci and ci[1] < 0:
                beat_b = "**yes (CI<0)**"
            elif t["brier_model"] < t["brier_market"]:
                beat_b = "point only"
            else:
                beat_b = "no"
        pci = t.get("pnl_per_trade_ci95")
        beat_p = "no trades" if not t.get("n_trades") else ("**yes (CI>0)**" if pci and pci[0] > 0 else ("point only" if t["pnl_total"] > 0 else "no"))
        L.append(f"| {r['name']} | {t.get('brier_model')} | {t.get('brier_market')} | {_fmt(t.get('brier_skill'))} | "
                 f"{ci if ci else '–'} | {t.get('n_trades')} | {t.get('pnl_total')} | {_fmt(t.get('pnl_per_trade'))} | "
                 f"{pci if pci else '–'} | {beat_b} | {beat_p} |")
    side = os.path.join(ROOT, "docs", "backtests_findings.md")
    if os.path.exists(side):
        L += ["", open(side, encoding="utf-8").read().strip()]
    L += ["", "## Runs", ""]
    for r in rows:
        c, t, tr = r["config"], r["test"], r["train"]
        L += [f"### {r['name']}", "",
              f"- Run at {r['run_at']} UTC. Config: estimator `{c['estimator']}` {c['est_params'] or ''}, min_edge {c['min_edge']}, "
              f"max_spread {c['max_spread']}, price {c['min_price']}–{c['max_price']}, execution {c['execution']}, sides {c['sides']}, "
              f"edge_space {c['edge_space']}, filter {c['filter']}, fee_rate {c['fee_rate']}.",
              f"- What changed: {c['notes']}",
              f"- Train (in-sample): Brier {tr.get('brier_model')} vs market {tr.get('brier_market')}; {tr.get('n_trades')} trades, P&L {tr.get('pnl_total')}.",
              f"- Test: Brier {t.get('brier_model')} vs market {t.get('brier_market')} (Δ CI {t.get('brier_diff_ci95')}); "
              f"{t.get('n_trades')} trades on {t.get('n_trade_events')} events, P&L {t.get('pnl_total')}, per trade {t.get('pnl_per_trade')} "
              f"(CI {t.get('pnl_per_trade_ci95')}), hit rate {t.get('hit_rate')}, return on cost {t.get('return_on_cost')}, "
              f"top-event share of P&L {t.get('top_event_pnl_share')}.", ""]
        if t.get("calibration_model"):
            L += ["| bucket | n | model pred | market pred | realized (model bucket) | realized (market bucket) |", "|---|---|---|---|---|---|"]
            mk = {x["bucket"]: x for x in t["calibration_market"]}
            for x in t["calibration_model"]:
                m = mk.get(x["bucket"], {})
                L.append(f"| {x['bucket']} | {x['n_snap']} | {x['mean_pred']} | {m.get('mean_pred','–')} | {x['realized']} | {m.get('realized','–')} |")
            L.append("")
    with open(DOC, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if not a.report:
        run()
    report()
