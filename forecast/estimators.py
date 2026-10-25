"""Probability estimators for the backtest. Each has fit(train_df) and predict(df).

Every estimator sees only snapshot columns observable at T (see snapshots.py).
Fitting uses market weights so a long-lived market does not outvote a short one.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

EPS = 1e-4


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def _w(df):
    return (1.0 / df.groupby("ticker")["ticker"].transform("count")).to_numpy()


class MarketMid:
    """The baseline: the market's own mid price."""
    def fit(self, df):
        return self

    def predict(self, df):
        return df["mid"].to_numpy()


class _Logistic:
    C = 1.0

    def features(self, df) -> np.ndarray:
        raise NotImplementedError

    def fit(self, df):
        X = self.features(df, fit=True)
        self.m = LogisticRegression(C=self.C, max_iter=2000)
        self.m.fit(X, df["outcome"].to_numpy(), sample_weight=_w(df))
        return self

    def predict(self, df):
        return self.m.predict_proba(self.features(df))[:, 1]


class PlattGlobal(_Logistic):
    """Recalibrate the market: p = sigmoid(a + b*logit(mid)). Captures favourite-longshot."""
    def features(self, df, fit=False):
        return logit(df["mid"]).reshape(-1, 1)


class OldPlanStageA(_Logistic):
    """The fund design's Stage A estimator, made mechanical.

    p0 = archetype base rate (an intercept per archetype, learned on train);
    p1 = p0 adjusted by the market's own information (slope on logit(mid)).
    In the design, p1's adjustment came from retrieved context via an LLM;
    with no LLM available the market price is the only context signal, and
    knowledge-file priors are tested separately (KGPrior).
    """
    def __init__(self, recency_days: float | None = None):
        self.recency_days = recency_days

    def features(self, df, fit=False):
        if fit:
            self.archs = sorted(df["archetype"].unique())
        A = np.column_stack([(df["archetype"] == a).to_numpy(float) for a in self.archs])
        return np.column_stack([logit(df["mid"]), A])

    def fit(self, df):
        if self.recency_days:
            df = df[df["T"] >= df["T"].max() - self.recency_days * 86400]
        return super().fit(df)


class PlattArchetypeSlope(OldPlanStageA):
    """Archetype-specific intercept AND slope."""
    def features(self, df, fit=False):
        if fit:
            self.archs = sorted(df["archetype"].unique())
        L = logit(df["mid"])
        cols = [L]
        for a in self.archs:
            m = (df["archetype"] == a).to_numpy(float)
            cols += [m, m * L]
        return np.column_stack(cols)


class RichLogistic(_Logistic):
    """Market price plus observable microstructure: spread, volume, age, drift, field size."""
    C = 0.5

    def features(self, df, fit=False):
        L = logit(df["mid"])
        X = np.column_stack([
            L,
            df["spread"].to_numpy(),
            np.log1p(df["vol_7d"].to_numpy()),
            np.log1p(df["oi"].to_numpy()),
            np.log1p(df["age_days"].to_numpy()),
            np.nan_to_num(df["d_mid_7d"].to_numpy()),
            np.log(df["event_size"].to_numpy()),
            L * df["spread"].to_numpy(),
        ])
        if fit:
            self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        return (X - self.mu) / self.sd


class Reversion(_Logistic):
    """Fade (or follow) last week's move: p = sigmoid(a + b*logit(mid) + c*d_mid_7d)."""
    def features(self, df, fit=False):
        return np.column_stack([logit(df["mid"]), np.nan_to_num(df["d_mid_7d"].to_numpy())])


class Isotonic:
    def fit(self, df):
        self.m = IsotonicRegression(out_of_bounds="clip", y_min=EPS, y_max=1 - EPS)
        self.m.fit(df["mid"].to_numpy(), df["outcome"].to_numpy(), sample_weight=_w(df))
        return self

    def predict(self, df):
        return self.m.predict(df["mid"].to_numpy())


class PaperFLB:
    """No fitting: Bürgi, Deng & Whelan (2026) Table 8 politics regression,
    outcome% - price% = -1.912 + 0.022*price% (p.24). Applied as a fixed prior."""
    def __init__(self, const=-1.912, slope=0.022):
        self.const, self.slope = const, slope

    def fit(self, df):
        return self

    def predict(self, df):
        mid = df["mid"].to_numpy()
        return np.clip(mid + (self.const + self.slope * 100 * mid) / 100, EPS, 1 - EPS)


class Blend:
    """w * inner + (1-w) * market; w chosen on a time-ordered validation tail of train."""
    def __init__(self, inner: str = "old_plan", grid=(0.0, 0.25, 0.5, 0.75, 1.0)):
        self.inner_key, self.grid = inner, grid

    def fit(self, df):
        from forecast.backtest import brier, inner_split
        tr, va, _ = inner_split(df)
        inner = ESTIMATORS[self.inner_key]().fit(tr)
        p, mid, y, w = inner.predict(va), va["mid"].to_numpy(), va["outcome"].to_numpy(), _w(va)
        scores = {g: brier(g * p + (1 - g) * mid, y, w) for g in self.grid}
        self.wt = min(scores, key=scores.get)
        self.inner = ESTIMATORS[self.inner_key]().fit(df)
        return self

    def predict(self, df):
        return self.wt * self.inner.predict(df) + (1 - self.wt) * df["mid"].to_numpy()


class SumToOne:
    """Normalise mids within an event at the same T when the legs look mutually
    exclusive (>2 legs, person/primary/nomination archetype, sum of mids 0.85-1.4),
    then Platt-recalibrate. Tests whether the field's overround is the bias."""
    def fit(self, df):
        self.platt = PlattGlobal().fit(df.assign(mid=self._norm(df)))
        return self

    def _norm(self, df):
        g = df.groupby(["event", "T"])["mid"].transform("sum")
        n = df.groupby(["event", "T"])["mid"].transform("count")
        excl = (df["archetype"].isin(["person_winner", "primary"])) & (n == df["event_size"]) & (n > 2) & g.between(0.85, 1.4)
        return np.where(excl, df["mid"] / g, df["mid"])

    def predict(self, df):
        return self.platt.predict(df.assign(mid=self._norm(df)))


ESTIMATORS = {
    "market": MarketMid,
    "platt": PlattGlobal,
    "old_plan": OldPlanStageA,
    "platt_arch_slope": PlattArchetypeSlope,
    "rich": RichLogistic,
    "reversion": Reversion,
    "isotonic": Isotonic,
    "paper_flb": PaperFLB,
    "blend": Blend,
    "sum_to_one": SumToOne,
}


# --- universe filters: f(df, train) -> df. Thresholds may use TRAIN only. -------

def _liquid(df, train):
    return df[df["spread"] <= 0.04]


def _mature(df, train):
    return df[df["age_days"] >= 30]


def _soph(level):
    def f(df, train):
        from forecast.participants import Sophistication
        s = Sophistication().fit(train)
        return df[s.tercile(df) == level]
    return f


def _sub_low(name):
    """Bottom tercile of ONE sophistication submodel; cut points from train."""
    def f(df, train):
        from forecast.participants import Sophistication
        s = Sophistication().fit(train)
        cut = np.nanpercentile(s.submodels(train)[name], 100 / 3)
        return df[(s.submodels(df)[name] <= cut).to_numpy()]
    return f


FILTERS = {"liquid": _liquid, "eff_low": _sub_low("efficiency"), "mature": _mature,
           "soph_low": _soph("low"), "soph_mid": _soph("mid"), "soph_high": _soph("high")}


# --- knowledge-layer prior ---------------------------------------------------------

BR_RE = None


def _base_rate_value(text: str):
    """Pull a probability out of a retrieved `base_rate: name = value` line.
    Accepts values in (0,1), or 1-100 when the name says rate/pct/share."""
    import re
    m = re.match(r"base_rate:\s*([A-Za-z0-9_]+)\s*=\s*(-?[\d.]+)", text)
    if not m:
        return None
    name, v = m.group(1).lower(), float(m.group(2))
    if 0 < v < 1:
        return v
    if 1 <= v < 100 and any(k in name for k in ("rate", "pct", "share", "percent", "win", "pass")):
        return v / 100
    return None


class KGPrior(_Logistic):
    """p = sigmoid(a + b*logit(mid) + c*logit(p_kg)*has_kg + d*has_kg).

    p_kg is the highest-ranked probability-like base rate among the top-k
    retrieved chunks dated before T. Fit on train: if the knowledge layer is
    noise, c -> 0 and Brier does not move."""

    def __init__(self, k: int = 10):
        self.k = k
        self._cache: dict = {}

    def _kg(self, df):
        """Score each market's query ONCE (the query does not depend on T), then
        for each decision time keep only chunks with as_of < T. Same result as
        calling search(as_of=T) per snapshot, without the per-week rescoring."""
        from forecast.retrieval import Retriever
        if not hasattr(self, "_r"):
            self._r = Retriever(per_file_cap=None)
        vals = np.full(len(df), np.nan)
        for j, (tkr, title, st, T) in enumerate(zip(df["ticker"], df["title"], df["series_title"], df["T"])):
            if tkr not in self._cache:
                hits = self._r.search(f"{title} {st or ''}", "", tkr, as_of=None, k=200)
                self._cache[tkr] = [(c.as_of, _base_rate_value(c.text) if c.kind == "claim" else None) for _, c in hits]
            seen = 0
            for as_of, v in self._cache[tkr]:
                if as_of >= T:
                    continue
                seen += 1
                if v is not None:
                    vals[j] = v
                    break
                if seen >= self.k:
                    break
        return vals

    def features(self, df, fit=False):
        kg = self._kg(df)
        has = ~np.isnan(kg)
        return np.column_stack([logit(df["mid"]), np.where(has, logit(np.nan_to_num(kg, nan=0.5)), 0.0), has.astype(float)])


ESTIMATORS["kg_prior"] = KGPrior


class JevStack(OldPlanStageA):
    """B0 plus Jev's judgments about each contract's text (forecast/jev_questions.py).

    p = sigmoid(B0 terms + sum_k c_k * jev_k [+ sum_k d_k * jev_k * logit(mid)] [+ microstructure]).
    Jev features are centred and scaled on train. Only TEXT questions are used:
    they ask what the contract says, not what happened. A market with no cached
    Jev answers raises, so a partial cache can never silently mix feature sets.
    """
    C = 0.5

    def __init__(self, interactions: bool = False, micro: bool = False, world: bool = False, C: float = 0.5,
                 placebo: bool = False):
        self.interactions, self.micro, self.world, self.C, self.placebo = interactions, micro, world, C, placebo
        self.recency_days = None

    def _jev(self, df):
        if not hasattr(self, "_tab"):
            from forecast.jev_features import feature_columns, table
            t = table(include_world=self.world)
            self._cols = ["jev_" + c for c in feature_columns(self.world)]
            self._tab = t.set_index("ticker")[self._cols]
            if self.placebo:   # control: same features, shuffled across markets
                vals = self._tab.to_numpy()[np.random.default_rng(0).permutation(len(self._tab))]
                self._tab = pd.DataFrame(vals, index=self._tab.index, columns=self._cols)
        missing = set(df["ticker"]) - set(self._tab.index)
        if missing:
            raise RuntimeError(f"{len(missing)} markets have no Jev answers; run python -m forecast.jev_features run")
        return self._tab.loc[df["ticker"]].to_numpy(float)

    def features(self, df, fit=False):
        base = super().features(df, fit=fit)
        J = self._jev(df)
        if fit:
            self.jmu, self.jsd = np.nanmean(J, 0), np.nanstd(J, 0) + 1e-9
        J = np.nan_to_num((J - self.jmu) / self.jsd)
        cols = [base, J]
        if self.interactions:
            cols.append(J * logit(df["mid"]).reshape(-1, 1))
        if self.micro:
            M = np.column_stack([df["spread"].to_numpy(), np.log1p(df["vol_7d"].to_numpy()),
                                 np.log1p(df["oi"].to_numpy()), np.log1p(df["age_days"].to_numpy()),
                                 np.nan_to_num(df["d_mid_7d"].to_numpy()), np.log(df["event_size"].to_numpy())])
            if fit:
                self.mmu, self.msd = M.mean(0), M.std(0) + 1e-9
            cols.append((M - self.mmu) / self.msd)
        return np.column_stack(cols)


ESTIMATORS["jev"] = JevStack
