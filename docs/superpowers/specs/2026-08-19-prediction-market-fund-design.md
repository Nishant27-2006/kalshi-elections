# Prediction-Market Fund — Design

**Date:** 2026-08-19
**Status:** approved in brainstorming; not implemented
**Repo baseline at time of writing:** 556 tests passing, `is_live=False`,
vault 277 notes / 28 hubs, 223 logged findings.

---

## 1. Purpose

Deploy real capital on Kalshi using the knowledge graph already built in this
repo as the primary asset, with a small, heavily-validated quantitative layer
on top. The knowledge graph is not decoration — it decides what is tradeable
at all, and it is fast enough to sit in the execution path (measured 0.15 ms
per retrieval, ~6,600/sec, CPU-only, no embeddings).

**Design constraints stated by the operator:**

- The knowledge/understanding layer is the valuable part. Change it as little
  as possible; build the quantitative layer *around* it.
- Low compute budget. No GPU, no large models, no deep RL stack.
- The system should improve from its own trading, and hyperparameters should
  be tuned rather than hand-set.
- Target a good Sharpe ratio, validated with train/test discipline.

## 2. Non-goals

- **Not** a high-frequency system. Kalshi books are thin and spreads are wide
  (measured 5–9¢ on deep futures books, 14–17¢ on NFL season props, 23–79¢ on
  illiquid court rungs). Turnover is a cost, not a virtue.
- **Not** a deep-RL agent. Sample counts are 10–50 trades/week; RL that needs
  thousands of episodes cannot be validated here and will fit noise.
- **Not** an attempt to trade every vertical. Capacity is limited and most of
  the board is dormant.

---

## 3. The evidence base

This design starts from measurements already in the repo, including a negative
one that reverses the original premise.

### 3.1 Momentum loses, and the sign is backwards

From `AGENT.md`, measured on live Florida election data:

> "Median P&L was negative at 1h and 4h in *every* config, and **raising the
> trigger made results worse** — the signature of mean reversion, not
> momentum."

| trigger | n | win rate | total P&L |
|---|---|---|---|
| ≥8¢ | 25 | 28.0% | −$14.61 |
| ≥10¢ | 24 | 33.3% | −$13.50 |

The worst single case, `KXDROPOUTPRIMARY-26-MMIL2`, ran 25¢ → 52¢ → 47¢ → **1¢
(resolved NO)**, returning **−$48.51 at a 17% win rate**. With risk caps
enabled the stateful win rate went **16.3% → 0.0%** while total loss halved —
the caps were doing risk control, not alpha selection.

A `+$217 / 75.6% win rate` long-horizon figure exists and is **an artifact**:
the winners had already resolved to 1¢/99¢, so it measures holding to expiry,
not edge. Any backtest reporting long-horizon win rates on resolved contracts
is measuring survivorship.

**Consequence for this design:** momentum is the null hypothesis, not the
thesis. Mean reversion and structural edges are tested against it.

### 3.2 Abandonment risk is real, measurable, and vertical-specific

The settled feed carries a third `result` value, `scalar`, marking a
settlement at an exchange-set price rather than YES/NO. Measured event-level
rates:

| vertical | void rate |
|---|---|
| scheduled data (charts, daily crypto ladders, index sessions) | 0% |
| MLB games | 0.5% |
| MLB player legs (per leg) | 0.9% |
| UFC method of victory | 1.7% |
| ATP matches | 3.7% |
| WTA matches | 4.0% |
| tennis games ladder | 5.3% |
| UFC bouts | 7.1% |
| CS2 esports series | 9.9% |

Two structural notes that matter for sizing:

- **The unit matters.** `KXMLBHR` voids 13.9% of *events* but only 0.9% of
  *player legs*, because a game lists ~34 hitters. Quoting the event rate
  against a single position overstates risk ~15×.
- **Abandonment is a property of the question, not the match.** The tennis
  games ladder voids 5.3% against the match-winner's 3.7% *on the same sport*,
  because a retirement still determines a winner but not a completed games
  count. The finer the quantity, the more often partial play cannot settle it.

### 3.3 Structure must be known before a book can be read

Seven contract structures are now classified, and misreading one produces a
confidently wrong number:

`exclusive_field` · `threshold_ladder` · `two_sided_handicap` ·
`independent_basket` · `fixed_cardinality` · `standalone_binary` ·
`disputed`/`indeterminate`

Two are empirically validated against settled outcomes:

- **fixed cardinality** — 20 settled NASCAR top-10 races, exactly 10 YES legs
  every time, zero variance, against `KXRAIN`'s 4.17-and-varying.
- **two-sided handicap** — 55 of 67 live spread series, **3.26M open
  interest**, previously read as either a ladder or a basket.

### 3.4 Price history is thin, and worst where liquidity is best

| series | 30d hourly candles |
|---|---|
| `KXALIENS` (long-dated) | 555 |
| `KXCPIYOY` (monthly) | 116 |
| `KXNFLSPREAD` (3-day-old book) | 40 |
| `KXBTCD` (daily ladder) | **0** |

**The markets with the most tradeable flow leave the least history.** Any
backtest built only on available candles is biased toward slow, thin,
long-dated contracts. This is a distinct survivorship problem from §3.1 and it
is the single largest threat to the research program.

---

## 4. Architecture

Five components, each independently testable.

```
                    ┌─────────────────────────┐
   contract ticker  │  Contract-Keyed         │
   ───────────────► │  Retrieval (KG)         │ 0.15 ms
                    │  structure, void rate,  │
                    │  settlement source,     │
                    │  spread regime, related │
                    └───────────┬─────────────┘
                                │ context
                    ┌───────────▼─────────────┐
                    │  Estimator              │
                    │  p̂₀ (base rate)         │
                    │  p̂₁ (with context)      │
                    └───────────┬─────────────┘
                                │ p̂₁
                    ┌───────────▼─────────────┐     ┌──────────────────┐
                    │  Risk Unit Sizer        │◄────┤  Risk Budget     │
                    │  N contracts from RU    │     │  (NOT tunable)   │
                    └───────────┬─────────────┘     └──────────────────┘
                                │ order
                    ┌───────────▼─────────────┐
                    │  Execution (is_live-    │
                    │  gated, IOC only)       │
                    └───────────┬─────────────┘
                                │ fill + outcome
                    ┌───────────▼─────────────┐
                    │  Learner                │
                    │  · calibration reward   │
                    │  · note posteriors      │
                    │  · contextual bandit    │
                    └─────────────────────────┘
```

### 4.1 Contract-keyed retrieval

A small extension of the existing `VaultGraph.retrieve_context`, which today
takes a headline. Trading needs the inverse: given a **ticker**, return the
note set and the machine-readable facts (structure, void rate, settlement
source, typical spread, related markets).

This is the only change to the knowledge layer, and it is additive — existing
headline retrieval is untouched.

### 4.2 Estimator

Deliberately simple. Produces two probabilities per candidate:

- `p̂₀` — base rate for the archetype, from the measured historical analogs
  (e.g. 49.9% for a 15-minute crypto binary, 46.0% KO/TKO for UFC method).
- `p̂₁` — `p̂₀` adjusted by the retrieved context.

The gap between them is what the learner scores. If context never improves on
the base rate, the knowledge layer is not earning its place and we should know
that quickly.

### 4.3 Risk Unit sizer

See §5.

### 4.4 Execution

Reuses the existing order path unchanged: `translate_side`,
`build_order_payload`, IOC time-in-force, `is_live()` gate. No resting-order
manager exists, so no GTC.

### 4.5 Learner

See §7.

---

## 5. The Risk Unit (RU)

"Risk 1% per trade" is meaningless on a binary: buying at 3¢ and at 60¢ with
equal dollars are entirely different risks. The unit is therefore **expected
adverse excursion**, not notional.

**1 RU = $1 of expected adverse move over the holding period.**

For `N` contracts entered at price `p` (dollars, 0–1), on the YES side:

```
RU = N·p·2σ                  volatility-scaled capital at risk, σ = √(p(1−p))
   + N·(½·spread + fee)      certain round-trip cost
   + N·p·v                   abandonment haircut, v = measured void rate
```

For a NO-side entry, substitute `(1−p)` for `p` in the first and third terms.

**Term by term:**

- **σ = √(p(1−p))** is the per-contract standard deviation of a binary,
  maximal at 50¢ and negligible at the extremes. This is what makes a 60¢
  position count more per dollar than a 3¢ one. The `2σ` multiplier is the
  planned adverse traverse and is itself a tuned hyperparameter (§7.4).
- **Spread** is not a rounding error at these widths and can exceed any
  plausible edge on an illiquid book.
- **`v`** is the measured void rate for the vertical (§3.2), at the correct
  unit (per leg for player props, per event for match books). This term has no
  analogue in standard position sizing and is specific to this venue.

**Portfolio aggregation.** Positions sharing an *event*, a *settlement
source*, or the two sides of one handicap are not independent:

- **within a cluster:** sum RU linearly (no diversification credit)
- **across clusters:** √-sum

Justification is in the vault: Alcaraz priced 61¢ to compete and 19¢ to win is
one position, not two.

**Two hard refusals, not size adjustments:**

1. **Sub-3¢ positions.** A percentage stop is sub-tick there (50% of 1.3¢ is
   not a price level). These are hold-to-resolution — premium spent, not a
   position managed.
2. **Unknown structure.** Anything classified `disputed`, `indeterminate`, or
   carrying a cardinality-mismatch note. If the exposure is not known, it
   cannot be sized.

---

## 6. Data plan

Two tracks, started simultaneously.

**Track 1 — backtest on what exists.** Long-lived markets only, with the
§3.4 bias stated explicitly in every result. Never report a backtest number
without naming the sample's survivorship character.

**Track 2 — start recording now.** Poll and persist the order book for a
watchlist of liquid series (daily crypto ladders, per-game sports, chart
markets) at fixed intervals. This is the only way the fast books become
backtestable, and every week of delay is a week of data not collected.

Recording is cheap, has no risk, and should begin before any capital is
deployed.

---

## 7. Research protocol

### 7.1 Walk-forward, never a single split

Expanding-window walk-forward. Fit on `[t₀, tᵢ]`, test on `[tᵢ, tᵢ₊₁]`,
advance. Report the **distribution** of out-of-sample results across folds,
never the best fold.

### 7.2 Deflated Sharpe Ratio is the acceptance test

A naive Sharpe from a short sample with many trials is not evidence. Every
reported Sharpe is accompanied by its **Deflated Sharpe Ratio**, which
discounts for the number of configurations tried and the sample length.

- Record the **trial count** honestly. Every configuration evaluated counts,
  including abandoned ones.
- **Acceptance threshold:** DSR > 0.95 (i.e. ≥95% probability the true Sharpe
  exceeds zero) on out-of-sample folds.
- A strategy that cannot clear this does not get capital, regardless of how
  good its raw Sharpe looks.

### 7.3 Risk-model validation is separate from alpha validation

These are different questions and conflating them is a common failure:

- **Alpha validation** — does the signal predict direction?
- **Risk validation** — does a position sized at 1 RU actually realise ~$1 of
  adverse excursion out-of-sample?

Risk validation needs **no alpha at all**. Calibrate on systematic or random
entries and check realised vs predicted adverse excursion per vertical. If the
void term is right, esports positions should breach their RU ~10% of the time
and MLB games ~0.5% — directly falsifiable.

**A calibrated risk model is worth more than an uncalibrated alpha model**,
because it is what keeps the account solvent during the search.

### 7.4 Hyperparameters

Kept deliberately few. Initial set:

| parameter | role | search |
|---|---|---|
| `sigma_multiple` | the `2σ` traverse in RU | coarse grid 1.0–3.0 |
| `ru_budget_pct` | RU per trade as % of NAV | coarse grid 0.25–2.0, **capped** |
| `min_edge` | required p̂₁ − market price to act | coarse grid |
| `max_spread` | refuse books wider than this | coarse grid |

Re-fit **monthly on an expanding window**, not continuously. Continuous
self-tuning at 10–50 trades/week fits noise.

**Two tuning loops, and only one of them is automatic.** These must not be
confused (see §9.1):

| loop | who runs it | may change |
|---|---|---|
| **online learner** | automatic, every trade | note weights, bandit arm posteriors |
| **offline re-fit** | monthly, human-approved | the four parameters above |

`ru_budget_pct` is tuned only in the offline loop, only within a hard ceiling
set outside the search space, and only with a human approving the promotion.
The online learner can never change it in either direction.

---

## 8. The learning layer

### 8.1 Reward on calibration, not P&L

A binary outcome is one bit and most of that bit is variance. Rewarding notes
on P&L amplifies luck and creates a positive feedback loop on variance.

Instead, score on whether the retrieved context **improved the probability
estimate**, using a proper scoring rule:

```
reward(note) = Brier(p̂₀, outcome) − Brier(p̂₁, outcome)
```

This has far lower variance than P&L, which is what makes it usable at
achievable sample sizes. P&L is the consequence; calibration is the teacher.

### 8.2 Note-influence posteriors

Each note carries a posterior over its calibration contribution with a
**skeptical prior** (default: no influence). A note must earn weight across
many observations. This is the specific mechanism preventing one lucky trade
from rewriting the graph.

Notes are **never deleted** by the learner. A note whose influence decays to
zero stops being weighted but remains retrievable — removing it would destroy
the context that may explain the next loss.

### 8.3 Contextual bandit, not RL

Arms are discrete choices (archetype family, sizing regime). **Thompson
sampling** over Bayesian posteriors handles small samples natively and
explores without collapsing onto early luck. Cost is microseconds.

### 8.4 Champion / challenger

A frozen configuration trades. A challenger must beat it out-of-sample by a
stated margin, with DSR clearing §7.2, before promotion. No silent drift.

---

## 9. Guardrails

These are invariants, extending the existing hard invariants in the repo.

1. **The learner cannot widen its own leash.** The *online* learner (§8) may
   change note weights and bandit posteriors only. Risk caps, the hard RU
   ceiling, and the execution gate are outside its reach entirely. A
   self-improving system able to raise its own position limits will eventually
   discover that doing so improves its objective.
   `ru_budget_pct` may be revised **only** by the monthly offline re-fit
   (§7.4), only inside a ceiling that is not itself a search parameter, and
   only with human approval of the promotion. The distinction is the whole
   guardrail: automatic learning adjusts *beliefs*, never *limits*.
2. **Shadow mode first.** The learner updates weights but does not size trades
   until its calibration is validated out-of-sample.
3. **Execution gate unchanged.** No order reaches the wire unless
   `RISK.is_live()`. `env=demo` plus `execution_enabled` must not transmit.
4. **No invented data.** Unchanged from the existing invariant K: if a fact is
   not in the API response or the vault, it is "unverified" and cannot enter a
   position rationale.
5. **Secrets.** RSA key local only, env vars only, never committed.

---

## 10. Staged rollout

**Stage C — structural / relative value (first live capital).**
Trade only mechanical inconsistencies the knowledge graph already finds:
cardinality mismatches (the 998¢ ten-place partition), cross-market implied
conditionals, ladder monotonicity violations. **Requires essentially no price
history** — the edge is in the rulebook, not the path. Lowest capacity,
highest confidence per trade. This stage exists to validate execution plumbing
and the RU model with real fills, at small size.

**Stage A — KG-gated rules (the engine).**
The graph gates what is tradeable; a 3–4 parameter quant layer decides entry.
Tuned per §7, benchmarked against Stage C's realised results and against the
momentum null from §3.1.

**Stage B — learned model (background).**
Accrues recorded data per §6 Track 2. Not funded until it clears §7.2 on data
that did not exist when it was designed.

---

## 10a. Implementation scope — this spec needs three plans, not one

This document describes more than one implementation plan's worth of work.
Decomposed, in dependency order:

| plan | contents | gated on |
|---|---|---|
| **Plan 1** | book recorder (§6 Track 2), RU sizer (§5), RU calibration harness (§7.3) | nothing — start now |
| **Plan 2** | Stage C structural strategy (§10), execution wiring, live-gate drill | Plan 1's RU calibrating |
| **Plan 3** | learner: calibration reward, note posteriors, bandit (§8) | Plan 2 producing real fills |

Only **Plan 1** should be written and executed off this spec initially. It
carries no capital risk, and the recorder's value decays with every week it is
not running. Plans 2 and 3 get their own planning cycle once their gate is
met, informed by what Plan 1 measures.

---

## 10b. Plan 2 entry gate — MEASURED, unresolved

Plan 1 shipped and its RU calibration harness works, but running it against
a recording does NOT currently certify the risk model. Measured from the
shipped formula:

`SIGMA_MULTIPLE = 2.0` makes predicted RU EXCEED the maximum loss a YES
contract can take, so across much of the price range a breach is
arithmetically impossible rather than merely rare. The affected region
depends on the spread and is not contiguous at tight ones — `mlb_game` at a
2c spread is breachable from about 3.1c to 32c and impossible from 32c to
63.3c, while the same series on an 8c book is impossible from 3c to 69.2c.

Worse, the effect is LARGEST where discrimination matters most. A higher
void rate and wider quotes raise predicted RU, so `esports_series` has a
wider no-breach zone than `mlb_game` at every spread. Section 7.3's stated
falsifiable claim — that esports should breach more often than MLB — is
inverted by construction.

Cause: for a bounded binary, a two-sigma move is definitionally the entire
distance to settlement; at 50c the volatility term alone equals the whole
capital. No ceiling on RU repairs this. Only a smaller multiple does, and
that halves RU and therefore DOUBLES every position size.

**Decision taken 2026-08-19: leave `SIGMA_MULTIPLE` at 2.0 and document.**
No capital is at risk in Plan 1, and the error direction is conservative
(over-stated risk, under-sized positions). Per section 7.4, parameter
revision belongs to the monthly human-approved offline re-fit, not to an
agent mid-plan.

**Binding on Plan 2:** a clean calibration run at mid prices is
UNINFORMATIVE, not evidence the RU is sound. Before Plan 2 sizes anything
with real capital, either re-fit the multiple against recorded books, or
restrict RU-certified trading to the price bands where a breach is
measurable. Do not read section 7.3's output as a green light until one of
those has happened.

---

## 11. Kill criteria

Stated before any capital is deployed, so they cannot be rationalised away
later.

- **Risk model fails calibration.** If realised adverse excursion diverges
  from RU prediction by >50% on any vertical over ≥100 positions, stop
  trading that vertical and re-derive.
- **Alpha fails DSR.** Any strategy whose out-of-sample DSR falls below 0.95
  over a full re-fit cycle is retired, not re-tuned.
- **Drawdown.** A drawdown exceeding the pre-set NAV limit halts all trading
  pending human review — not automatic resizing.
- **Learner divergence.** If champion and challenger disagree on sizing by
  more than a stated factor, freeze the learner and review.
- **The null wins.** If, after a full cycle, a flat "do nothing" baseline
  outperforms the deployed strategy net of costs, the fund stops. This is the
  most likely outcome and must be treatable as an ordinary result.

---

## 12. Open questions

1. **Capital size and capacity.** Not yet specified by the operator. Kalshi
   book depth caps deployable size per market; this determines whether Stage C
   alone can absorb the intended capital.
2. **Fee schedule.** Kalshi's exact maker/taker fees must be read and encoded
   in the cost model; the RU spread term currently carries a placeholder.
3. **Tax and account structure.** Out of scope for this document.
4. **Regulatory posture.** Trading own capital only. Managing outside money
   would be a different undertaking with different obligations and is
   explicitly out of scope here.

---

## 13. What this design deliberately does not promise

The evidence in §3.1 is that the strategy family originally proposed loses
money on this venue, and the most likely outcome of a disciplined research
program is that **no deployable edge is found**. Every acceptance gate in this
document is built so that outcome is detected early and cheaply rather than
discovered through drawdown.
