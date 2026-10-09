"""Submodels for how sophisticated a market's participants are, from what is
observable at decision time T only.

Three submodels, each a score where HIGHER = more sophisticated:

  liquidity   z(log vol_7d) + z(log OI) - z(spread)
              Professional market makers quote tight and deep; retail-only
              books are wide and thin.
  efficiency  -|lag-1 autocorrelation of daily mid changes| - z(reversal share)
              In an informed book a move sticks. In a noisy book moves reverse
              (overreaction) or trickle in over days (slow reaction to news).
              Both show up as non-zero autocorrelation.
  activity    -z(stale_days) + z(log candles with volume / age)
              How continuously the book is attended.

composite = mean of the three z-scored submodels. All z-scores use TRAIN
moments, so test markets are scored on a fixed scale.

Trade-size profile (median / 90th pct contracts per print) needs one trades
call per market, so it is fetched for a sample and reported in
docs/participants.md rather than used in the backtest filter.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from forecast.kalshi_data import load_candles
from forecast.snapshots import parse_candles


def _autocorr_by_ticker(snap: pd.DataFrame) -> pd.DataFrame:
    """Per (ticker, T): lag-1 autocorrelation and reversal share of daily mid
    changes over the 30 days before T. Uses only candles ending <= T."""
    out = []
    for tkr, g in snap.groupby("ticker"):
        cs = load_candles(tkr)
        if not cs:
            continue
        df = parse_candles(cs)
        if df.empty:
            continue
        mid = ((df["bid"] + df["ask"]) / 2).where(df["bid"].notna() & df["ask"].notna(), df["last"])
        df = df.assign(mid=mid).dropna(subset=["mid"])
        t = df["t"].to_numpy()
        m = df["mid"].to_numpy()
        traded = (df["vol"] > 0).to_numpy()
        for T in g["T"].unique():
            sel = (t <= T) & (t > T - 30 * 86400)
            x = np.diff(m[sel])
            if len(x) >= 6 and np.std(x[:-1]) > 0 and np.std(x[1:]) > 0:
                ac = float(np.corrcoef(x[:-1], x[1:])[0, 1])
                nz = x[np.abs(x) > 0.005]
                rev = float(np.mean(np.sign(nz[1:]) != np.sign(nz[:-1]))) if len(nz) >= 3 else np.nan
            else:
                ac, rev = np.nan, np.nan
            out.append({"ticker": tkr, "T": T, "ac1": ac, "reversal": rev,
                        "traded_days_30": int(traded[sel].sum())})
    return pd.DataFrame(out)


def add_features(snap: pd.DataFrame) -> pd.DataFrame:
    ac = _autocorr_by_ticker(snap)
    return snap.merge(ac, on=["ticker", "T"], how="left")


class Sophistication:
    def fit(self, train: pd.DataFrame):
        F = self._raw(train)
        self.mu, self.sd = F.mean(), F.std().replace(0, 1)
        Z = (F - self.mu) / self.sd
        sub = self._submodels(Z)
        self.sub_mu, self.sub_sd = sub.mean(), sub.std().replace(0, 1)
        comp = self.score(train)
        self.cuts = np.nanpercentile(comp, [100 / 3, 200 / 3])
        return self

    @staticmethod
    def _raw(df):
        return pd.DataFrame({
            "lvol": np.log1p(df["vol_7d"]), "loi": np.log1p(df["oi"]), "spread": df["spread"],
            "abs_ac": df["ac1"].abs().fillna(df["ac1"].abs().median() if df["ac1"].notna().any() else 0.3),
            "reversal": df["reversal"].fillna(0.5),
            "stale": df["stale_days"],
            "activity": np.log1p(df["traded_days_30"].fillna(0)),
        }, index=df.index)

    @staticmethod
    def _submodels(Z):
        return pd.DataFrame({
            "liquidity": Z["lvol"] + Z["loi"] - Z["spread"],
            "efficiency": -Z["abs_ac"] - Z["reversal"],
            "activity": Z["activity"] - Z["stale"],
        }, index=Z.index)

    def submodels(self, df):
        Z = (self._raw(df) - self.mu) / self.sd
        return (self._submodels(Z) - self.sub_mu) / self.sub_sd

    def score(self, df):
        return self.submodels(df).mean(axis=1).to_numpy()

    def tercile(self, df):
        s = self.score(df)
        return np.where(s <= self.cuts[0], "low", np.where(s <= self.cuts[1], "mid", "high"))
