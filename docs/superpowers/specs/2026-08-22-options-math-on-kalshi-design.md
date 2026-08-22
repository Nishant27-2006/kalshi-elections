# Options Mathematics on Kalshi — Design

**Status:** design approved in chat 2026-08-22; awaiting spec review.
**Supersedes nothing.** Complements
`2026-08-19-prediction-market-fund-design.md`, which owns risk sizing (RU),
execution gating and the learner. This document owns *pricing*.

---

## 0. The premise correction this design rests on

The request was to apply Black-Scholes and related equations to "put options
and call options on Kalshi." **Kalshi lists no puts or calls.** Verified
against the live API: every contract returns `market_type: binary` and, on
threshold markets, `strike_type: greater`.

That is not a dead end. It is a shortcut:

> **A Kalshi contract already IS a digital (binary) option, and its price is
> the risk-neutral probability.**

The part of Black-Scholes that survives is the digital call value
`e^{-rT}·N(d₂)`. At Kalshi tenors the discount factor is negligible, so a
quoted price *is* `N(d₂)`. You do not price these with a model — you invert
them to recover what the market believes.

And the structure goes further. A threshold ladder is a strip of digital
calls at successive strikes, which means:

> **The ladder IS the risk-neutral CDF, published by the exchange, for free.**

Measured live, 2026-08-22:

| series | strikes | interior (2–98c) | span |
|---|---|---|---|
| `KXBTCD-26AUG2817` | 50 | 45 | 68.5k–90.5k, 96c→5c |
| `KXINXU-26AUG24H1000` | 60 | 60 | S&P 7475–7770 |
| `KXETHD-26AUG2201` | 300 | 235 | ETH 1700–3145 |
| `KXCPIYOY-26NOV` | 21 | 21 | CPI 3%–5% |

Breeden-Litzenberger recovers a density from vanilla calls by taking
`∂²C/∂K²`. On a digital ladder the exchange has already done one of those
derivatives: the ladder is `1 − CDF`, so a single first difference gives the
density.

---

## 1. Measured baseline — what the edge is NOT

Run before any code was designed, so the plan is not built on hope.

**Monotonicity scan**, 10 live ladders (`strike_type: greater`), looking for
`ask(Kᵢ) < bid(Kᵢ₊₁)`:

    violations: 0

**Binary put-call parity**, 285 events, looking for
`YES_ask + NO_ask < 100c`:

    violations: 0

**Partition sum**, 300 events with the event's real `mutually_exclusive`
flag attached (287 exclusive, 13 cumulative):

    true violations: 1  (KXNCAAFGAME-26AUG29HAWSTAN, 2 legs, bid-sum 101.0c)
    gross +1.0c  ->  NET -2.2c after 0.07*P*(1-P) on both legs

**One violation in 300 events, and it loses money after fees.**

A methodological note kept deliberately: the first version of this scan
reported *16* partition violations. All were false — it applied the
partition invariant to CUMULATIVE ladders, where nested legs
(`P(X≥68.5k) + P(X≥69.1k) + …`) sum far above 1 by construction. This is the
`threshold_ladder` vs `exclusive_field` distinction the repo's own taxonomy
already encodes, and ignoring it manufactured 16 phantom edges.

**Design consequence, load-bearing:** the applicable invariant depends on the
contract STRUCTURE. The scanner must run off `momentum_filter`'s existing
classifiers (`is_threshold_ladder`, `is_two_sided_handicap`,
`stated_cardinality`, `fixed_cardinality_range`), never on a naive
assumption that an event is a partition.

---

## 2. Stage A — model-free constraints (an instrument, not a strategy)

Assumes nothing about dynamics, which is why it comes first. Ships as a
**measurement** that runs against recorded ladders over days and reports
violation frequency, magnitude and fee-survival — one snapshot of 10 ladders
proves very little, and the book recorder already exists to supply the time
series.

| constraint | form | applies to |
|---|---|---|
| Monotonicity | `P(X≥Kᵢ) ≥ P(X≥Kᵢ₊₁)` | `threshold_ladder` |
| Density non-negativity | `pᵢ = P(X≥Kᵢ) − P(X≥Kᵢ₊₁) ≥ 0` | `threshold_ladder` |
| Binary put-call parity | `YES(K) + NO(K) = 1` | every contract |
| Partition bounds | `Σ bidᵢ ≤ 1 ≤ Σ askᵢ` | `exclusive_field` **only** |
| Vertical spread bounds | `0 ≤ pᵢ ≤ 1` | `threshold_ladder` |
| Fee-adjusted edge | `gross − Σ 0.07·Pᵢ(1−Pᵢ) > 0` | all of the above |

The last row is the one that matters. It is the same arithmetic that turned
the single real violation found above from `+1.0c` into `−2.2c`, and the
same that `AGENT.md:166` records for FL-23 D.

**Success criterion:** after 30 days of recording, report the violation rate
per structure family and the fraction clearing fees. If that fraction is
zero, Stage A has answered its question honestly and is retired as a
validator for Stage B rather than kept as a strategy.

---

## 3. Stage B — the implied distribution

**Density.** For a cumulative ladder:

    pdf(Kᵢ) ≈ [P(X≥Kᵢ) − P(X≥Kᵢ₊₁)] / (Kᵢ₊₁ − Kᵢ)

The raw difference is noisy at 1c tick granularity, which is what the
smoothing hyperparameter exists for (§6).

**Moments**, straight off the discrete density: mean, variance, skewness,
excess kurtosis.

**Implied volatility.** Invert the digital formula per strike:

    P(X≥K) = N(d₂),   d₂ = [ln(S/K) + (r − σ²/2)T] / (σ√T)

Solving for σ at each strike yields a **volatility smile on a prediction
market**. A monotone-in-strike σ is a flat-smile market; curvature is the
market pricing fat tails. Deviations between adjacent strikes' implied σ are
candidate mispricings that need no dynamics model.

**Risk-neutral vs physical.** The ladder gives the risk-neutral
distribution. Realized volatility from the existing 60-minute book recording
(Yang-Zhang and Garman-Klass estimators, which use the full OHLC the
recorder captures rather than close-to-close alone) gives the physical one.
The gap is the variance risk premium — and is the first genuinely tradeable
quantity in this document that does not require an arbitrage.

**Known constraint from Plan 1:** realized adverse excursion SATURATES at
about 1.7 cents within ~15 minutes and is flat for the following 45. Any
implied-vs-realized comparison must use matched horizons or it will
manufacture a premium out of a horizon mismatch.

---

## 4. Stage C — fair value from dynamics

Split by whether a price process genuinely exists.

**Diffusive underlyings** (crypto, indices, macro levels):
- GBM digital: `P(X≥K) = N(d₂)` — the baseline.
- Merton jump-diffusion for crypto, because BTC/ETH tails are not lognormal
  and a pure GBM will systematically underprice the wings the ladder shows.

**Sports** (`KXMLBGAME`, `KXNFLGAME`, `KXNCAAFGAME`, …): **no diffusion
exists.** A game is a score-state process, so forcing `N(d₂)` onto it is a
category error. These get a separate Markov engine:
- Soccer/hockey: Poisson goal arrivals, per-team rates, giving
  `P(home wins)`, `P(draw)`, and the totals ladder in one model.
- Baseball: inning/base/out state Markov chain.
- The output is a win probability and a totals distribution comparable
  directly against the listed ladder.

Sports carry the deepest books on the exchange (`KXMLBGAME` alone showed
15.0M contracts of 24h volume), which is why they are in scope despite
needing their own model and their own validation.

---

## 5. Architecture

Six modules, each independently testable, following the repo's existing
file-per-responsibility pattern.

| file | responsibility |
|---|---|
| `agent/ladder.py` | event → structure-classified strike ladder |
| `agent/arbitrage.py` | the §2 constraint table, fee-adjusted |
| `agent/density.py` | CDF → pdf → moments → implied-vol smile |
| `agent/pricing.py` | GBM and Merton digitals |
| `agent/sports_model.py` | Poisson / Markov score-state engine |
| `graphs/pricing_graph.py` | LangGraph `StateGraph` wiring the above |
| `graphs/tuning_graph.py` | LangGraph hyperparameter search |

`agent/ladder.py` is the seam that keeps §1's lesson enforced: nothing
downstream sees a raw event, only a ladder that already knows its structure.

**Dependencies.** `langgraph`, `langchain-core 0.3.84`, `scipy 1.17.1` and
`numpy 2.3.5` are already installed in this environment, so the fund spec's
"no new third-party dependencies" constraint is satisfied without
exception — but `requirements.txt` must be updated to declare them, since
they are now load-bearing rather than incidental.

---

## 6. LangGraph integration

**Pricing graph** — a `StateGraph` over a typed `PricingState`:

    ingest → classify_structure → arb_scan
       ├─ violation clears fees ─→ size_and_stop      (no forecast needed)
       └─ otherwise ─────────────→ density → implied_vol → fair_value
                                      → risk_check → decide

The conditional edge after `arb_scan` is the point of using a graph at all: a
genuine arbitrage short-circuits every model downstream, because it needs no
view. `risk_check` calls the existing `ru_per_contract` / `size_position`
and honours both hard refusals.

**Tuning graph** — fan-out/fan-in over configurations:

    propose_configs → [evaluate ×N in parallel] → score → select → persist

Evaluation is walk-forward on recorded ladders, never in-sample.

**No LLM sits inside the mathematics.** LangGraph is the orchestrator and
the state machine; every node is deterministic numerics. This keeps each
node unit-testable without a model call and keeps results reproducible.

---

## 7. Hyperparameters

| parameter | grid | tuned against |
|---|---|---|
| density smoothing window | 1, 3, 5, 7 strikes | out-of-sample density likelihood |
| smoothing method | none, moving average, isotonic | monotonicity violations introduced |
| implied-vol solver tolerance | 1e-4 … 1e-8 | convergence rate vs runtime |
| realized-vol estimator | close-close, Parkinson, Garman-Klass, Yang-Zhang | RMSE vs next-period realized |
| realized-vol window | 5, 15, 30, 60 min | same |
| jump intensity λ, jump size σ_J | coarse grid | wing fit on crypto ladders |
| arb edge threshold | 0.5c … 5c above fee | precision of flagged violations |

**Isotonic regression is the notable one:** it is the only smoother that
cannot introduce a monotonicity violation, because it projects onto the
monotone cone by construction. A moving average can smooth a valid CDF into
an invalid one, which would make Stage A report arbitrage the smoother
itself created.

**Selection is by Deflated Sharpe**, not raw score — the backtester already
implements it, and a grid this wide will otherwise crown noise. Train/test
split is by CLOCK, never by ladder.

---

## 8. Validation

1. **Analytic ground truth.** `N(d₂)` inversion round-trips: given σ, price a
   ladder, recover σ. Any implementation that cannot recover a σ it just used
   is wrong before it sees market data.
2. **Synthetic ladders.** Build a ladder from a known distribution; the
   recovered density must match to tolerance. Same discipline as the
   excursion-scaling fit, which recovers known exponents to ±0.05.
3. **Constraint invariance.** Smoothing must never increase the count of
   monotonicity violations.
4. **Walk-forward only.** Every hyperparameter fitted on train, scored once
   on a held-out tail.
5. **Mutation testing** on each guard, matching the standard used through
   Plan 1: if removing a check does not fail a test, the check is untested.

---

## 9. Decomposition into plans

This spec is more than one plan's work.

| plan | contents | gated on |
|---|---|---|
| **Plan A** | `ladder.py`, `arbitrage.py`, the Stage A measurement harness | nothing — start now |
| **Plan B** | `density.py`, `pricing.py`, implied-vol smile, LangGraph pricing graph | Plan A producing a clean structure-classified ladder |
| **Plan C** | `sports_model.py`, LangGraph tuning graph, full hyperparameter sweep | Plan B producing a validated density |

Only **Plan A** should be written off this spec initially. It carries no
capital risk, needs no model, and its output determines whether Stage B's
premise holds.

---

## 10. Kill criteria

- If after 30 days **no** fee-clearing arbitrage appears in any structure
  family, Stage A is retired as a strategy and kept only as a ladder
  validator.
- If recovered densities fail the synthetic round-trip, Stage B stops until
  the estimator is fixed — a wrong density is worse than none, because it
  looks authoritative.
- If the implied-vs-realized gap is not statistically distinguishable from
  the horizon-mismatch artefact described in §3, Stage B produces no trading
  signal and says so.
- If the sports Markov model cannot beat the listed ladder out-of-sample on
  Brier score, Stage C's sports branch is dropped rather than tuned further.

---

## 11. Open questions

1. **Risk-free rate.** At Kalshi tenors `e^{-rT} ≈ 1`, but for the
   `KXBTCMAXY-26DEC31` class (months out) it is not. Which curve, and does
   Kalshi's margin treatment make the relevant rate zero? Not resolved here.
2. **Underlying spot.** Inverting `N(d₂)` needs `S`. Kalshi does not publish
   it. Taking it from the ladder's own median is circular; taking it from an
   external feed adds a dependency and a latency mismatch. Plan B must
   choose and justify.
3. **American-style early settlement.** Some Kalshi markets settle early on
   determination. Whether that makes any contract meaningfully American is
   unverified.
4. **Whether any of this survives the cost floor.** Plan 1 measured a 7.18%
   round-trip cost, fee-dominated, versus a 0.185% mean directional move.
   Every signal in this document must be sized against that, and the maker
   side remains the only branch where the arithmetic is survivable.
