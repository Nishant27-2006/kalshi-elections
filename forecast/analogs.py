"""Find historical analogs of a race and read off how its polls missed.

Example of the pattern this hunts for: 2022 PA Senate. Oz (R) was an outsider
with poor favorability, Fetterman (D) was a well-known statewide officeholder,
and Fetterman beat his final polling average. Given a 2026 race, which past
races look most like it on those factors, and how did THEIR polls miss?

Data: knowledge/politics/data/races_*.csv (schema in RACE_SCHEMA.md).

A poll miss has two parts:
    miss = cycle-wide bias (every race that year shares it) + race residual
The cycle part is the same for every race in a year, so candidate factors
cannot explain it; analogs are matched on the RESIDUAL. The cycle part is
reported separately as an uncertainty, not a prediction.

Two encodings, and the out-of-sample check decides between them:
  literal  : factors are D-minus-R, miss is D-minus-R.
  mirrored : factors and miss are re-signed toward the party OUT of the White
             House, so a D-president midterm (2022) can analog an R-president
             midterm (2026).

    python -m forecast.analogs validate             # walk-forward by cycle
    python -m forecast.analogs explain 2022-senate-PA
    python -m forecast.analogs predict --year 2026  # analogs for live races
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "knowledge", "politics", "data")

FEATURES = [
    "midterm_env",     # +1 midterm with R president (env favours D), -1 with D president, 0 presidential year
    "incumbency",      # +1 D incumbent running, -1 R incumbent, 0 open
    "lean",            # prior presidential margin / 10
    "quality_gap",     # D prior statewide win minus R
    "fame_gap",        # D well known minus R well known
    "outsider_gap",    # R outsider minus D outsider (positive = R is the outsider)
    "scandal_gap",     # R scandal minus D scandal
    "trump_endorsed",  # R nominee Trump-endorsed (signed toward D: +1 = endorsed)
    "fav_gap",         # (D net fav - R net fav) / 10, 0 when unknown
    "money",           # log(D raised / R raised), 0 when unknown
    "closeness",       # -|poll margin| / 10 (tight races near 0)
    "governor",        # 1 governor, 0 senate
]


def load_races() -> pd.DataFrame:
    frames = [pd.read_csv(p) for p in sorted(glob.glob(os.path.join(DATA, "races_*.csv")))]
    df = pd.concat(frames, ignore_index=True).drop_duplicates("race_id", keep="last")
    return df


def _num(s):
    return pd.to_numeric(s, errors="coerce")


def encode(df: pd.DataFrame, mirrored: bool) -> pd.DataFrame:
    f = pd.DataFrame(index=df.index)
    midterm = (df["cycle_type"].str.lower() == "midterm").astype(float)
    pres_r = (df["pres_party"].str.upper() == "R").astype(float)
    f["midterm_env"] = midterm * (2 * pres_r - 1)
    inc = df["incumbent_running"].fillna("none").str.upper()
    f["incumbency"] = np.where(inc == "D", 1.0, np.where(inc == "R", -1.0, 0.0))
    f["lean"] = _num(df["state_prior_pres_margin"]).fillna(0) / 10
    f["quality_gap"] = _num(df["d_prior_statewide"]).fillna(0) - _num(df["r_prior_statewide"]).fillna(0)
    f["fame_gap"] = _num(df["d_well_known"]).fillna(0) - _num(df["r_well_known"]).fillna(0)
    f["outsider_gap"] = _num(df["r_outsider"]).fillna(0) - _num(df["d_outsider"]).fillna(0)
    f["scandal_gap"] = _num(df["r_scandal"]).fillna(0) - _num(df["d_scandal"]).fillna(0)
    f["trump_endorsed"] = _num(df["r_trump_endorsed"]).fillna(0)
    fav = (_num(df["d_net_fav"]) - _num(df["r_net_fav"])) / 10
    f["fav_gap"] = fav.fillna(0).clip(-4, 4)
    ratio = _num(df["fundraising_ratio_d_over_r"])
    f["money"] = np.log(ratio.where(ratio > 0)).fillna(0).clip(-3, 3)
    pm = _num(df["final_poll_avg_margin"])
    f["closeness"] = -(pm.abs() / 10).fillna(1.5)
    f["governor"] = (df["office"].str.lower() == "governor").astype(float)

    miss = _num(df["poll_miss"])
    if mirrored:
        # sign = +1 when the out-party is D (R president), -1 when the out-party is R
        sign = np.where(pres_r == 1, 1.0, -1.0)
        for c in ["incumbency", "lean", "quality_gap", "fame_gap", "outsider_gap",
                  "scandal_gap", "trump_endorsed", "fav_gap", "money"]:
            f[c] = f[c] * sign
        f["midterm_env"] = midterm  # always "against the president's party" once mirrored
        miss = miss * sign
    f["miss"] = miss
    f["poll_margin"] = pm
    f["year"] = df["year"].astype(int)
    f["race_id"] = df["race_id"]
    f["sign"] = np.where(pres_r == 1, 1.0, -1.0) if mirrored else 1.0
    return f


def _residualize(enc: pd.DataFrame) -> pd.DataFrame:
    enc = enc.copy()
    enc["cycle_bias"] = enc.groupby("year")["miss"].transform("mean")
    enc["resid"] = enc["miss"] - enc["cycle_bias"]
    return enc


def _scale(train: pd.DataFrame):
    mu = train[FEATURES].mean()
    sd = train[FEATURES].std().replace(0, 1).fillna(1)
    return mu, sd


def neighbours(target: pd.Series, pool: pd.DataFrame, mu, sd, k: int = 7, weights=None):
    w = np.ones(len(FEATURES)) if weights is None else np.asarray(weights)
    X = ((pool[FEATURES] - mu) / sd).to_numpy()
    x = ((target[FEATURES] - mu) / sd).to_numpy(dtype=float)
    d = np.sqrt((((X - x) ** 2) * w).sum(axis=1))
    out = pool.assign(dist=d).sort_values("dist").head(k)
    # inverse-distance weights, softened so one near-duplicate cannot dominate
    out["w"] = 1.0 / (out["dist"] + 0.5)
    return out


def predict_resid(target, pool, mu, sd, k=7):
    nb = neighbours(target, pool, mu, sd, k)
    w = nb["w"] / nb["w"].sum()
    mean = float((w * nb["resid"]).sum())
    spread = float(math.sqrt((w * (nb["resid"] - mean) ** 2).sum()))
    return mean, spread, nb


def validate(k: int = 7) -> dict:
    """Walk forward by cycle: predict year Y's residuals from cycles < Y only."""
    races = load_races()
    report = {}
    for mode in ("literal", "mirrored"):
        enc = _residualize(encode(races, mirrored=(mode == "mirrored")).dropna(subset=["miss"]))
        rows = []
        for y in sorted(enc["year"].unique()):
            train, test = enc[enc["year"] < y], enc[enc["year"] == y]
            if len(train) < 15 or test.empty:
                continue
            mu, sd = _scale(train)
            for _, t in test.iterrows():
                p, s, _ = predict_resid(t, train, mu, sd, k)
                rows.append({"year": y, "race_id": t["race_id"], "pred": p, "actual": t["resid"]})
        r = pd.DataFrame(rows)
        if r.empty:
            report[mode] = {"n": 0}
            continue
        mae_model = float((r["pred"] - r["actual"]).abs().mean())
        mae_zero = float(r["actual"].abs().mean())
        corr = float(np.corrcoef(r["pred"], r["actual"])[0, 1]) if len(r) > 2 else float("nan")
        # sign accuracy only where the analogs commit to a direction (>1pt)
        committed = r[r["pred"].abs() > 1.0]
        sign_acc = float((np.sign(committed["pred"]) == np.sign(committed["actual"])).mean()) if len(committed) else float("nan")
        boot = []
        rng = np.random.default_rng(0)
        for _ in range(2000):
            b = r.sample(len(r), replace=True, random_state=int(rng.integers(1e9)))
            boot.append((b["actual"].abs() - (b["pred"] - b["actual"]).abs()).mean())
        lo, hi = np.percentile(boot, [2.5, 97.5])
        report[mode] = {
            "n": len(r), "years": sorted(r["year"].unique().tolist()),
            "mae_model": round(mae_model, 3), "mae_zero": round(mae_zero, 3),
            "mae_gain_ci95": [round(float(lo), 3), round(float(hi), 3)],
            "corr": round(corr, 3), "sign_acc_when_committed": round(sign_acc, 3),
            "n_committed": len(committed),
        }
    return report


def explain(race_id: str, k: int = 7, mode: str = "mirrored") -> None:
    races = load_races()
    enc = _residualize(encode(races, mirrored=(mode == "mirrored")))
    t = enc[enc["race_id"] == race_id]
    if t.empty:
        raise SystemExit(f"unknown race {race_id}")
    t = t.iloc[0]
    pool = enc[(enc["year"] < t["year"]) & enc["miss"].notna()]
    mu, sd = _scale(pool)
    p, s, nb = predict_resid(t, pool, mu, sd, k)
    unit = "toward the party OUT of the White House" if mode == "mirrored" else "toward D"
    print(f"{race_id} [{mode}]  predicted race-specific poll miss {p:+.1f} pts {unit} "
          f"(= {p * t['sign']:+.1f} D-R), analog spread {s:.1f}")
    if pd.notna(t["miss"]):
        print(f"   actual miss {t['miss']:+.1f} = cycle {t['cycle_bias']:+.1f} + residual {t['resid']:+.1f}")
    print(f"   nearest past races (miss/resid {unit}; miss_DR = same miss in D-R points):")
    for _, r in nb.iterrows():
        print(f"     {r['race_id']:<28} dist {r['dist']:.2f}  miss {r['miss']:+5.1f}  resid {r['resid']:+5.1f}"
              f"  miss_DR {r['miss'] * r['sign']:+5.1f}")


def predict(year: int, k: int = 7, mode: str = "mirrored") -> list[dict]:
    races = load_races()
    enc = _residualize(encode(races, mirrored=(mode == "mirrored")))
    pool = enc[(enc["year"] < year) & enc["miss"].notna()]
    mu, sd = _scale(pool)
    cyc = pool.groupby("year")["miss"].mean()
    midterm_cyc = pool[pool["midterm_env"] != 0].groupby("year")["miss"].mean()
    out = []
    for _, t in enc[enc["year"] == year].iterrows():
        p, s, nb = predict_resid(t, pool, mu, sd, k)
        sign = t["sign"]
        out.append({
            "race_id": t["race_id"], "mode": mode,
            "poll_margin_d": None if pd.isna(t["poll_margin"]) else float(t["poll_margin"]),
            # back to D-minus-R units
            "pred_resid_d": round(float(p * sign), 2), "analog_spread": round(s, 2),
            "analogs": [{"race_id": r["race_id"], "dist": round(float(r["dist"]), 2),
                         "miss_d": round(float(r["miss"] * (r["sign"] if mode == "mirrored" else 1)), 1)}
                        for _, r in nb.iterrows()],
            "cycle_bias_sd": round(float(cyc.std()), 2),
            "past_midterm_cycle_bias_outparty": round(float(midterm_cyc.mean()), 2) if len(midterm_cyc) else None,
        })
    return out


PATTERN_FACTORS = {
    "R nominee is an outsider (never held office)": lambda f: f["outsider_gap"] > 0,
    "D nominee is an outsider": lambda f: f["outsider_gap"] < 0,
    "D better known than R": lambda f: f["fame_gap"] > 0,
    "R better known than D": lambda f: f["fame_gap"] < 0,
    "D has prior statewide win, R doesn't": lambda f: f["quality_gap"] > 0,
    "R has prior statewide win, D doesn't": lambda f: f["quality_gap"] < 0,
    "R nominee Trump-endorsed in primary": lambda f: f["trump_endorsed"] > 0,
    "R nominee hit by scandal": lambda f: f["scandal_gap"] > 0,
    "D nominee hit by scandal": lambda f: f["scandal_gap"] < 0,
    "D incumbent running": lambda f: f["incumbency"] > 0,
    "R incumbent running": lambda f: f["incumbency"] < 0,
    "open seat": lambda f: f["incumbency"] == 0,
    "midterm, D president": lambda f: f["midterm_env"] < 0,
    "midterm, R president": lambda f: f["midterm_env"] > 0,
    "D outraised R 2:1+": lambda f: f["money"] > np.log(2),
    "R outraised D 2:1+": lambda f: f["money"] < -np.log(2),
    "D net-fav lead >10 over R": lambda f: f["fav_gap"] > 1,
    "R net-fav lead >10 over D": lambda f: f["fav_gap"] < -1,
    "governor race": lambda f: f["governor"] > 0,
    "state voted R for president by 5+ last time": lambda f: f["lean"] < -0.5,
    "state voted D for president by 5+ last time": lambda f: f["lean"] > 0.5,
}


def patterns(min_n: int = 6, n_boot: int = 4000, control: bool = False) -> pd.DataFrame:
    """For each factor: mean race-specific poll miss (toward D) when present,
    minus when absent, bootstrap CI. Uses the cycle-demeaned residual so a
    factor is not credited with a whole cycle's polling error."""
    enc = _residualize(encode(load_races(), mirrored=False).dropna(subset=["miss"]))
    if control:
        # Remove what partisan lean and the poll margin itself explain (polls in
        # lopsided races understate the favourite), so a factor is not credited
        # with the "margin expands toward the stronger side" effect.
        X = np.column_stack([np.ones(len(enc)), enc["lean"], enc["poll_margin"].fillna(0) / 10])
        beta, *_ = np.linalg.lstsq(X, enc["resid"].to_numpy(), rcond=None)
        enc["resid"] = enc["resid"] - X @ beta
        print(f"control fit: resid = {beta[0]:+.2f} {beta[1]:+.2f}*lean/10pts {beta[2]:+.2f}*poll_margin/10pts")
    rng = np.random.default_rng(0)
    rows = []
    for name, fn in PATTERN_FACTORS.items():
        m = fn(enc).to_numpy()
        a, b = enc.loc[m, "resid"].to_numpy(), enc.loc[~m, "resid"].to_numpy()
        if len(a) < min_n or len(b) < min_n:
            continue
        diffs = [rng.choice(a, len(a)).mean() - rng.choice(b, len(b)).mean() for _ in range(n_boot)]
        lo, hi = np.percentile(diffs, [2.5, 97.5])
        rows.append({"factor": name, "n_with": len(a), "mean_resid_with": round(a.mean(), 2),
                     "mean_resid_without": round(b.mean(), 2), "diff": round(a.mean() - b.mean(), 2),
                     "ci95": (round(float(lo), 2), round(float(hi), 2)),
                     "years": ",".join(str(y) for y in sorted(enc.loc[m, "year"].unique())),
                     "examples": ", ".join(enc.loc[m].assign(a=enc.loc[m, "resid"].abs()).sort_values("a", ascending=False)["race_id"].head(3))})
    out = pd.DataFrame(rows).sort_values("diff", key=lambda s: -s.abs())
    out["clear"] = out["ci95"].apply(lambda c: c[0] > 0 or c[1] < 0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["validate", "explain", "predict", "patterns"])
    ap.add_argument("race", nargs="?")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--k", type=int, default=7)
    ap.add_argument("--control", action="store_true", help="patterns: net out state lean and poll margin first")
    ap.add_argument("--mode", default="mirrored", choices=["mirrored", "literal"])
    a = ap.parse_args()
    if a.cmd == "validate":
        print(json.dumps(validate(a.k), indent=2))
    elif a.cmd == "patterns":
        pd.set_option("display.width", 250, "display.max_colwidth", 70)
        print(patterns(control=a.control).to_string(index=False))
    elif a.cmd == "explain":
        explain(a.race, a.k, a.mode)
    else:
        print(json.dumps(predict(a.year, a.k, a.mode), indent=2))


if __name__ == "__main__":
    main()
