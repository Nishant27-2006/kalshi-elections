# Kalshi EQR Terminal — Design

**Status:** design approved in chat 2026-08-30; awaiting spec review.
**Owns:** the research panel, the pedagogy contract, the web terminal.
**Complements:** `2026-08-19-prediction-market-fund-design.md` (risk sizing,
execution gating) and `2026-08-22-options-math-on-kalshi-design.md` (pricing).
This document supersedes neither.

---

## 0. Purpose, and the constraint that shapes everything

The deliverable is not a trading system. It is a **research stack the author
can defend out loud in a Citadel EQR interview on 2026-09-09**, built by the
author rather than for him.

That single constraint drives three non-obvious choices:

1. **Strategies are written in Python, not TypeScript.** The terminal is
   TypeScript/React because the author asked for a real-time web application.
   The alpha research is Python/numpy because that is the language the room
   will ask about. Mixing them would produce a worse answer to "walk me
   through your research process."
2. **Nothing is written for the author that he should be able to write.**
   Plumbing, tests, and the terminal are delivered. Every pricing function,
   every density estimator, every alpha is his. See §4.
3. **Cross-sectional structure is forced into the design.** Kalshi is not an
   equity cross-section, and EQR is. The panel (§3) manufactures one anyway,
   so that IC, quantile spreads and neutralization are computable on real
   data rather than discussed in the abstract. This is a deliberate
   distortion of the venue to serve the learning goal, and it is stated here
   so it is never mistaken for a claim about how Kalshi is best traded.

## 1. Measured baseline — what is already known, and not to be re-litigated

Carried forward from `2026-08-22-options-math-on-kalshi-design.md`, all
measured against the live API:

| scan | universe | result |
|---|---|---|
| Ladder monotonicity (`ask(Kᵢ) < bid(Kᵢ₊₁)`) | 10 live ladders | **0 violations** |
| Binary put-call parity (`YES_ask + NO_ask < 100c`) | 285 events | **0 violations** |
| Partition sum (`Σ bid > 1`, exclusive events only) | 300 events | **1**, worth **−2.2c net of fees** |

And from `AGENT.md`: momentum-chasing loses at every trigger from 3c to 10c
(n=123), and the loss *worsens* as the trigger rises. Kalshi's short-horizon
signature is mean-reverting.

**Design consequence.** There is no model-free arbitrage to harvest. An
arbitrage scanner is therefore specified in §2.6 as a **validator** — it
proves a fitted density is arbitrage-free before anything trades off it —
and explicitly not as a source of alpha. The alpha is model-based (§2.3–2.5)
and cross-sectional (§3).

## 2. Measured this session (2026-08-30)

New findings that change the plumbing:

**2.1 The `/markets` endpoint is unusable for universe construction.**
Paging 15,000 open markets returned `KXMVECROSSCATEGORY-SHARD1-*` combo
contracts and nothing else — every one, across 15 pages. All twelve sampled
returned **zero candlesticks**. Sorting the universe by volume therefore
selects entirely untradeable synthetic shards with no price history.

**2.2 `/events?with_nested_markets=true` is the correct enumeration.**
1,200 open events carrying 8,291 real markets, with real volume
(`KXPRESNOMD-28`: 207M) and ladders of 5–82 strikes.

**2.3 The book recorder works unauthenticated.** `book_recorder.py` writes
~1,300 rows per sweep across 8 seeded series. Launched 2026-08-30 at a
300-second interval for 3,000 sweeps (≈10 days) into
`state/eqr_panel.jsonl`. **This is the data spine and it is time-critical:
history not recorded is history that cannot be recovered.**

Operational note, learned the hard way: a `nohup … &` launch from Git Bash on
Windows dies when its wrapper shell exits — the first launch recorded exactly
one sweep and stopped. The recorder must be started detached via PowerShell
`Start-Process -WindowStyle Hidden -PassThru`, with the PID written to
`state/recorder.pid` so liveness is checkable. Verify with
`Get-Process -Id (Get-Content state/recorder.pid)` and by confirming
`state/eqr_panel.jsonl` is still growing; a stalled recorder is silent.

## 3. Architecture

Three new packages inside the existing repository, reusing `kalshi_client.py`,
`agent/digital.py`, `agent/ladder.py`, `agent/risk_unit.py` and
`momentum_filter.py`'s structure classifiers.

```
eqr/                    research core (Python)
  universe.py           combo exclusion + point-in-time liquidity screen
  panel.py              point-in-time cross-sectional panel
  gbm.py            ★   Brownian motion, GBM paths, Monte-Carlo pricer
  surface.py        ★   implied-vol inversion; the two-root problem
  greeks.py         ★   digital delta/vega/gamma, MC-verified
  density.py        ★   ladder → risk-neutral PDF, moments
  signals/base.py       Signal protocol (delivered)
  signals/alpha_*.py ★  every alpha
  evaluate.py           IC, IC decay, quantile spread, t-stat, deflated Sharpe
  costs.py              0.07·P(1−P) fee + spread + impact
  noarb.py              monotonicity / parity / partition validator
server/                 FastAPI + WebSocket (delivered)
terminal/               Vite + React + TypeScript (delivered)
drills/                 day01..day09 — concept .md + failing tests
```

★ = written by the author. Delivered items are plumbing, tests and UI.

**Module contracts.** Every ★ module is pure and I/O-free, so its tests run
without an API key — the same discipline `agent/digital.py` already follows.
`panel.py` is the only module permitted to know about time, and it is the
only place lookahead bias can be introduced; that is why it is isolated.

### 3.1 The panel

A point-in-time table, one row per (timestamp, market), carrying quote,
spread, open interest, structure class, ladder position, and forward
returns at 1h/4h/1d. Built only from `state/eqr_panel.jsonl` snapshots at or
before `t`. Forward returns are joined from strictly later snapshots and are
never visible to a signal.

**Success criterion:** a deliberately planted lookahead signal must score an
IC near 1.0 in a broken panel and near 0.0 once `panel.py` is correct. This
test ships before `panel.py` does.

### 3.2 Universe construction

Exclude `KXMVECROSSCATEGORY`. Apply a liquidity screen using only
information available at `t`. The screen is a research decision with a
survivorship trap attached, and the drill (§5, Day 1) is to find that trap
before it is explained.

## 4. The pedagogy contract

Each day runs three phases in fixed order.

- **DRILL** — derive by hand, no code.
- **BUILD** — failing tests are delivered encoding the specification; the
  author makes them pass. Questions are answered; bodies are not written.
- **DEFENSE** — adversarial interrogation at full Citadel-superday intensity
  (the author's explicit choice): lookahead, survivorship, multiple testing,
  cost naivety, statistical significance. Hand-waving is not accepted and
  the day does not close until the result is defended or fixed.

## 5. Curriculum — 2026-08-30 through 2026-09-08

Ordered to front-load the mathematics (author's explicit choice) while the
recorder accumulates panel history behind it.

| Day | Drill | Author builds |
|---|---|---|
| 1 | Brownian motion, quadratic variation, Itô intuition | `gbm.py` — GBM paths + Monte-Carlo digital pricer |
| 2 | Digital price **is** `N(d₂)`; why vol inversion has two roots | `surface.py` |
| 3 | Greeks; why digital vega changes sign at the strike | `greeks.py`, verified against his own MC |
| 4 | Discrete Breeden–Litzenberger; negative density = arbitrage | `density.py` |
| 5 | Universe construction, survivorship, point-in-time | `universe.py`, `panel.py` |
| 6 | Cross-sectional alpha, IC, IC decay, Fundamental Law | `alpha_01`, `alpha_02` |
| 7 | Costs, turnover, capacity — why a 3-Sharpe backtest nets zero | `costs.py`, capacity curve |
| 8 | Factor exposure, neutralization, deflated Sharpe | `alpha_03`, neutralized |
| 9 | Mock superday | defends everything |

**Convergence gate, Day 1→3.** The Monte-Carlo pricer in `gbm.py` must
reproduce `agent/digital.py`'s closed-form `N(d₂)` to within Monte-Carlo
error. Two independent implementations agreeing is the only evidence either
is right, and it is the author's first real result.

## 6. The terminal

Vite + React + TypeScript. FastAPI serves the panel; a WebSocket pushes
quote updates. Panels: Universe, Ladder, Density, Surface, Alpha, Backtest,
Risk, Drill. The Density and Surface panels render the author's own
`density.py` and `surface.py` output — the terminal is a lens on his code,
which means a bug in his math is visible as a malformed curve rather than a
silent number.

## 7. Risks and open questions

1. **Panel history may be too short by Day 6.** Ten days at 300s gives ~2,900
   snapshots per market, which is ample intraday but thin for daily
   cross-section. Mitigation: horizons are 1h/4h/1d, not daily.
2. **Kalshi's WebSocket requires authentication.** The author's key is not
   yet installed. Mitigation: the terminal polls REST until the key exists;
   the feed interface is identical either way.
3. **Forward returns on expiring contracts are contaminated by resolution.**
   Markets settling inside the forward window resolve to 0 or 1, which is a
   real return but not a tradeable one. `panel.py` must flag and exclude
   them, and the drill on Day 5 is to notice this unaided.
4. **Cross-sectional structure is synthetic** (§0.3). Stated, not hidden.

## 8. Out of scope

Order placement. The existing risk gate (`agent/risk.py`) and the fund
design own live execution, and nothing in this document authorises trading
real money.
