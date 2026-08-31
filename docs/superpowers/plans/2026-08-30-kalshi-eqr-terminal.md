# Kalshi EQR Terminal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real-time Bloomberg-style Kalshi terminal over a Python research core, where the human author writes every pricing model and every alpha himself against delivered failing tests, in time to defend the work at a Citadel EQR superday on 2026-09-09.

**Architecture:** A Python research package (`eqr/`) reuses the repo's existing `kalshi_client.py`, `agent/digital.py`, `agent/ladder.py` and `agent/risk_unit.py`. A FastAPI service (`server/`) exposes the panel and streams quotes over WebSocket. A Vite + React + TypeScript terminal (`terminal/`) renders it. The `eqr/` modules marked ★ are written by the human; everything else is delivered to him.

**Tech Stack:** Python 3.13, numpy 2.3.5, scipy 1.17.1, pytest 9.0.3, FastAPI + uvicorn, Node 22.19.0, Vite, React 18, TypeScript 5, lightweight-charts.

**Spec:** `docs/superpowers/specs/2026-08-30-kalshi-eqr-terminal-design.md`

## Global Constraints

- **Ownership is absolute.** Files marked ★ are written by the human author. An executing agent writes their *tests* and their *docstring contract*, never their bodies. If a ★ file would be left non-functional, that is correct and intended.
- **★ modules are pure.** No network, no file I/O, no global state. Their tests must pass with no API key and no internet.
- **Fee model is fixed:** `agent/risk_unit.fee_per_contract(price) = 0.07 * price * (1 - price)`, price in dollars, charged `FEE_LEGS = 2` times per round trip. Never re-derive it, never use a flat placeholder.
- **Universe enumeration is `/events?with_nested_markets=true`.** Never `/markets` — it returns only `KXMVECROSSCATEGORY` combo shards with zero candlesticks.
- **Exclude any ticker starting with `KXMVECROSSCATEGORY`** from every universe, always.
- **Prices from the API are dollar-strings with a `_dollars` suffix; quantities carry `_fp`.** Bare `yes_bid` / `volume` read as `None`.
- **Recorder must stay alive.** Started detached via PowerShell `Start-Process -WindowStyle Hidden`, PID in `state/recorder.pid`. A `nohup … &` launch from Git Bash dies silently.
- **Refinement on the spec (§3):** the spec listed `eqr/evaluate.py` as delivered. This plan moves its two core statistics — `information_coefficient()` and `quantile_spread()` — to ★, because computing an IC by hand is the single highest-value thing the author learns on Day 6. The surrounding harness (loading, reporting, plotting) stays delivered.

---

## File Structure

| File | Owner | Responsibility |
|---|---|---|
| `eqr/__init__.py` | delivered | package marker |
| `eqr/gbm.py` | ★ author | Brownian motion, GBM paths, Monte-Carlo digital pricer |
| `eqr/surface.py` | ★ author | implied-vol inversion across a ladder; two-root handling |
| `eqr/greeks.py` | ★ author | digital delta/vega/gamma by finite difference, MC-verified |
| `eqr/density.py` | ★ author | ladder → risk-neutral PDF, moments |
| `eqr/universe.py` | ★ author | combo exclusion + point-in-time liquidity screen |
| `eqr/panel.py` | ★ author | point-in-time cross-sectional panel with forward returns |
| `eqr/signals/base.py` | delivered | `Signal` protocol |
| `eqr/signals/alpha_*.py` | ★ author | every alpha |
| `eqr/evaluate.py` | mixed | IC/quantile core ★; harness delivered |
| `eqr/costs.py` | ★ author | fee + spread + impact, capacity curve |
| `eqr/noarb.py` | delivered | no-arbitrage validator |
| `eqr/loader.py` | delivered | reads `state/eqr_panel.jsonl` into records |
| `server/app.py` | delivered | FastAPI routes |
| `server/feed.py` | delivered | REST poll → WebSocket broadcast |
| `terminal/` | delivered | Vite + React + TS terminal |
| `drills/dayNN-*.md` | delivered | concept drill, derived by hand before coding |
| `tests/eqr/test_*.py` | delivered | the failing tests the author turns green |

---

## Task 0: Scaffold — toolchain, packages, and a terminal that renders live Kalshi data

Proves the TypeScript actually runs before any math depends on it.

**Files:**
- Create: `eqr/__init__.py`, `eqr/loader.py`, `server/app.py`, `server/feed.py`, `terminal/` (Vite scaffold), `requirements-eqr.txt`
- Test: `tests/eqr/test_loader.py`

**Interfaces:**
- Consumes: `book_recorder.snapshot_from_market`, `state/eqr_panel.jsonl`
- Produces: `eqr.loader.load_snapshots(path) -> list[dict]`, `eqr.loader.latest_by_ticker(rows) -> dict[str, dict]`; FastAPI routes `GET /api/universe`, `GET /api/ladder/{event_ticker}`, `WS /ws/quotes`

- [ ] **Step 1: Install the missing Python deps**

```bash
cd "C:/Users/nisha/Desktop/kalshi-elections"
python -m pip install fastapi "uvicorn[standard]" websockets
python -c "import fastapi,uvicorn;print('ok',fastapi.__version__)"
```

- [ ] **Step 2: Write the failing loader test**

```python
# tests/eqr/test_loader.py
import json
from pathlib import Path
from eqr import loader


def test_load_snapshots_reads_jsonl(tmp_path: Path):
    p = tmp_path / "snap.jsonl"
    rows = [
        {"ts": 100, "series": "KXBTCD", "ticker": "KXBTCD-26AUG3101-T87299.99",
         "event_ticker": "KXBTCD-26AUG3101", "yes_bid_c": 40.0,
         "yes_ask_c": 42.0, "spread_c": 2.0, "oi": 10.0, "v24": 5.0},
        {"ts": 200, "series": "KXBTCD", "ticker": "KXBTCD-26AUG3101-T87299.99",
         "event_ticker": "KXBTCD-26AUG3101", "yes_bid_c": 41.0,
         "yes_ask_c": 43.0, "spread_c": 2.0, "oi": 11.0, "v24": 6.0},
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    got = loader.load_snapshots(p)
    assert len(got) == 2
    assert got[0]["ts"] == 100


def test_latest_by_ticker_keeps_newest(tmp_path: Path):
    rows = [
        {"ts": 100, "ticker": "A", "yes_bid_c": 1.0},
        {"ts": 200, "ticker": "A", "yes_bid_c": 9.0},
        {"ts": 150, "ticker": "B", "yes_bid_c": 3.0},
    ]
    latest = loader.latest_by_ticker(rows)
    assert latest["A"]["yes_bid_c"] == 9.0
    assert latest["B"]["yes_bid_c"] == 3.0


def test_load_snapshots_skips_malformed_lines(tmp_path: Path):
    p = tmp_path / "snap.jsonl"
    p.write_text('{"ts":1,"ticker":"A"}\nNOT JSON\n{"ts":2,"ticker":"B"}\n')
    got = loader.load_snapshots(p)
    assert [r["ticker"] for r in got] == ["A", "B"]
```

- [ ] **Step 3: Run it and confirm it fails**

Run: `python -m pytest tests/eqr/test_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eqr'`

- [ ] **Step 4: Implement the loader**

```python
# eqr/loader.py
"""Reads the book recorder's JSONL into memory.

A malformed line is SKIPPED, not fatal. The recorder appends while this
reads, so a torn final line is normal and must never abort a research run.
"""
from __future__ import annotations

import json
from pathlib import Path


def load_snapshots(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def latest_by_ticker(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in rows:
        t = r.get("ticker")
        if t is None:
            continue
        prev = out.get(t)
        if prev is None or r.get("ts", 0) > prev.get("ts", 0):
            out[t] = r
    return out
```

- [ ] **Step 5: Run tests and confirm they pass**

Run: `python -m pytest tests/eqr/test_loader.py -v`
Expected: 3 passed

- [ ] **Step 6: Write the FastAPI service**

```python
# server/app.py
"""FastAPI over the recorder file and the live Kalshi REST API.

No API key required: every endpoint used here is public. The WebSocket
polls REST and broadcasts deltas, so the client-side interface is identical
whether or not an authenticated Kalshi socket is available later.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from eqr import loader

REPO = Path(__file__).resolve().parents[1]
PANEL = REPO / "state" / "eqr_panel.jsonl"

app = FastAPI(title="Kalshi EQR Terminal")
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:5173"],
    allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    exists = PANEL.exists()
    n = sum(1 for _ in open(PANEL, encoding="utf-8")) if exists else 0
    return {"ok": True, "panel_rows": n, "panel_path": str(PANEL)}


@app.get("/api/universe")
def universe(limit: int = 400) -> dict:
    rows = loader.load_snapshots(PANEL) if PANEL.exists() else []
    latest = loader.latest_by_ticker(rows)
    out = [r for r in latest.values()
           if not r.get("ticker", "").startswith("KXMVECROSSCATEGORY")]
    out.sort(key=lambda r: -(r.get("v24") or 0))
    return {"count": len(out), "markets": out[:limit]}


@app.get("/api/ladder/{event_ticker}")
def ladder(event_ticker: str) -> dict:
    rows = loader.load_snapshots(PANEL) if PANEL.exists() else []
    latest = loader.latest_by_ticker(rows)
    rungs = [r for r in latest.values()
             if r.get("event_ticker") == event_ticker]
    rungs.sort(key=lambda r: r.get("ticker", ""))
    return {"event_ticker": event_ticker, "rungs": rungs}


@app.websocket("/ws/quotes")
async def ws_quotes(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            rows = loader.load_snapshots(PANEL) if PANEL.exists() else []
            latest = loader.latest_by_ticker(rows)
            payload = [r for r in latest.values()
                       if not r.get("ticker", "").startswith("KXMVECROSSCATEGORY")]
            payload.sort(key=lambda r: -(r.get("v24") or 0))
            await ws.send_text(json.dumps({"markets": payload[:200]}))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
```

- [ ] **Step 7: Verify the server boots and answers**

```bash
cd "C:/Users/nisha/Desktop/kalshi-elections"
python -m uvicorn server.app:app --port 8000 &
sleep 4
curl -s http://localhost:8000/api/health
curl -s "http://localhost:8000/api/universe?limit=3"
```

Expected: `{"ok":true,"panel_rows":<n>,...}` with `n > 2000`, and three markets.

- [ ] **Step 8: Scaffold the TypeScript terminal**

```bash
cd "C:/Users/nisha/Desktop/kalshi-elections"
npm create vite@latest terminal -- --template react-ts
cd terminal && npm install && npm install lightweight-charts
```

- [ ] **Step 9: Verify TypeScript compiles and the dev server runs**

```bash
cd "C:/Users/nisha/Desktop/kalshi-elections/terminal"
npx tsc --noEmit
npm run build
```

Expected: `tsc --noEmit` exits 0 with no output; `npm run build` writes `dist/`.

**This step is the gate.** If `tsc --noEmit` does not exit 0, Task 0 is not done.

- [ ] **Step 10: Commit**

```bash
git add eqr server terminal tests/eqr requirements-eqr.txt
git commit -m "feat(eqr): scaffold research package, FastAPI service and TS terminal"
```

---

## Task 1 (Day 1): `eqr/gbm.py` — Brownian motion and a Monte-Carlo digital pricer ★

**The author writes this file.** An executing agent delivers the tests and the drill, runs the tests to show them failing, and stops.

**Files:**
- Create: `eqr/gbm.py` (★ author), `drills/day01-brownian-motion.md` (delivered)
- Test: `tests/eqr/test_gbm.py` (delivered)

**Interfaces:**
- Consumes: `agent.digital.digital_call(forward, strike, sigma, t_years, rate=0.0) -> float | None`
- Produces:
  - `brownian_paths(n_paths: int, n_steps: int, t_years: float, seed: int) -> np.ndarray` — shape `(n_paths, n_steps + 1)`, `W[:, 0] == 0`
  - `gbm_terminal(forward: float, sigma: float, t_years: float, n_paths: int, seed: int) -> np.ndarray` — shape `(n_paths,)`
  - `mc_digital_call(forward: float, strike: float, sigma: float, t_years: float, n_paths: int, seed: int) -> tuple[float, float]` — `(price, standard_error)`

- [ ] **Step 1: Deliver the drill**

```markdown
<!-- drills/day01-brownian-motion.md -->
# Day 1 — Brownian motion, by hand, before you write code

Answer these on paper. Do not open an editor until all five are done.

1. W(t) is standard Brownian motion. Write Var[W(t) - W(s)] for t > s.
   Now write Var[W(t)] itself. Why is it linear in t and not in sqrt(t),
   when the standard deviation goes as sqrt(t)?

2. Quadratic variation. Partition [0, T] into n intervals and form
   S_n = sum (W(t_{i+1}) - W(t_i))^2. What does S_n converge to as
   n -> infinity? State the answer, then say in one sentence why this is
   the single fact that makes Ito calculus different from ordinary
   calculus.

3. Under geometric Brownian motion with zero drift under the risk-neutral
   measure, S(T) = F * exp(-0.5*sigma^2*T + sigma*W(T)). Take the
   expectation E[S(T)] and show it equals F. Explain what the -0.5*sigma^2*T
   term is doing there and what breaks if you drop it.

4. A digital call pays $1 if S(T) >= K. Show that its risk-neutral price
   with r = 0 is P(S(T) >= K), and reduce that probability to N(d2) with
   d2 = [ln(F/K) - 0.5*sigma^2*T] / (sigma*sqrt(T)).
   NOTE the sign. Compare it to the d2 in agent/digital.py:60 and account
   for any difference before you continue.

5. Monte-Carlo error. If you price this digital by simulating n paths and
   averaging an indicator, the estimator is a sample mean of a Bernoulli
   with parameter p. Write its standard error. How many paths do you need
   for a standard error below 0.001 when p is near 0.5?

Bring your answer to 5 to the build step. You will check your simulation
against it, and a run whose error does not match your formula is a bug in
the code or a bug in the formula. Find out which.
```

- [ ] **Step 2: Deliver the failing tests**

```python
# tests/eqr/test_gbm.py
"""Day 1. These fail until eqr/gbm.py exists. The author writes gbm.py.

The load-bearing test is test_mc_converges_to_closed_form: an independent
Monte-Carlo implementation agreeing with agent/digital.py's closed form is
the only evidence that either one is right.
"""
import math

import numpy as np
import pytest

from agent import digital
from eqr import gbm


def test_brownian_paths_shape_and_origin():
    W = gbm.brownian_paths(n_paths=500, n_steps=50, t_years=1.0, seed=7)
    assert W.shape == (500, 51)
    assert np.allclose(W[:, 0], 0.0)


def test_brownian_variance_grows_linearly_in_time():
    W = gbm.brownian_paths(n_paths=200_000, n_steps=4, t_years=1.0, seed=11)
    # Var[W(t)] = t, sampled at t = 0.25, 0.50, 0.75, 1.00
    for k, t in enumerate([0.25, 0.5, 0.75, 1.0], start=1):
        assert W[:, k].var() == pytest.approx(t, rel=0.02)


def test_brownian_increments_are_independent():
    W = gbm.brownian_paths(n_paths=200_000, n_steps=2, t_years=1.0, seed=13)
    d1 = W[:, 1] - W[:, 0]
    d2 = W[:, 2] - W[:, 1]
    corr = np.corrcoef(d1, d2)[0, 1]
    assert abs(corr) < 0.01


def test_quadratic_variation_converges_to_T():
    """Drill question 2, made executable."""
    T = 1.0
    W = gbm.brownian_paths(n_paths=64, n_steps=20_000, t_years=T, seed=3)
    qv = np.diff(W, axis=1).__pow__(2).sum(axis=1)
    assert qv.mean() == pytest.approx(T, rel=0.02)


def test_gbm_terminal_is_a_martingale():
    """E[S(T)] == F. Drill question 3."""
    F = 100.0
    S = gbm.gbm_terminal(forward=F, sigma=0.6, t_years=0.5,
                         n_paths=400_000, seed=17)
    se = S.std() / math.sqrt(len(S))
    assert abs(S.mean() - F) < 4.0 * se


def test_gbm_terminal_is_lognormal_with_right_variance():
    F, sigma, T = 100.0, 0.4, 2.0
    S = gbm.gbm_terminal(F, sigma, T, n_paths=400_000, seed=19)
    logs = np.log(S / F)
    assert logs.mean() == pytest.approx(-0.5 * sigma ** 2 * T, abs=0.01)
    assert logs.var() == pytest.approx(sigma ** 2 * T, rel=0.02)


@pytest.mark.parametrize("strike", [80.0, 100.0, 125.0])
def test_mc_converges_to_closed_form(strike):
    """THE GATE. Two independent implementations must agree."""
    F, sigma, T = 100.0, 0.5, 0.25
    mc, se = gbm.mc_digital_call(F, strike, sigma, T,
                                 n_paths=500_000, seed=23)
    closed = digital.digital_call(F, strike, sigma, T)
    assert closed is not None
    assert abs(mc - closed) < 4.0 * se, (
        f"MC {mc:.5f} vs closed form {closed:.5f}, se {se:.5f}"
    )


def test_mc_standard_error_matches_bernoulli_formula():
    """Drill question 5, made executable."""
    F, K, sigma, T, n = 100.0, 105.0, 0.5, 0.25, 200_000
    price, se = gbm.mc_digital_call(F, K, sigma, T, n_paths=n, seed=29)
    expected_se = math.sqrt(price * (1.0 - price) / n)
    assert se == pytest.approx(expected_se, rel=0.05)


def test_seed_is_reproducible():
    a = gbm.mc_digital_call(100.0, 100.0, 0.4, 1.0, n_paths=10_000, seed=5)
    b = gbm.mc_digital_call(100.0, 100.0, 0.4, 1.0, n_paths=10_000, seed=5)
    assert a == b
```

- [ ] **Step 3: Deliver the contract stub — signatures and docstrings only**

```python
# eqr/gbm.py
"""Brownian motion, GBM, and a Monte-Carlo digital pricer.

★ THE AUTHOR WRITES THE BODIES. Signatures and contracts are fixed here so
the delivered tests compile; every `raise NotImplementedError` below is his
to replace.

Pure and I/O-free by design, so tests run with no API key.
"""
from __future__ import annotations

import numpy as np


def brownian_paths(n_paths: int, n_steps: int, t_years: float,
                   seed: int) -> np.ndarray:
    """Standard Brownian motion on [0, t_years], shape (n_paths, n_steps+1).

    W[:, 0] must be exactly 0. Increments are iid N(0, dt) with
    dt = t_years / n_steps. Use np.random.default_rng(seed).
    """
    raise NotImplementedError("Day 1: yours to write")


def gbm_terminal(forward: float, sigma: float, t_years: float,
                 n_paths: int, seed: int) -> np.ndarray:
    """S(T) under zero-drift GBM: F * exp(-0.5*sigma^2*T + sigma*W(T)).

    Returns shape (n_paths,). Only the terminal value is needed to price a
    European payoff, so do not simulate a full path here -- one normal draw
    per path is both correct and ~n_steps times faster.
    """
    raise NotImplementedError("Day 1: yours to write")


def mc_digital_call(forward: float, strike: float, sigma: float,
                    t_years: float, n_paths: int,
                    seed: int) -> tuple[float, float]:
    """(price, standard_error) for a cash-or-nothing digital call, r = 0.

    price = mean of the indicator 1{S(T) >= strike}.
    standard_error = sqrt(p*(1-p)/n) -- the Bernoulli SE from drill Q5, not
    the sample std of the indicator divided by sqrt(n) with ddof=1. They
    agree to O(1/n); use the closed form so the test comparing them is
    checking your understanding rather than a numerical accident.
    """
    raise NotImplementedError("Day 1: yours to write")
```

- [ ] **Step 4: Run the tests and confirm they fail for the right reason**

Run: `python -m pytest tests/eqr/test_gbm.py -v`
Expected: 10 failures, every one `NotImplementedError: Day 1: yours to write`. Not `ImportError`, not `AttributeError` — if you see either, the stub is wrong, not the author's code.

- [ ] **Step 5: STOP. Hand off to the author.**

Do not implement `gbm.py`. Report the failing test list and the drill path.

- [ ] **Step 6: After the author's implementation, run the DEFENSE**

Interrogate at full superday intensity. Required questions:
1. "Your `d2` — `agent/digital.py:60` computes `d1` with `+0.5*sigma^2*T` then subtracts `sigma*sqrt(T)`. Your drill answer had `-0.5*sigma^2*T` directly in `d2`. Are these the same number? Prove it."
2. "You passed with 500,000 paths. What's your standard error? Is your agreement with the closed form evidence, or is your tolerance just wide?"
3. "`gbm_terminal` doesn't call `brownian_paths`. Justify that, or admit it's a bug."
4. "Fix the seed and halve `n_paths`. Does the error fall by sqrt(2)? If not, why not?"

- [ ] **Step 7: Commit (author's work + delivered tests)**

```bash
git add eqr/gbm.py tests/eqr/test_gbm.py drills/day01-brownian-motion.md
git commit -m "feat(eqr): Brownian motion and Monte-Carlo digital pricer

MC converges to agent/digital.py's closed-form N(d2) within 4 standard
errors at three strikes. Two independent implementations agreeing is the
evidence."
```

---

## Task 2 (Day 2): `eqr/surface.py` — implied vol and the two-root problem ★

**Files:**
- Create: `eqr/surface.py` (★ author), `drills/day02-two-roots.md` (delivered)
- Test: `tests/eqr/test_surface.py` (delivered)

**Interfaces:**
- Consumes: `agent.digital.implied_vol`, `agent.digital.implied_vol_roots`, `agent.digital.peak_vol`, `agent.digital.max_digital_price`, `agent.digital.moneyness`
- Produces:
  - `SurfacePoint` dataclass: `strike: float, price: float, moneyness: float, iv_low: float | None, iv_high: float | None, invertible: bool`
  - `build_surface(forward: float, t_years: float, quotes: list[tuple[float, float]]) -> list[SurfacePoint]`
  - `smile_slope(points: list[SurfacePoint]) -> float | None`

- [ ] **Step 1: Deliver the drill**

```markdown
<!-- drills/day02-two-roots.md -->
# Day 2 — Why a digital has two implied vols

On paper first.

1. Fix F = 100, K = 125, T = 0.25. Compute the digital price N(d2) at
   sigma = 0.1, 0.5, 1.0, 2.0, 5.0. Sketch price against sigma.
   It is NOT monotone. Describe the shape in one sentence.

2. Explain economically why more vol first RAISES an out-of-the-money
   digital and then LOWERS it. What is the limiting price as
   sigma -> infinity, and why is it that number and not 1?

3. Differentiate the digital price with respect to sigma and show that
   vega has the sign of -d1. Where does vega vanish? Confirm your answer
   equals agent/digital.py's `peak_vol`.

4. Consequence for inversion: given an out-of-the-money digital quote
   below the peak price, how many sigmas reproduce it? Above the peak
   price? Exactly at it?

5. agent/digital.py:178 returns the LOW root and says so. Why is the low
   root the right default for building a surface? What would a surface
   built from the high root look like as strikes cross the forward?
```

- [ ] **Step 2: Deliver the failing tests**

```python
# tests/eqr/test_surface.py
"""Day 2. The two-root problem, made executable."""
import pytest

from agent import digital
from eqr import surface


def test_surface_point_recovers_the_vol_it_was_priced_with():
    F, T, sigma = 100.0, 0.25, 0.45
    strikes = [85.0, 95.0, 100.0, 110.0]
    quotes = [(k, digital.digital_call(F, k, sigma, T)) for k in strikes]
    pts = surface.build_surface(F, T, quotes)
    assert len(pts) == 4
    for p in pts:
        assert p.invertible
        assert p.iv_low == pytest.approx(sigma, abs=1e-4)


def test_out_of_the_money_quote_has_two_roots():
    """K far above F: the price is non-monotone in sigma, so two vols fit."""
    F, K, T = 100.0, 130.0, 0.25
    peak = digital.peak_vol(F, K, T)
    assert peak is not None
    mx = digital.max_digital_price(F, K, T)
    price = 0.5 * mx  # strictly below the peak -> two roots
    pts = surface.build_surface(F, T, [(K, price)])
    p = pts[0]
    assert p.iv_low is not None and p.iv_high is not None
    assert p.iv_low < peak < p.iv_high
    assert digital.digital_call(F, K, p.iv_low, T) == pytest.approx(price, abs=1e-6)
    assert digital.digital_call(F, K, p.iv_high, T) == pytest.approx(price, abs=1e-6)


def test_in_the_money_quote_has_one_root():
    """K below F: price IS monotone in sigma, so iv_high must be None."""
    F, K, T, sigma = 100.0, 80.0, 0.25, 0.5
    price = digital.digital_call(F, K, sigma, T)
    p = surface.build_surface(F, T, [(K, price)])[0]
    assert p.iv_low == pytest.approx(sigma, abs=1e-4)
    assert p.iv_high is None


def test_quote_above_the_attainable_maximum_is_not_invertible():
    F, K, T = 100.0, 130.0, 0.25
    mx = digital.max_digital_price(F, K, T)
    p = surface.build_surface(F, T, [(K, min(0.999, mx + 0.05))])[0]
    assert p.invertible is False
    assert p.iv_low is None


def test_moneyness_sign_convention():
    F, T = 100.0, 0.25
    pts = surface.build_surface(F, T, [(80.0, 0.9), (125.0, 0.1)])
    assert pts[0].moneyness > 0     # strike below forward
    assert pts[1].moneyness < 0


def test_smile_slope_is_none_with_fewer_than_two_invertible_points():
    assert surface.smile_slope([]) is None


def test_flat_vol_gives_zero_smile_slope():
    F, T, sigma = 100.0, 0.25, 0.4
    quotes = [(k, digital.digital_call(F, k, sigma, T))
              for k in (90.0, 95.0, 105.0, 110.0)]
    pts = surface.build_surface(F, T, quotes)
    assert surface.smile_slope(pts) == pytest.approx(0.0, abs=1e-3)
```

- [ ] **Step 3: Deliver the contract stub**

```python
# eqr/surface.py
"""Implied-vol surface from a strip of Kalshi digitals.

★ THE AUTHOR WRITES THE BODIES.

The whole difficulty is that a digital's price is not monotone in sigma
out of the money, so inversion is not a function -- it is a relation with
up to two branches. agent/digital.py already exposes `implied_vol_roots`,
`peak_vol` and `max_digital_price`; use them rather than rolling a solver.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SurfacePoint:
    strike: float
    price: float
    moneyness: float
    iv_low: float | None
    iv_high: float | None
    invertible: bool


def build_surface(forward: float, t_years: float,
                  quotes: list[tuple[float, float]]) -> list[SurfacePoint]:
    """One SurfacePoint per (strike, price) quote, in the order given.

    invertible is False when no sigma reproduces the price -- which happens
    when an out-of-the-money quote exceeds `max_digital_price`. Return the
    point with iv_low = iv_high = None rather than dropping it: a
    non-invertible quote is a signal, not a nuisance.
    """
    raise NotImplementedError("Day 2: yours to write")


def smile_slope(points: list[SurfacePoint]) -> float | None:
    """OLS slope of iv_low against moneyness over invertible points.

    None when fewer than two points are invertible. This is the crudest
    possible skew measure and that is deliberate -- you will replace it on
    Day 4 once you have a real density.
    """
    raise NotImplementedError("Day 2: yours to write")
```

- [ ] **Step 4: Run tests and confirm they fail with `NotImplementedError`**

Run: `python -m pytest tests/eqr/test_surface.py -v`
Expected: 7 failures, all `NotImplementedError: Day 2: yours to write`

- [ ] **Step 5: STOP. Hand off.**

- [ ] **Step 6: DEFENSE**

1. "Show me a real Kalshi ladder where a quote is non-invertible. What does that mean about the market's belief?"
2. "You defaulted to the low root. Give me a case where that is the wrong choice and you'd be lying to yourself."
3. "Your smile slope is an OLS on four points. What's its standard error? Would you trade on it?"

- [ ] **Step 7: Commit**

```bash
git add eqr/surface.py tests/eqr/test_surface.py drills/day02-two-roots.md
git commit -m "feat(eqr): implied-vol surface with explicit two-root handling"
```

---

## Task 3 (Day 3): `eqr/greeks.py` — digital Greeks, verified against your own Monte Carlo ★

**Files:**
- Create: `eqr/greeks.py` (★ author), `drills/day03-greeks.md` (delivered)
- Test: `tests/eqr/test_greeks.py` (delivered)

**Interfaces:**
- Consumes: `eqr.gbm.mc_digital_call`, `agent.digital.delta/vega/gamma/peak_vol`
- Produces:
  - `fd_delta(forward, strike, sigma, t_years, h=1e-4, n_paths=400_000, seed=31) -> float`
  - `fd_vega(forward, strike, sigma, t_years, h=1e-4, n_paths=400_000, seed=31) -> float`
  - `vega_sign(forward, strike, sigma, t_years) -> int` — `+1`, `-1`, or `0`

- [ ] **Step 1: Deliver the drill**

```markdown
<!-- drills/day03-greeks.md -->
# Day 3 — Greeks of a digital, and the sign that catches people

1. Write dPrice/dF for the digital analytically. Note it is a PDF, not a
   CDF. Sketch it against F. Why is this "a spike, not a ramp", and why
   does that make a digital brutal to hedge near expiry?

2. Vega. Show d(N(d2))/d(sigma) = -phi(d2) * d1 / sigma. Vega therefore has
   the sign of -d1. Where is d1 = 0? Write that strike in terms of F, sigma
   and T.

3. Sign table. For F = 100, T = 0.25, sigma = 0.5, state the sign of vega
   at K = 80, K = 100, K = 130. Then explain to an interviewer, in two
   sentences and no equations, why buying vol helps you on one of these
   and hurts you on another.

4. Common-random-numbers. You will estimate delta by bumping F and
   re-simulating. If you draw FRESH randoms for the bumped run, your
   finite difference is (signal + noise)/h with h tiny. Estimate how bad
   that is. What must you do instead?

5. Why is `mc_digital_call`'s payoff an indicator, and what does that do to
   pathwise differentiation? (This is why you are bumping, not
   differentiating the payoff.)
```

- [ ] **Step 2: Deliver the failing tests**

```python
# tests/eqr/test_greeks.py
"""Day 3. Finite-difference Greeks must reproduce the closed forms."""
import pytest

from agent import digital
from eqr import greeks


@pytest.mark.parametrize("strike", [90.0, 100.0, 115.0])
def test_fd_delta_matches_closed_form(strike):
    F, sigma, T = 100.0, 0.5, 0.25
    fd = greeks.fd_delta(F, strike, sigma, T)
    closed = digital.delta(F, strike, sigma, T)
    assert closed is not None
    assert fd == pytest.approx(closed, rel=0.05)


@pytest.mark.parametrize("strike", [85.0, 120.0])
def test_fd_vega_matches_closed_form(strike):
    F, sigma, T = 100.0, 0.5, 0.25
    fd = greeks.fd_vega(F, strike, sigma, T)
    closed = digital.vega(F, strike, sigma, T)
    assert closed is not None
    assert fd == pytest.approx(closed, rel=0.08)


def test_vega_is_negative_in_the_money_and_positive_out():
    """Drill Q3, made executable. This is THE digital-specific fact."""
    F, sigma, T = 100.0, 0.5, 0.25
    assert greeks.vega_sign(F, 80.0, sigma, T) == -1
    assert greeks.vega_sign(F, 130.0, sigma, T) == +1


def test_vega_vanishes_at_the_peak_vol_strike():
    F, T = 100.0, 0.25
    K = 130.0
    pk = digital.peak_vol(F, K, T)
    assert pk is not None
    assert greeks.vega_sign(F, K, pk, T) == 0


def test_common_random_numbers_are_used():
    """Two calls with the same seed must return EXACTLY the same number.

    If fresh randoms leak in, this is flaky by construction.
    """
    a = greeks.fd_delta(100.0, 105.0, 0.5, 0.25, seed=41)
    b = greeks.fd_delta(100.0, 105.0, 0.5, 0.25, seed=41)
    assert a == b
```

- [ ] **Step 3: Deliver the contract stub**

```python
# eqr/greeks.py
"""Digital Greeks by finite difference over your own Monte Carlo.

★ THE AUTHOR WRITES THE BODIES.

The point of this module is NOT to compute Greeks -- agent/digital.py
already has closed forms. The point is that your MC and the closed forms
must agree, which is what proves you understand both.

CRITICAL: use COMMON RANDOM NUMBERS. Pass the same seed to both the base
and the bumped simulation. Fresh randoms make the finite difference
(signal + noise)/h, and with h = 1e-4 the noise wins by orders of
magnitude. If a test is flaky, this is why.
"""
from __future__ import annotations


def fd_delta(forward: float, strike: float, sigma: float, t_years: float,
             h: float = 1e-4, n_paths: int = 400_000,
             seed: int = 31) -> float:
    """Central difference dPrice/dForward with common random numbers."""
    raise NotImplementedError("Day 3: yours to write")


def fd_vega(forward: float, strike: float, sigma: float, t_years: float,
            h: float = 1e-4, n_paths: int = 400_000,
            seed: int = 31) -> float:
    """Central difference dPrice/dSigma with common random numbers."""
    raise NotImplementedError("Day 3: yours to write")


def vega_sign(forward: float, strike: float, sigma: float,
              t_years: float) -> int:
    """+1, -1 or 0. Use the ANALYTIC vega, not the finite difference --
    a noisy estimate near the zero crossing would return the wrong sign.
    Return 0 when |vega| is below 1e-9."""
    raise NotImplementedError("Day 3: yours to write")
```

- [ ] **Step 4: Run and confirm failure**

Run: `python -m pytest tests/eqr/test_greeks.py -v`
Expected: 8 failures, all `NotImplementedError: Day 3: yours to write`

- [ ] **Step 5: STOP. Hand off.**

- [ ] **Step 6: DEFENSE**

1. "Break common random numbers on purpose. Show me the delta estimate. Now explain the variance."
2. "You're long a Kalshi YES at 15c. Vol doubles. Which way does your mark move, and would you have known that from a vanilla-options intuition?"
3. "Your `fd_vega` matched to 8% but `fd_delta` to 5%. Why is vega harder?"

- [ ] **Step 7: Commit**

```bash
git add eqr/greeks.py tests/eqr/test_greeks.py drills/day03-greeks.md
git commit -m "feat(eqr): finite-difference digital Greeks with common random numbers"
```

---

## Task 4 (Day 4): `eqr/density.py` — the ladder is the risk-neutral CDF ★

**Files:**
- Create: `eqr/density.py` (★ author), `drills/day04-density.md` (delivered)
- Test: `tests/eqr/test_density.py` (delivered)

**Interfaces:**
- Consumes: `agent.ladder.Ladder`, `agent.ladder.parse_strike`, `agent.ladder.ladders_from_rows`
- Produces:
  - `pdf_from_cdf(strikes: list[float], p_ge: list[float]) -> list[tuple[float, float]]` — `(midpoint_strike, mass)`
  - `moments(pdf: list[tuple[float, float]]) -> dict` — keys `mean, var, stdev, skew, kurtosis, mass`
  - `negative_mass(pdf) -> list[tuple[float, float]]`
  - `implied_move(pdf, confidence: float = 0.68) -> tuple[float, float] | None`

- [ ] **Step 1: Deliver the drill**

```markdown
<!-- drills/day04-density.md -->
# Day 4 — Breeden-Litzenberger, one derivative cheaper

1. Breeden-Litzenberger: for VANILLA calls, the risk-neutral density is
   d2C/dK2. Write why -- start from C(K) = E[(S-K)+] and differentiate
   twice under the integral.

2. Kalshi lists DIGITALS, not vanillas, with strike_type "greater". So a
   rung quotes P(X >= K). Write the relationship between the rung price
   and the CDF. How many derivatives do you now need to get the density?

3. Therefore: given rungs at K_0 < K_1 < ... < K_n with prices p_i =
   P(X >= K_i), write the probability mass in the bucket [K_i, K_{i+1}].
   Which strike do you assign that mass to, and what error does your
   choice introduce?

4. Sum of all bucket masses. What should it be? What IS it, for a real
   ladder that does not span (-inf, inf)? agent/ladder.py calls this
   `mass_captured`. Why can you not simply renormalise it to 1 and move on?

5. NEGATIVE MASS. Under what quoted condition does your bucket formula
   return a negative number? Is that an arbitrage? State the trade that
   captures it, then apply the fee 0.07*P*(1-P) to BOTH legs and say
   whether it survives. (Look up AGENT.md:166 before you answer.)
```

- [ ] **Step 2: Deliver the failing tests**

```python
# tests/eqr/test_density.py
"""Day 4. A ladder of digitals is a CDF; one difference gives the density."""
import math

import pytest

from eqr import density


def _lognormal_ladder(forward, sigma, t, strikes):
    """P(X >= K) under GBM -- a ladder with a KNOWN density."""
    from agent import digital
    return [digital.digital_call(forward, k, sigma, t) for k in strikes]


def test_pdf_is_first_difference_of_survival_function():
    strikes = [10.0, 20.0, 30.0, 40.0]
    p_ge = [0.9, 0.6, 0.25, 0.05]
    pdf = density.pdf_from_cdf(strikes, p_ge)
    assert len(pdf) == 3
    masses = [m for _, m in pdf]
    assert masses == pytest.approx([0.3, 0.35, 0.20], abs=1e-9)


def test_pdf_bucket_strikes_are_midpoints():
    pdf = density.pdf_from_cdf([10.0, 20.0, 30.0], [0.9, 0.6, 0.25])
    assert [k for k, _ in pdf] == pytest.approx([15.0, 25.0])


def test_moments_recover_a_known_lognormal():
    F, sigma, T = 100.0, 0.3, 1.0
    strikes = [float(k) for k in range(20, 401, 2)]
    p_ge = _lognormal_ladder(F, sigma, T, strikes)
    pdf = density.pdf_from_cdf(strikes, p_ge)
    m = density.moments(pdf)
    assert m["mass"] == pytest.approx(1.0, abs=0.02)
    assert m["mean"] == pytest.approx(F, rel=0.03)
    expected_var = F * F * (math.exp(sigma ** 2 * T) - 1.0)
    assert m["var"] == pytest.approx(expected_var, rel=0.10)
    assert m["skew"] > 0.0     # lognormal is right-skewed


def test_negative_mass_flags_a_monotonicity_violation():
    strikes = [10.0, 20.0, 30.0]
    p_ge = [0.5, 0.6, 0.1]     # 0.6 > 0.5: impossible for a survival fn
    pdf = density.pdf_from_cdf(strikes, p_ge)
    bad = density.negative_mass(pdf)
    assert len(bad) == 1
    assert bad[0][1] < 0


def test_clean_ladder_has_no_negative_mass():
    strikes = [float(k) for k in range(50, 200, 5)]
    p_ge = _lognormal_ladder(100.0, 0.4, 0.5, strikes)
    pdf = density.pdf_from_cdf(strikes, p_ge)
    assert density.negative_mass(pdf) == []


def test_mass_captured_is_below_one_for_a_truncated_ladder():
    """Drill Q4: a ladder spanning 90-110 cannot hold all the mass."""
    strikes = [float(k) for k in range(90, 111)]
    p_ge = _lognormal_ladder(100.0, 0.6, 1.0, strikes)
    m = density.moments(density.pdf_from_cdf(strikes, p_ge))
    assert m["mass"] < 0.5


def test_implied_move_brackets_the_centre():
    strikes = [float(k) for k in range(20, 401, 2)]
    p_ge = _lognormal_ladder(100.0, 0.3, 1.0, strikes)
    pdf = density.pdf_from_cdf(strikes, p_ge)
    lo, hi = density.implied_move(pdf, confidence=0.68)
    assert lo < 100.0 < hi


def test_implied_move_returns_none_when_mass_is_insufficient():
    pdf = [(10.0, 0.1), (20.0, 0.1)]     # only 0.2 of mass, cannot cover 0.68
    assert density.implied_move(pdf, confidence=0.68) is None
```

- [ ] **Step 3: Deliver the contract stub**

```python
# eqr/density.py
"""Risk-neutral density from a Kalshi threshold ladder.

★ THE AUTHOR WRITES THE BODIES.

Kalshi rungs quote P(X >= K), so the ladder IS 1 - CDF. Breeden-Litzenberger
needs d2C/dK2 for vanillas; here the exchange has already done one of those
derivatives for you, and a single first difference gives the density.

DO NOT renormalise mass to 1. A truncated ladder genuinely does not observe
the tails, and pretending otherwise silently inflates every moment you
compute. Report `mass` and let the caller decide.
"""
from __future__ import annotations


def pdf_from_cdf(strikes: list[float],
                 p_ge: list[float]) -> list[tuple[float, float]]:
    """Bucket masses from a survival curve. Returns (midpoint, mass) pairs.

    Input must be sorted ascending by strike; raise ValueError if not.
    Output has len(strikes) - 1 entries. Mass may be NEGATIVE when the
    quotes violate monotonicity -- do not clip it, that is the signal.
    """
    raise NotImplementedError("Day 4: yours to write")


def moments(pdf: list[tuple[float, float]]) -> dict:
    """mean, var, stdev, skew, kurtosis, mass.

    Moments are computed on the OBSERVED mass without renormalising, then
    divided by `mass`, so a truncated ladder gives a conditional moment and
    `mass` tells you how much to distrust it. skew and kurtosis are the
    standardised third and fourth central moments; kurtosis is NOT excess.
    """
    raise NotImplementedError("Day 4: yours to write")


def negative_mass(pdf: list[tuple[float, float]]
                  ) -> list[tuple[float, float]]:
    """Every bucket with mass < 0. Empty list when the ladder is clean."""
    raise NotImplementedError("Day 4: yours to write")


def implied_move(pdf: list[tuple[float, float]],
                 confidence: float = 0.68) -> tuple[float, float] | None:
    """Narrowest (lo, hi) strike interval holding `confidence` of the mass.

    None when the observed mass is less than `confidence` -- you cannot
    report a 68% interval from a ladder that only observes 40% of the
    distribution.
    """
    raise NotImplementedError("Day 4: yours to write")
```

- [ ] **Step 4: Run and confirm failure**

Run: `python -m pytest tests/eqr/test_density.py -v`
Expected: 8 failures, all `NotImplementedError: Day 4: yours to write`

- [ ] **Step 5: STOP. Hand off.**

- [ ] **Step 6: DEFENSE**

1. "Run this on a live `KXBTCD` ladder from `state/eqr_panel.jsonl`. What's your `mass`? Now tell me whether your `mean` means anything."
2. "You found negative mass. Price the trade. Apply the fee to both legs. Still want it?"
3. "You used mids. The bid-ask spread is 2c. Redo it on bids, then on asks. Which of your three densities is real?"

- [ ] **Step 7: Commit**

```bash
git add eqr/density.py tests/eqr/test_density.py drills/day04-density.md
git commit -m "feat(eqr): risk-neutral density from Kalshi threshold ladders"
```

---

## Task 5: Terminal panels for Density and Surface (delivered)

Wires the author's Day 2 and Day 4 modules into the terminal so a bug in his math shows up as a malformed curve.

**Files:**
- Create: `terminal/src/panels/LadderPanel.tsx`, `terminal/src/panels/DensityPanel.tsx`, `terminal/src/api.ts`, `terminal/src/theme.css`
- Modify: `server/app.py` — add `GET /api/density/{event_ticker}`
- Test: `terminal/src/api.test.ts`, manual `npx tsc --noEmit`

**Interfaces:**
- Consumes: `eqr.density.pdf_from_cdf`, `eqr.density.moments`, `eqr.surface.build_surface`
- Produces: `GET /api/density/{event_ticker}` returning `{strikes, p_ge, pdf, moments, negative_buckets}`

- [ ] **Step 1: Invoke the frontend-design skill before writing any TSX**

The terminal's visual identity is a deliverable, not an afterthought. Run `Skill(frontend-design:frontend-design)` and apply its output to `theme.css` before building panels.

- [ ] **Step 2: Add the density endpoint**

```python
# server/app.py — append
from agent import ladder as ladder_mod
from eqr import density as density_mod


@app.get("/api/density/{event_ticker}")
def density_endpoint(event_ticker: str) -> dict:
    rows = loader.load_snapshots(PANEL) if PANEL.exists() else []
    latest = loader.latest_by_ticker(rows)
    rungs = [r for r in latest.values()
             if r.get("event_ticker") == event_ticker]
    pairs = []
    for r in rungs:
        k = ladder_mod.parse_strike(r.get("ticker", ""))
        bid, ask = r.get("yes_bid_c"), r.get("yes_ask_c")
        if k is None or bid is None or ask is None:
            continue
        pairs.append((k, 0.5 * (bid + ask) / 100.0))
    pairs.sort()
    if len(pairs) < 3:
        return {"event_ticker": event_ticker, "strikes": [], "p_ge": [],
                "pdf": [], "moments": {}, "negative_buckets": []}
    strikes = [k for k, _ in pairs]
    p_ge = [p for _, p in pairs]
    try:
        pdf = density_mod.pdf_from_cdf(strikes, p_ge)
        mom = density_mod.moments(pdf)
        neg = density_mod.negative_mass(pdf)
    except NotImplementedError:
        # The author has not written Day 4 yet. Say so honestly.
        return {"event_ticker": event_ticker, "strikes": strikes,
                "p_ge": p_ge, "pdf": [], "moments": {},
                "negative_buckets": [], "pending": "eqr/density.py"}
    return {"event_ticker": event_ticker, "strikes": strikes, "p_ge": p_ge,
            "pdf": pdf, "moments": mom, "negative_buckets": neg}
```

- [ ] **Step 3: Write the typed API client**

```typescript
// terminal/src/api.ts
export interface MarketRow {
  ts: number; series: string; ticker: string; event_ticker: string;
  yes_bid_c: number; yes_ask_c: number; spread_c: number;
  oi: number; v24: number;
}
export interface DensityResponse {
  event_ticker: string;
  strikes: number[];
  p_ge: number[];
  pdf: [number, number][];
  moments: Partial<Record<'mean'|'var'|'stdev'|'skew'|'kurtosis'|'mass', number>>;
  negative_buckets: [number, number][];
  pending?: string;
}

const BASE = 'http://localhost:8000';

export async function getUniverse(limit = 400): Promise<MarketRow[]> {
  const r = await fetch(`${BASE}/api/universe?limit=${limit}`);
  if (!r.ok) throw new Error(`universe ${r.status}`);
  return (await r.json()).markets as MarketRow[];
}

export async function getDensity(ev: string): Promise<DensityResponse> {
  const r = await fetch(`${BASE}/api/density/${encodeURIComponent(ev)}`);
  if (!r.ok) throw new Error(`density ${r.status}`);
  return await r.json() as DensityResponse;
}

export function openQuoteSocket(onRows: (rows: MarketRow[]) => void): WebSocket {
  const ws = new WebSocket(`${BASE.replace('http', 'ws')}/ws/quotes`);
  ws.onmessage = (e) => {
    try { onRows(JSON.parse(e.data).markets as MarketRow[]); }
    catch { /* a torn frame is not fatal */ }
  };
  return ws;
}
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd terminal && npx tsc --noEmit`
Expected: exit 0, no output.

- [ ] **Step 5: Build the panels and re-verify**

Run: `cd terminal && npx tsc --noEmit && npm run build`
Expected: exit 0 both.

- [ ] **Step 6: Commit**

```bash
git add terminal server/app.py
git commit -m "feat(terminal): ladder and density panels over the author's eqr modules"
```

---

## Task 6 (Day 5): `eqr/universe.py` and `eqr/panel.py` — point-in-time, with a lookahead canary ★

**Files:**
- Create: `eqr/universe.py` (★), `eqr/panel.py` (★), `drills/day05-lookahead.md` (delivered)
- Test: `tests/eqr/test_panel.py` (delivered)

**Interfaces:**
- Consumes: `eqr.loader.load_snapshots`
- Produces:
  - `universe.exclude_combos(rows) -> list[dict]`
  - `universe.liquidity_screen(rows, asof_ts: int, min_v24: float, max_spread_c: float) -> list[dict]`
  - `panel.build(rows, asof_ts: int, horizon_s: int) -> list[dict]` — each row gains `fwd_ret` and `resolves_in_window: bool`
  - `panel.cross_section(rows, asof_ts, horizon_s) -> tuple[list[dict], list[float]]`

- [ ] **Step 1: Deliver the drill**

```markdown
<!-- drills/day05-lookahead.md -->
# Day 5 — The three ways your backtest lies

1. LOOKAHEAD. You build a panel at time t and join a forward return from
   t + h. Name three fields on a snapshot that, if you take them from the
   t + h row instead of the t row, would leak the answer. For each, say
   how large the fake IC would be.

2. SURVIVORSHIP. Your recorder only has markets that were OPEN when it
   swept. Which markets are systematically missing from your history, and
   which direction does that bias a mean-reversion result?

3. THE LIQUIDITY SCREEN TRAP. You screen on v24 > 1000. v24 is
   24-hour volume AS OF THE SNAPSHOT. Is that point-in-time? Now suppose
   you screened on "markets that ever exceeded 1000 volume". Explain
   precisely why the second is a disaster and the first is not.

4. RESOLUTION CONTAMINATION. A contract settling inside your forward
   window goes to exactly 0 or 1. That is a real return. Why is it not a
   TRADEABLE return, and what happens to your Sharpe if you leave those
   rows in?

5. Write the one-line test that would catch you if you got #1 wrong.
   (Then look at test_planted_lookahead_signal_scores_near_zero below and
   see whether you wrote the same test.)
```

- [ ] **Step 2: Deliver the failing tests, including the canary**

```python
# tests/eqr/test_panel.py
"""Day 5. The panel is the ONLY place lookahead can enter. Guard it."""
import pytest

from eqr import panel, universe


def _rows():
    """Two tickers, three timestamps, hand-computable returns."""
    out = []
    for ts, (a, b) in [(100, (40.0, 60.0)),
                       (200, (44.0, 57.0)),
                       (300, (50.0, 50.0))]:
        out.append({"ts": ts, "ticker": "A", "event_ticker": "EA",
                    "series": "S", "yes_bid_c": a - 1, "yes_ask_c": a + 1,
                    "spread_c": 2.0, "oi": 100.0, "v24": 5000.0})
        out.append({"ts": ts, "ticker": "B", "event_ticker": "EB",
                    "series": "S", "yes_bid_c": b - 1, "yes_ask_c": b + 1,
                    "spread_c": 2.0, "oi": 100.0, "v24": 5000.0})
    return out


def test_exclude_combos_drops_cross_category_shards():
    rows = [{"ticker": "KXMVECROSSCATEGORY-SHARD1-XYZ"}, {"ticker": "KXBTCD-1-T2"}]
    kept = universe.exclude_combos(rows)
    assert [r["ticker"] for r in kept] == ["KXBTCD-1-T2"]


def test_liquidity_screen_uses_only_rows_at_or_before_asof():
    rows = _rows()
    rows.append({"ts": 999, "ticker": "C", "event_ticker": "EC",
                 "series": "S", "yes_bid_c": 10.0, "yes_ask_c": 12.0,
                 "spread_c": 2.0, "oi": 1.0, "v24": 1e9})
    kept = universe.liquidity_screen(rows, asof_ts=300, min_v24=1000.0,
                                     max_spread_c=5.0)
    assert "C" not in {r["ticker"] for r in kept}


def test_liquidity_screen_rejects_wide_spreads():
    rows = _rows()
    rows[0]["spread_c"] = 40.0
    kept = universe.liquidity_screen(rows, asof_ts=100, min_v24=1000.0,
                                     max_spread_c=5.0)
    assert "A" not in {r["ticker"] for r in kept}


def test_forward_return_uses_a_strictly_later_snapshot():
    rows = _rows()
    built = panel.build(rows, asof_ts=100, horizon_s=100)
    by = {r["ticker"]: r for r in built}
    # A mid goes 40 -> 44 over the horizon; return in probability points.
    assert by["A"]["fwd_ret"] == pytest.approx(0.04, abs=1e-9)
    assert by["B"]["fwd_ret"] == pytest.approx(-0.03, abs=1e-9)


def test_forward_return_is_none_when_no_later_snapshot_exists():
    built = panel.build(_rows(), asof_ts=300, horizon_s=100)
    assert all(r["fwd_ret"] is None for r in built)


def test_panel_row_carries_no_future_fields():
    """Every value on the row except fwd_ret must come from the asof snap."""
    built = panel.build(_rows(), asof_ts=100, horizon_s=100)
    by = {r["ticker"]: r for r in built}
    assert by["A"]["yes_bid_c"] == 39.0      # the t=100 quote, not t=200
    assert by["A"]["ts"] == 100


def test_planted_lookahead_signal_scores_near_zero():
    """THE CANARY. A signal built from the asof row must not know fwd_ret.

    If panel.build leaks a future field onto the row, a signal that reads
    only 'present' fields will nonetheless correlate perfectly with the
    forward return, and this test fails loudly.
    """
    rows = _rows()
    built = panel.build(rows, asof_ts=100, horizon_s=100)
    present_fields = {k for r in built for k, v in r.items()
                      if k != "fwd_ret" and isinstance(v, (int, float))}
    rets = [r["fwd_ret"] for r in built]
    for f in present_fields:
        xs = [r[f] for r in built]
        if len(set(xs)) < 2:
            continue
        # With n=2 any two distinct numbers correlate +-1, so assert on the
        # VALUES instead: no present field may equal the forward return.
        assert xs != rets, f"field {f} leaks the forward return"


def test_resolution_contamination_is_flagged():
    rows = _rows()
    # B settles to 0 inside the window.
    rows.append({"ts": 400, "ticker": "B", "event_ticker": "EB",
                 "series": "S", "yes_bid_c": 0.0, "yes_ask_c": 0.0,
                 "spread_c": 0.0, "oi": 0.0, "v24": 5000.0})
    built = panel.build(rows, asof_ts=300, horizon_s=100)
    by = {r["ticker"]: r for r in built}
    assert by["B"]["resolves_in_window"] is True


def test_cross_section_returns_aligned_rows_and_returns():
    rows_, rets = panel.cross_section(_rows(), asof_ts=100, horizon_s=100)
    assert len(rows_) == len(rets) == 2
    assert all(r is not None for r in rets)
```

- [ ] **Step 3: Deliver the contract stubs**

```python
# eqr/universe.py
"""Universe construction. ★ THE AUTHOR WRITES THE BODIES.

Measured 2026-08-30: paging /markets returns ONLY KXMVECROSSCATEGORY combo
shards -- 15,000 of them, all with zero candlesticks. Sorting a universe by
volume without excluding them selects entirely untradeable synthetics.
"""
from __future__ import annotations

COMBO_PREFIX = "KXMVECROSSCATEGORY"


def exclude_combos(rows: list[dict]) -> list[dict]:
    """Drop every row whose ticker starts with COMBO_PREFIX."""
    raise NotImplementedError("Day 5: yours to write")


def liquidity_screen(rows: list[dict], asof_ts: int, min_v24: float,
                     max_spread_c: float) -> list[dict]:
    """Latest snapshot per ticker AT OR BEFORE asof_ts, passing the screen.

    POINT-IN-TIME IS THE WHOLE POINT. A row dated after asof_ts must never
    influence the result, not even to decide membership. Screen on the
    v24 and spread_c recorded in the asof snapshot itself.
    """
    raise NotImplementedError("Day 5: yours to write")


# eqr/panel.py
"""The point-in-time cross-sectional panel. ★ THE AUTHOR WRITES THE BODIES.

This is the ONLY module permitted to know about time, and therefore the
only place lookahead bias can enter the system. Everything downstream is
pure arithmetic on what this returns.

Mid price is (yes_bid_c + yes_ask_c) / 2 / 100, in probability units.
Forward return is a DIFFERENCE of probabilities, not a log return -- a
contract at 2c going to 4c has doubled, but as a probability it moved two
points, and probability points are what you get paid in.
"""
from __future__ import annotations


def build(rows: list[dict], asof_ts: int, horizon_s: int) -> list[dict]:
    """One row per ticker live at asof_ts, plus fwd_ret and
    resolves_in_window.

    fwd_ret = mid(first snapshot at ts >= asof_ts + horizon_s) - mid(asof).
    None when no such snapshot exists. resolves_in_window is True when the
    forward snapshot's mid is exactly 0.0 or 1.0.

    Every other field on the returned row MUST be copied from the asof
    snapshot. Copying anything from the forward snapshot is the bug the
    canary test exists to catch.
    """
    raise NotImplementedError("Day 5: yours to write")


def cross_section(rows: list[dict], asof_ts: int,
                  horizon_s: int) -> tuple[list[dict], list[float]]:
    """(rows, forward_returns) with rows lacking fwd_ret dropped, aligned."""
    raise NotImplementedError("Day 5: yours to write")
```

- [ ] **Step 4: Run and confirm failure**

Run: `python -m pytest tests/eqr/test_panel.py -v`
Expected: 9 failures, all `NotImplementedError: Day 5: yours to write`

- [ ] **Step 5: STOP. Hand off.**

- [ ] **Step 6: DEFENSE**

1. "Delete one line so `build` copies `v24` from the forward snapshot. Which test catches you? If none does, the canary is too weak — strengthen it."
2. "Your recorder only saw open markets. Name the markets missing from your history and the direction of the bias."
3. "You screened `v24 > 1000`. How many names survive at a random asof? If it's 30, your cross-section is too thin for an IC and you need to say so."

- [ ] **Step 7: Commit**

```bash
git add eqr/universe.py eqr/panel.py tests/eqr/test_panel.py drills/day05-lookahead.md
git commit -m "feat(eqr): point-in-time universe and panel with a lookahead canary"
```

---

## Task 7 (Day 6): Signals, IC, and the first two alphas ★

**Files:**
- Create: `eqr/signals/__init__.py` (delivered), `eqr/signals/base.py` (delivered), `eqr/evaluate.py` (mixed), `eqr/signals/alpha_01_reversal.py` (★), `eqr/signals/alpha_02_spread.py` (★), `drills/day06-ic.md` (delivered)
- Test: `tests/eqr/test_evaluate.py`, `tests/eqr/test_alphas.py` (delivered)

**Interfaces:**
- Consumes: `eqr.panel.cross_section`
- Produces:
  - `signals.base.Signal` protocol — `name: str`, `compute(rows: list[dict]) -> list[float | None]`
  - `evaluate.information_coefficient(signal_values, forward_returns) -> float | None` ★
  - `evaluate.quantile_spread(signal_values, forward_returns, n_q: int = 5) -> float | None` ★
  - `evaluate.ic_t_stat(ics: list[float]) -> float | None` (delivered)
  - `evaluate.ic_decay(rows, horizons) -> dict[int, float]` (delivered)

- [ ] **Step 1: Deliver the drill**

```markdown
<!-- drills/day06-ic.md -->
# Day 6 — Information coefficient, and whether yours is real

1. Define the information coefficient. Spearman or Pearson? Say which you
   are using and why cross-sectional alpha research usually prefers rank
   correlation.

2. The Fundamental Law of Active Management: IR ~ IC * sqrt(breadth).
   You have ~300 liquid Kalshi markets and you rebalance hourly. Write
   your breadth per year. Now: what IC do you need for an IR of 1.0?
   Is that number plausible? Be honest.

3. SIGNIFICANCE. You compute an IC at each of N rebalances and average.
   Write the t-stat of the mean IC. If your mean IC is 0.02 with a
   cross-sectional std of 0.15 over 200 rebalances, is it significant?

4. BREADTH IS A LIE when names are correlated. All your KXBTCD rungs are
   driven by one Bitcoin price. What is your EFFECTIVE breadth? How does
   that change your answer to Q2?

5. IC DECAY. Sketch what IC vs horizon should look like for (a) a
   microstructure reversal signal and (b) a slow fundamental signal.
   Which one is AGENT.md's momentum result, and which way does it point?
```

- [ ] **Step 2: Deliver `signals/base.py` and the evaluate harness**

```python
# eqr/signals/base.py
"""The contract every alpha satisfies. Delivered -- do not modify."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Signal(Protocol):
    name: str

    def compute(self, rows: list[dict]) -> list[float | None]:
        """One score per row, same order, same length.

        None means "no opinion on this name" and is excluded from the IC
        rather than treated as zero. A signal that returns 0.0 where it
        means None will have its IC diluted toward zero and you will
        conclude it does not work when in fact you never asked it.

        MUST be a pure function of the CURRENT rows. Reading a forward
        return here is the cardinal sin; the Day 5 canary exists because
        this contract is easy to violate by accident.
        """
        ...
```

```python
# eqr/evaluate.py
"""Signal evaluation.

MIXED OWNERSHIP. `information_coefficient` and `quantile_spread` are ★ --
the author writes them, because hand-building an IC is the highest-value
hour of Day 6. Everything else here is delivered.
"""
from __future__ import annotations

import math


def information_coefficient(signal_values: list[float | None],
                            forward_returns: list[float | None]
                            ) -> float | None:
    """★ Spearman rank correlation between signal and forward return.

    Pairs where EITHER side is None are dropped. Returns None when fewer
    than 3 usable pairs remain -- a rank correlation on two points is
    always +-1 and is not information.

    Ties must be handled with AVERAGE ranks. Ranking [5, 5, 9] as [1, 2, 3]
    invents an ordering the signal never expressed.
    """
    raise NotImplementedError("Day 6: yours to write")


def quantile_spread(signal_values: list[float | None],
                    forward_returns: list[float | None],
                    n_q: int = 5) -> float | None:
    """★ Mean forward return of the top quantile minus the bottom.

    None when fewer than n_q usable pairs remain. This is the number a PM
    actually cares about: an IC of 0.04 that comes entirely from the middle
    of the distribution is not tradeable.
    """
    raise NotImplementedError("Day 6: yours to write")


# ---------------------------------------------------------------- delivered

def ic_t_stat(ics: list[float]) -> float | None:
    """t-stat of the mean IC across rebalances. Newey-West is NOT applied:
    overlapping horizons make these autocorrelated and this t-stat is
    therefore OPTIMISTIC. Treat it as an upper bound."""
    clean = [x for x in ics if x is not None and not math.isnan(x)]
    n = len(clean)
    if n < 2:
        return None
    mean = sum(clean) / n
    var = sum((x - mean) ** 2 for x in clean) / (n - 1)
    if var <= 0:
        return None
    return mean / math.sqrt(var / n)


def deflated_sharpe(observed_sharpe: float, n_trials: int,
                    n_obs: int) -> float | None:
    """Sharpe adjusted for how many strategies you TRIED before this one.

    Bailey & Lopez de Prado. The expected maximum Sharpe from n_trials
    independent random strategies is roughly sqrt(2*ln(n_trials)) /
    sqrt(n_obs). If your observed Sharpe does not clear that, you found
    noise and named it alpha.
    """
    if n_trials < 1 or n_obs < 2:
        return None
    expected_max = math.sqrt(2.0 * math.log(max(n_trials, 2))) / math.sqrt(n_obs)
    return observed_sharpe - expected_max
```

- [ ] **Step 3: Deliver the failing tests**

```python
# tests/eqr/test_evaluate.py
import pytest

from eqr import evaluate


def test_ic_is_one_for_a_perfectly_ranked_signal():
    sig = [1.0, 2.0, 3.0, 4.0, 5.0]
    ret = [0.01, 0.02, 0.03, 0.04, 0.05]
    assert evaluate.information_coefficient(sig, ret) == pytest.approx(1.0)


def test_ic_is_minus_one_for_a_perfectly_inverted_signal():
    sig = [1.0, 2.0, 3.0, 4.0, 5.0]
    ret = [0.05, 0.04, 0.03, 0.02, 0.01]
    assert evaluate.information_coefficient(sig, ret) == pytest.approx(-1.0)


def test_ic_drops_none_pairs():
    sig = [1.0, None, 3.0, 4.0]
    ret = [0.01, 0.02, None, 0.04]
    # only (1.0, 0.01) and (4.0, 0.04) survive -> 2 pairs -> None
    assert evaluate.information_coefficient(sig, ret) is None


def test_ic_uses_average_ranks_for_ties():
    sig = [5.0, 5.0, 9.0]
    ret = [0.01, 0.02, 0.03]
    ic = evaluate.information_coefficient(sig, ret)
    assert ic is not None
    assert ic == pytest.approx(0.8660254, abs=1e-6)


def test_quantile_spread_is_positive_for_a_good_signal():
    sig = list(range(20))
    ret = [i * 0.001 for i in range(20)]
    assert evaluate.quantile_spread(sig, ret, n_q=5) > 0


def test_quantile_spread_returns_none_when_too_few_names():
    assert evaluate.quantile_spread([1.0, 2.0], [0.1, 0.2], n_q=5) is None


def test_ic_t_stat_delivered_matches_hand_computation():
    ics = [0.02, 0.04, 0.00, 0.06]
    assert evaluate.ic_t_stat(ics) == pytest.approx(2.3237900, abs=1e-6)


def test_deflated_sharpe_penalises_many_trials():
    assert evaluate.deflated_sharpe(2.0, n_trials=1000, n_obs=250) < 2.0
    assert (evaluate.deflated_sharpe(2.0, 1000, 250)
            < evaluate.deflated_sharpe(2.0, 10, 250))
```

```python
# tests/eqr/test_alphas.py
"""The author's first two alphas must satisfy the Signal contract."""
from eqr.signals import base


def _rows():
    return [
        {"ticker": "A", "yes_bid_c": 39.0, "yes_ask_c": 41.0,
         "spread_c": 2.0, "v24": 5000.0, "oi": 100.0, "ts": 100},
        {"ticker": "B", "yes_bid_c": 59.0, "yes_ask_c": 61.0,
         "spread_c": 2.0, "v24": 4000.0, "oi": 90.0, "ts": 100},
        {"ticker": "C", "yes_bid_c": 4.0, "yes_ask_c": 8.0,
         "spread_c": 4.0, "v24": 100.0, "oi": 10.0, "ts": 100},
    ]


def test_alpha_01_satisfies_the_signal_protocol():
    from eqr.signals import alpha_01_reversal as a
    s = a.Alpha()
    assert isinstance(s, base.Signal)
    assert isinstance(s.name, str) and s.name


def test_alpha_01_returns_one_value_per_row():
    from eqr.signals import alpha_01_reversal as a
    out = a.Alpha().compute(_rows())
    assert len(out) == 3


def test_alpha_02_satisfies_the_signal_protocol():
    from eqr.signals import alpha_02_spread as a
    s = a.Alpha()
    assert isinstance(s, base.Signal)


def test_alpha_02_returns_one_value_per_row():
    from eqr.signals import alpha_02_spread as a
    assert len(a.Alpha().compute(_rows())) == 3


def test_alphas_are_pure_and_do_not_mutate_input():
    from eqr.signals import alpha_01_reversal as a1
    from eqr.signals import alpha_02_spread as a2
    rows = _rows()
    snapshot = [dict(r) for r in rows]
    a1.Alpha().compute(rows)
    a2.Alpha().compute(rows)
    assert rows == snapshot
```

- [ ] **Step 4: Deliver alpha stubs with the hypothesis stated, bodies empty**

```python
# eqr/signals/alpha_01_reversal.py
"""★ Alpha 1 -- short-horizon reversal.

HYPOTHESIS (state it before you code it, and do not change it afterwards):
AGENT.md records that momentum-chasing lost at every trigger from 3c to 10c
over n=123, and lost MORE as the trigger rose. That is a mean-reversion
signature. This signal therefore scores a name POSITIVELY when its recent
move was DOWN, expecting reversion.

You need prior snapshots to compute a recent move. `compute` receives only
the current rows, so you must decide how the signal gets its history --
and whatever you decide, the Day 5 canary must still pass. Think about
that before you write anything.
"""
from __future__ import annotations


class Alpha:
    name = "alpha_01_reversal"

    def compute(self, rows: list[dict]) -> list[float | None]:
        raise NotImplementedError("Day 6: yours to write")


# eqr/signals/alpha_02_spread.py
"""★ Alpha 2 -- spread as an adverse-selection proxy.

HYPOTHESIS: a wide bid-ask spread on Kalshi signals an uninformed or thin
book. Whether that predicts return POSITIVELY or NEGATIVELY is exactly
what you do not know yet -- state your prior, then let the IC tell you,
and do NOT flip the sign afterwards and call it a discovery.
"""
from __future__ import annotations


class Alpha:
    name = "alpha_02_spread"

    def compute(self, rows: list[dict]) -> list[float | None]:
        raise NotImplementedError("Day 6: yours to write")
```

- [ ] **Step 5: Run and confirm failure**

Run: `python -m pytest tests/eqr/test_evaluate.py tests/eqr/test_alphas.py -v`
Expected: the two delivered tests (`test_ic_t_stat_delivered_matches_hand_computation`, `test_deflated_sharpe_penalises_many_trials`) PASS; all others fail with `NotImplementedError: Day 6: yours to write`.

- [ ] **Step 6: STOP. Hand off.**

- [ ] **Step 7: DEFENSE**

1. "Your IC is 0.03. Run `ic_t_stat`. Now tell me your effective breadth given every KXBTCD rung tracks one Bitcoin price. Is 0.03 significant against THAT?"
2. "You flipped alpha_02's sign after seeing the IC, didn't you. That's one trial or two? Feed the honest number to `deflated_sharpe`."
3. "Your quantile spread is positive but your IC is near zero. What does that combination mean, and is it tradeable?"

- [ ] **Step 8: Commit**

```bash
git add eqr/signals eqr/evaluate.py tests/eqr/test_evaluate.py tests/eqr/test_alphas.py drills/day06-ic.md
git commit -m "feat(eqr): Signal protocol, IC/quantile evaluation, first two alphas"
```

---

## Task 8 (Day 7): `eqr/costs.py` — why a 3-Sharpe backtest nets zero ★

**Files:**
- Create: `eqr/costs.py` (★), `drills/day07-costs.md` (delivered)
- Test: `tests/eqr/test_costs.py` (delivered)

**Interfaces:**
- Consumes: `agent.risk_unit.fee_per_contract`, `agent.risk_unit.FEE_LEGS`
- Produces:
  - `round_trip_cost(price: float, spread_c: float) -> float`
  - `net_edge(gross_edge: float, price: float, spread_c: float) -> float`
  - `breakeven_edge(price: float, spread_c: float) -> float`
  - `capacity_curve(gross_edge, price, spread_c, turnovers: list[float]) -> list[tuple[float, float]]`

- [ ] **Step 1: Deliver the drill**

```markdown
<!-- drills/day07-costs.md -->
# Day 7 — The arithmetic that kills strategies

1. Kalshi's fee is 0.07 * C * P * (1-P). Where is it maximised in P, and
   what is the maximum in cents per contract? At what two prices does it
   equal 1 cent? (agent/risk_unit.py:32 has the answer -- derive it first,
   then check.)

2. You cross a 2c spread to enter and 2c to exit. Add the fee on both
   legs at P = 0.5. Write your total round-trip cost in probability
   points. Now write the gross edge you need just to break even.

3. Compare that breakeven to the IC you measured on Day 6. Translate:
   an IC of 0.03 on a cross-section with return std of 4 probability
   points gives what expected edge per name? Does it clear the cost?

4. TURNOVER. If you rebalance hourly you pay that round trip ~6,000 times
   a year. If you rebalance daily, ~250. Write annual return as
   (edge_per_trade - cost) * turnover. Sketch it against turnover. Where
   is the maximum, and why is "trade more" not the answer?

5. Now explain in two sentences, to a PM, why AGENT.md's momentum result
   losing MORE at higher triggers is partly a COST story and not purely
   a signal story.
```

- [ ] **Step 2: Deliver the failing tests**

```python
# tests/eqr/test_costs.py
import pytest

from agent import risk_unit
from eqr import costs


def test_round_trip_cost_includes_spread_and_both_fee_legs():
    price, spread_c = 0.5, 2.0
    got = costs.round_trip_cost(price, spread_c)
    expected = (spread_c / 100.0) + risk_unit.FEE_LEGS * risk_unit.fee_per_contract(price)
    assert got == pytest.approx(expected, abs=1e-12)


def test_fee_is_maximised_at_fifty_cents():
    """Drill Q1 made executable."""
    at_50 = costs.round_trip_cost(0.50, 0.0)
    assert at_50 > costs.round_trip_cost(0.20, 0.0)
    assert at_50 > costs.round_trip_cost(0.80, 0.0)
    assert at_50 == pytest.approx(2 * 0.07 * 0.25, abs=1e-12)


def test_cheap_longshots_cost_less_than_coinflips():
    assert costs.round_trip_cost(0.03, 2.0) < costs.round_trip_cost(0.50, 2.0)


def test_net_edge_subtracts_the_round_trip():
    assert costs.net_edge(0.10, 0.5, 2.0) == pytest.approx(
        0.10 - costs.round_trip_cost(0.5, 2.0), abs=1e-12)


def test_breakeven_edge_is_exactly_the_round_trip_cost():
    for p in (0.05, 0.25, 0.5, 0.9):
        assert costs.breakeven_edge(p, 2.0) == pytest.approx(
            costs.round_trip_cost(p, 2.0), abs=1e-12)


def test_a_two_point_edge_does_not_survive_a_coinflip_round_trip():
    """The headline result: 2 probability points is NOT enough at 50c."""
    assert costs.net_edge(0.02, 0.50, 2.0) < 0


def test_capacity_curve_turns_negative_at_high_turnover():
    # cost at 50c over a 2c spread = 0.02 + 2*0.07*0.25 = 0.055, so a
    # 0.03 gross edge is NET NEGATIVE and more turnover only loses faster.
    curve = costs.capacity_curve(gross_edge=0.03, price=0.5, spread_c=2.0,
                                 turnovers=[1.0, 10.0, 100.0, 1000.0])
    assert len(curve) == 4
    annuals = [a for _, a in curve]
    assert all(a < 0 for a in annuals)
    assert annuals == sorted(annuals, reverse=True)
    assert annuals[0] == pytest.approx(-0.025, abs=1e-12)


def test_capacity_curve_is_positive_when_edge_beats_cost():
    curve = costs.capacity_curve(gross_edge=0.20, price=0.5, spread_c=2.0,
                                 turnovers=[1.0, 10.0])
    assert all(a > 0 for _, a in curve)
```

- [ ] **Step 3: Deliver the contract stub**

```python
# eqr/costs.py
"""Transaction costs. ★ THE AUTHOR WRITES THE BODIES.

Everything here is in PROBABILITY POINTS (dollars per contract, 0-1), the
same units as panel.fwd_ret, so edges and costs are directly comparable.
That is the whole reason this module exists as its own file: unit
confusion between cents and probability is the most common way a
prediction-market backtest reports a profit it never had.

Reuse agent/risk_unit.fee_per_contract. Do NOT re-derive 0.07*P*(1-P) here.
"""
from __future__ import annotations


def round_trip_cost(price: float, spread_c: float) -> float:
    """Spread (converted to dollars) plus FEE_LEGS fee charges at `price`.

    Charging the whole spread rather than half is deliberate and
    conservative: a marketable order crosses it, and assuming you get filled
    at the mid is the second most common way a backtest lies.
    """
    raise NotImplementedError("Day 7: yours to write")


def net_edge(gross_edge: float, price: float, spread_c: float) -> float:
    """gross_edge minus the round trip. May be negative; do not clamp."""
    raise NotImplementedError("Day 7: yours to write")


def breakeven_edge(price: float, spread_c: float) -> float:
    """The gross edge at which net_edge is exactly zero."""
    raise NotImplementedError("Day 7: yours to write")


def capacity_curve(gross_edge: float, price: float, spread_c: float,
                   turnovers: list[float]) -> list[tuple[float, float]]:
    """(turnover, annual_return) for each turnover, in probability points.

    annual_return = net_edge * turnover. The shape is the lesson: with a
    fixed per-trade edge, return is LINEAR in turnover and flips sign the
    moment cost exceeds edge. There is no turnover that rescues a strategy
    whose net edge is negative.
    """
    raise NotImplementedError("Day 7: yours to write")
```

- [ ] **Step 4: Run and confirm failure**

Run: `python -m pytest tests/eqr/test_costs.py -v`
Expected: 8 failures, all `NotImplementedError: Day 7: yours to write`

- [ ] **Step 5: STOP. Hand off.**

- [ ] **Step 6: DEFENSE**

1. "Take your Day 6 IC. Convert it to an expected edge per name. Run `net_edge`. Is your strategy alive? Say the number out loud."
2. "You want to trade 3c longshots because the fee is small there. What's the spread as a FRACTION of price at 3c, and does that save you?"
3. "Give me the turnover that maximises your annual return. Now tell me why that answer is a trap when your edge estimate has a standard error."

- [ ] **Step 7: Commit**

```bash
git add eqr/costs.py tests/eqr/test_costs.py drills/day07-costs.md
git commit -m "feat(eqr): transaction cost and capacity model in probability points"
```

---

## Task 9 (Day 8): Neutralization and honest significance ★

**Files:**
- Create: `eqr/signals/alpha_03_neutral.py` (★), `eqr/neutralize.py` (★), `drills/day08-neutralization.md` (delivered)
- Test: `tests/eqr/test_neutralize.py` (delivered)

**Interfaces:**
- Consumes: `eqr.evaluate.information_coefficient`, `eqr.evaluate.deflated_sharpe`
- Produces:
  - `neutralize.demean_by_group(values, groups) -> list[float | None]`
  - `neutralize.zscore(values) -> list[float | None]`
  - `neutralize.regress_out(values, factors: list[list[float]]) -> list[float | None]`

- [ ] **Step 1: Deliver the drill**

```markdown
<!-- drills/day08-neutralization.md -->
# Day 8 — Neutralization, and admitting how many things you tried

1. Your Kalshi cross-section contains 40 KXBTCD rungs, 30 KXETHD rungs and
   20 political markets. If Bitcoin rallies, what happens to the IC of ANY
   signal that happens to load on the BTC group? Is that alpha?

2. Write the operation that removes it. Demeaning within series is the
   crude version; regressing the signal on group dummies is the general
   one. Show they are the same when the only factors are group dummies.

3. Why z-score AFTER demeaning and not before?

4. MULTIPLE TESTING. Count honestly: how many signal variants have you
   run since Day 6? Include every sign flip, every parameter, every
   "let me just try". Feed that count to `deflated_sharpe`. What survives?

5. Write the sentence you would say to a Citadel interviewer who asks
   "how do you know this isn't overfit?" It must contain a number.
```

- [ ] **Step 2: Deliver the failing tests**

```python
# tests/eqr/test_neutralize.py
import pytest

from eqr import neutralize


def test_demean_by_group_removes_group_means():
    vals = [1.0, 3.0, 10.0, 20.0]
    groups = ["A", "A", "B", "B"]
    out = neutralize.demean_by_group(vals, groups)
    assert out == pytest.approx([-1.0, 1.0, -5.0, 5.0])


def test_demean_by_group_propagates_none():
    out = neutralize.demean_by_group([1.0, None, 3.0], ["A", "A", "A"])
    assert out[1] is None
    assert out[0] == pytest.approx(-1.0)
    assert out[2] == pytest.approx(1.0)


def test_zscore_has_zero_mean_and_unit_std():
    out = neutralize.zscore([1.0, 2.0, 3.0, 4.0, 5.0])
    clean = [x for x in out if x is not None]
    assert sum(clean) == pytest.approx(0.0, abs=1e-12)
    n = len(clean)
    var = sum(x * x for x in clean) / (n - 1)
    assert var == pytest.approx(1.0, abs=1e-9)


def test_zscore_returns_all_none_for_zero_variance():
    assert neutralize.zscore([5.0, 5.0, 5.0]) == [None, None, None]


def test_regress_out_removes_a_perfectly_collinear_factor():
    vals = [2.0, 4.0, 6.0, 8.0]
    factor = [1.0, 2.0, 3.0, 4.0]
    resid = neutralize.regress_out(vals, [factor])
    assert all(abs(r) < 1e-9 for r in resid)


def test_regress_out_leaves_an_orthogonal_signal_alone():
    vals = [1.0, -1.0, 1.0, -1.0]
    factor = [1.0, 1.0, -1.0, -1.0]
    resid = neutralize.regress_out(vals, [factor])
    assert resid == pytest.approx(vals, abs=1e-9)


def test_group_dummies_and_demeaning_agree():
    """Drill Q2 made executable."""
    vals = [1.0, 3.0, 10.0, 20.0]
    groups = ["A", "A", "B", "B"]
    dummy_a = [1.0, 1.0, 0.0, 0.0]
    dummy_b = [0.0, 0.0, 1.0, 1.0]
    by_demean = neutralize.demean_by_group(vals, groups)
    by_regress = neutralize.regress_out(vals, [dummy_a, dummy_b])
    assert by_regress == pytest.approx(by_demean, abs=1e-9)
```

- [ ] **Step 3: Deliver the contract stub**

```python
# eqr/neutralize.py
"""Neutralization. ★ THE AUTHOR WRITES THE BODIES.

A raw Kalshi cross-section is dominated by group effects: 40 KXBTCD rungs
all track one Bitcoin price. A signal that loads on "is a BTC rung" will
show a large IC on any day BTC moves, and that is not alpha -- it is a
factor bet you did not know you were making.

Order matters: demean within group FIRST, then z-score. Reversing them
lets a large group's dispersion set the scale for every other group.
"""
from __future__ import annotations


def demean_by_group(values: list[float | None],
                    groups: list[str]) -> list[float | None]:
    """Subtract each group's mean from its members. None passes through."""
    raise NotImplementedError("Day 8: yours to write")


def zscore(values: list[float | None]) -> list[float | None]:
    """(x - mean) / sample_std over non-None values, ddof = 1.

    Returns all None when the standard deviation is zero -- a constant
    signal carries no cross-sectional information and must not be
    resurrected by dividing by an epsilon.
    """
    raise NotImplementedError("Day 8: yours to write")


def regress_out(values: list[float | None],
                factors: list[list[float]]) -> list[float | None]:
    """OLS residual of values on factors, no intercept added automatically.

    Include an intercept explicitly as a column of ones if you want one.
    Use numpy.linalg.lstsq -- it handles the rank-deficient case that
    perfectly collinear group dummies produce, which a normal-equations
    inverse does not.
    """
    raise NotImplementedError("Day 8: yours to write")
```

- [ ] **Step 4: Run and confirm failure**

Run: `python -m pytest tests/eqr/test_neutralize.py -v`
Expected: 7 failures, all `NotImplementedError: Day 8: yours to write`

- [ ] **Step 5: STOP. Hand off. Author also writes `alpha_03_neutral.py` reusing these.**

- [ ] **Step 6: DEFENSE**

1. "Report your IC before and after neutralization. If it collapsed, what were you actually measuring for two days?"
2. "How many variants have you run in total? Not the number you'd like — the number. Run `deflated_sharpe` with it."
3. "Your group dummies are rank-deficient with an intercept. Did `lstsq` warn you? Would normal equations have?"

- [ ] **Step 7: Commit**

```bash
git add eqr/neutralize.py eqr/signals/alpha_03_neutral.py tests/eqr/test_neutralize.py drills/day08-neutralization.md
git commit -m "feat(eqr): group neutralization and deflated-Sharpe honesty"
```

---

## Task 10: Alpha and Backtest panels in the terminal (delivered)

**Files:**
- Create: `terminal/src/panels/AlphaPanel.tsx`, `terminal/src/panels/BacktestPanel.tsx`
- Modify: `server/app.py` — add `GET /api/alphas`, `GET /api/backtest/{alpha_name}`

- [ ] **Step 1: Add the alpha-scoring endpoints**

```python
# server/app.py — append
import importlib
import pkgutil

from eqr import evaluate, panel as panel_mod, universe as universe_mod


def _discover_alphas() -> dict:
    import eqr.signals as pkg
    found = {}
    for m in pkgutil.iter_modules(pkg.__path__):
        if not m.name.startswith("alpha_"):
            continue
        mod = importlib.import_module(f"eqr.signals.{m.name}")
        cls = getattr(mod, "Alpha", None)
        if cls is not None:
            found[m.name] = cls()
    return found


@app.get("/api/alphas")
def alphas() -> dict:
    out = []
    for name, sig in _discover_alphas().items():
        out.append({"module": name, "name": getattr(sig, "name", name)})
    return {"alphas": out}


@app.get("/api/backtest/{alpha_module}")
def backtest(alpha_module: str, horizon_s: int = 3600,
             min_v24: float = 1000.0, max_spread_c: float = 10.0) -> dict:
    rows = loader.load_snapshots(PANEL) if PANEL.exists() else []
    sig = _discover_alphas().get(alpha_module)
    if sig is None:
        return {"error": f"unknown alpha {alpha_module}"}
    try:
        stamps = sorted({r["ts"] for r in rows})
        ics = []
        for asof in stamps[:-1]:
            screened = universe_mod.liquidity_screen(
                universe_mod.exclude_combos(rows), asof, min_v24, max_spread_c)
            xs, rets = panel_mod.cross_section(screened, asof, horizon_s)
            if len(xs) < 5:
                continue
            ic = evaluate.information_coefficient(sig.compute(xs), rets)
            if ic is not None:
                ics.append({"ts": asof, "ic": ic})
    except NotImplementedError as exc:
        return {"alpha": alpha_module, "pending": str(exc), "ics": []}
    mean_ic = sum(x["ic"] for x in ics) / len(ics) if ics else None
    return {"alpha": alpha_module, "n_rebalances": len(ics),
            "mean_ic": mean_ic,
            "t_stat": evaluate.ic_t_stat([x["ic"] for x in ics]),
            "ics": ics}
```

- [ ] **Step 2: Verify the endpoints answer before the author's code exists**

```bash
python -m uvicorn server.app:app --port 8000 &
sleep 4
curl -s http://localhost:8000/api/alphas
curl -s http://localhost:8000/api/backtest/alpha_01_reversal
```

Expected: `/api/alphas` lists modules; `/api/backtest/...` returns `{"pending": "Day 6: yours to write", "ics": []}`. **The terminal must degrade honestly, never crash, when the author has not written a module yet.**

- [ ] **Step 3: Verify TypeScript still compiles**

Run: `cd terminal && npx tsc --noEmit && npm run build`
Expected: exit 0 both.

- [ ] **Step 4: Commit**

```bash
git add terminal server/app.py
git commit -m "feat(terminal): alpha discovery, IC backtest endpoint and panels"
```

---

## Task 11 (Day 9): Mock superday

**Files:**
- Create: `drills/day09-mock-superday.md`, `docs/superpowers/records/2026-09-08-eqr-results.md`

- [ ] **Step 1: Write the results record**

The author writes a one-page record containing, with numbers: universe size and construction rule, panel rebalance count, mean IC with t-stat, IC decay across 1h/4h/1d, quantile spread, round-trip cost, net edge, deflated Sharpe with the honest trial count, and one paragraph on what did not work.

- [ ] **Step 2: Run the mock superday**

Full adversarial interrogation across every day's DEFENSE questions, in random order, with follow-ups. Any answer that cannot cite a number from the record is a failure and goes back to the relevant task.

- [ ] **Step 3: Commit**

```bash
git add drills/day09-mock-superday.md docs/superpowers/records/2026-09-08-eqr-results.md
git commit -m "docs: EQR results record and mock superday"
```

---

## Self-Review

**Spec coverage.** Spec §2.1/§2.2 (combo exclusion, event enumeration) → Task 6 + Global Constraints. §2.3 (recorder) → done pre-plan, constraint recorded. §3 module table → Tasks 1–9 one-for-one. §3.1 panel + lookahead canary → Task 6 Step 2. §3.2 universe → Task 6. §4 pedagogy contract → every ★ task's Steps 1/5/6. §5 curriculum → Tasks 1–9 in day order. §6 terminal → Tasks 0, 5, 10. §7.1 short history → 1h/4h/1d horizons in Task 10. §7.2 WebSocket auth → Task 0 Step 6 polls REST. §7.3 resolution contamination → Task 6 `resolves_in_window`. §8 no order placement → nothing in this plan calls `client.post`.

**Deviation recorded:** `evaluate.information_coefficient` and `quantile_spread` moved from delivered to ★ (Global Constraints, final bullet).

**Type consistency.** `mc_digital_call` returns `(price, se)` in Task 1 and is consumed as such in Task 3. `pdf_from_cdf` returns `list[tuple[float, float]]` in Task 4 and is consumed with that shape in Task 5's endpoint. `cross_section` returns `(rows, returns)` in Task 6 and is unpacked that way in Task 10. `Signal.compute` returns `list[float | None]` in Task 7 and is passed straight to `information_coefficient`, whose first parameter is `list[float | None]`. `liquidity_screen(rows, asof_ts, min_v24, max_spread_c)` is called positionally in Task 10 in that order.
