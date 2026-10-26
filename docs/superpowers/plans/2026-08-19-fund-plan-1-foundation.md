# Fund Plan 1 — No-Capital-Risk Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the three pieces that carry no capital risk — an order-book recorder, the Risk Unit sizer, and a calibration harness that validates the risk model without any alpha model.

**Architecture:** Pure-math sizing library in `agent/risk_unit.py` with its measured inputs isolated in `agent/void_rates.py`; two top-level CLI scripts (`book_recorder.py`, `ru_calibration.py`) following the existing `find_momentum.py` / `backfill_probe.py` convention. Nothing here places an order or touches the execution path.

**Tech Stack:** Python 3.13, pytest, stdlib only (`math`, `json`, `pathlib`, `argparse`, `dataclasses`). No new dependencies. Existing helpers reused: `kalshi_client.KalshiClient`, `find_momentum._all_open_markets`, `momentum_filter._bid_cents/_ask_cents`, `agent.history.fetch_settled/group_settled/void_rate`.

**Spec:** `docs/superpowers/specs/2026-08-19-prediction-market-fund-design.md`

## Global Constraints

- **`is_live()` must remain `False`.** Nothing in this plan may call `post()` or `delete()`, or alter `agent/config.py` execution settings. Verified by test in Task 8.
- **Read the `_fp` fields.** The `/markets` payload has **no** `open_interest`, `volume_24h`, `volume`, `yes_bid` or `yes_ask` keys. Only `open_interest_fp`, `volume_24h_fp`, `volume_fp` (strings) and `yes_bid_dollars`, `yes_ask_dollars` (strings) exist. Reading the plain names returns `None`/0 silently.
- **`.get(key, [])` does not protect against `null`.** Kalshi sends `"series": null`. Always use `or []`.
- **Never commit `.env` or `*.pem`.**
- **Prices:** the codebase works in **cents** at the boundary (`_ask_cents` returns cents) and this plan's math works in **dollars 0–1**. Convert explicitly; never mix.
- **No invented data.** Any rate not measured from the API is `None`, not a guess.
- Windows console is cp1252 — set `PYTHONIOENCODING=utf-8` before printing vault text.

---

## File Structure

| file | responsibility |
|---|---|
| `agent/void_rates.py` (create) | Measured per-vertical abandonment rates + series→vertical lookup. Data, refreshable from the settled feed. |
| `agent/risk_unit.py` (create) | Pure RU math: per-contract RU, sizing, refusals, portfolio aggregation. No I/O, no network. |
| `book_recorder.py` (create) | CLI. Polls a watchlist and appends order-book snapshots to JSONL. |
| `ru_calibration.py` (create) | CLI. Replays recorded snapshots, compares realised adverse excursion to RU prediction. |
| `tests/test_void_rates.py` (create) | Lookup correctness, unknown-vertical behaviour. |
| `tests/test_risk_unit.py` (create) | RU math, refusals, aggregation. |
| `tests/test_book_recorder.py` (create) | Snapshot schema, `_fp` field handling, append semantics. |
| `tests/test_ru_calibration.py` (create) | Adverse-excursion measurement, breach-rate reporting. |

---

### Task 1: Void-rate table and vertical lookup

**Files:**
- Create: `agent/void_rates.py`
- Test: `tests/test_void_rates.py`

**Interfaces:**
- Consumes: nothing (leaf module)
- Produces:
  - `VOID_RATES: dict[str, float]` — vertical name → measured rate
  - `vertical_for_series(series_ticker: str) -> str | None`
  - `void_rate_for_series(series_ticker: str) -> float | None`
  - `DEFAULT_VOID_RATE: float`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_void_rates.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.void_rates import (DEFAULT_VOID_RATE, VOID_RATES,
                              vertical_for_series, void_rate_for_series)


def test_measured_rates_match_the_spec_table():
    """These are measured from the settled feed, not assumed. Spec section 3.2."""
    assert VOID_RATES["mlb_game"] == 0.005
    assert VOID_RATES["esports_series"] == 0.099
    assert VOID_RATES["scheduled_data"] == 0.0


def test_series_maps_to_its_vertical():
    assert vertical_for_series("KXMLBGAME") == "mlb_game"
    assert vertical_for_series("KXCS2GAME") == "esports_series"
    assert vertical_for_series("KXBTCD") == "scheduled_data"


def test_an_unmapped_series_returns_none_not_a_guess():
    """Invariant K: no invented data. An unknown series has no measured rate."""
    assert vertical_for_series("KXTOTALLYUNKNOWN") is None
    assert void_rate_for_series("KXTOTALLYUNKNOWN") is None


def test_the_conservative_default_is_the_worst_measured_rate():
    """A caller choosing to proceed without a measurement must not get an
    optimistic number. The default is the worst rate we have observed."""
    assert DEFAULT_VOID_RATE == max(VOID_RATES.values())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_void_rates.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.void_rates'`

- [ ] **Step 3: Write minimal implementation**

```python
# agent/void_rates.py
"""Measured abandonment rates: how often a contract settles at a price
rather than YES/NO.

The settled feed's `result` has THREE values -- `yes`, `no`, and `scalar`.
`scalar` marks a settlement at an exchange-set price, so a fraction of every
position's capital has an administratively-determined return regardless of
whether the thesis was right. Standard position sizing has no term for this.

Every number below was measured from Kalshi's own settled feed (see
LOOP_LOG.md findings 266-270, 305, 349-352, 354-357). Refresh with:

    python -c "import sys;sys.path.insert(0,'.');\\
from kalshi_client import KalshiClient;\\
from agent.history import fetch_settled,group_settled,void_rate;\\
r=void_rate(group_settled(fetch_settled(KalshiClient.from_env(),'KXATPMATCH')));\\
print(r.hits,'/',r.total)"
"""
from __future__ import annotations

# vertical -> measured event-level void rate
VOID_RATES: dict[str, float] = {
    "scheduled_data": 0.000,   # charts, daily crypto ladders, index sessions
    "mlb_game": 0.005,         # 4 of 876
    "mlb_player_leg": 0.009,   # 21 of 2,400 LEGS -- see note below
    "ufc_method": 0.017,       # 2 of 115
    "atp_match": 0.037,        # 35 of 944
    "wta_match": 0.040,        # 38 of 956
    "tennis_games_ladder": 0.053,   # 43 of 804
    "ufc_bout": 0.071,         # 9 of 127
    "esports_series": 0.099,   # 119 of 1,200 -- a FLOOR, cursor outstanding
}

# A caller that proceeds without a measurement must not be handed an
# optimistic number, so the fallback is the WORST observed rate.
DEFAULT_VOID_RATE: float = max(VOID_RATES.values())

# Series prefix -> vertical. Order matters: longer prefixes first, because
# KXMLBHR must not match the KXMLB* game rule.
_PREFIX_RULES: list[tuple[str, str]] = [
    ("KXMLBHR", "mlb_player_leg"),
    ("KXMLBRBI", "mlb_player_leg"),
    ("KXMLBGAME", "mlb_game"),
    ("KXATPGTOTAL", "tennis_games_ladder"),
    ("KXWTAGTOTAL", "tennis_games_ladder"),
    ("KXATPMATCH", "atp_match"),
    ("KXWTAMATCH", "wta_match"),
    ("KXUFCMOV", "ufc_method"),
    ("KXUFCVICROUND", "ufc_method"),
    ("KXUFCFIGHT", "ufc_bout"),
    ("KXCS2GAME", "esports_series"),
    ("KXCS2MAP", "esports_series"),
    ("KXLOLGAME", "esports_series"),
    ("KXBTCD", "scheduled_data"),
    ("KXBTC15M", "scheduled_data"),
    ("KXINXU", "scheduled_data"),
    ("KXTOPSONG", "scheduled_data"),
    ("KXTOPALBUM", "scheduled_data"),
    ("KXRAIN", "scheduled_data"),
]


def vertical_for_series(series_ticker: str) -> str | None:
    """The vertical whose measured void rate applies, or None if unmeasured."""
    t = (series_ticker or "").upper()
    for prefix, vertical in _PREFIX_RULES:
        if t.startswith(prefix):
            return vertical
    return None


def void_rate_for_series(series_ticker: str) -> float | None:
    """Measured rate for this series, or None. NEVER guesses."""
    vertical = vertical_for_series(series_ticker)
    return VOID_RATES[vertical] if vertical else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_void_rates.py -v`
Expected: 4 passed

- [ ] **Step 5: Run the full suite for regressions**

Run: `python -m pytest tests/ -q`
Expected: 561 passed (557 existing + 4 new)

- [ ] **Step 6: Commit**

```bash
git add agent/void_rates.py tests/test_void_rates.py
git commit -m "feat(risk): measured per-vertical void rates with no-guess lookup"
```

---

### Task 2: Risk Unit — per-contract math

**Files:**
- Create: `agent/risk_unit.py`
- Test: `tests/test_risk_unit.py`

**Interfaces:**
- Consumes: `agent.void_rates.void_rate_for_series`, `DEFAULT_VOID_RATE`
- Produces:
  - `SIGMA_MULTIPLE: float`
  - `FEE_PER_CONTRACT_USD: float`
  - `ru_per_contract(price: float, spread_cents: float, void_rate: float, side: str = "yes") -> float`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_risk_unit.py
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent.risk_unit import (FEE_PER_CONTRACT_USD, SIGMA_MULTIPLE,
                             ru_per_contract)


def test_ru_is_the_sum_of_its_three_terms():
    """Spec section 5: RU = volatility-scaled capital + certain cost + void haircut."""
    p, spread, v = 0.50, 4.0, 0.037
    got = ru_per_contract(p, spread_cents=spread, void_rate=v)
    sigma = math.sqrt(p * (1 - p))
    expected = (p * SIGMA_MULTIPLE * sigma
                + (0.5 * spread / 100.0 + FEE_PER_CONTRACT_USD)
                + p * v)
    assert got == pytest.approx(expected)


def test_a_mid_priced_contract_carries_more_risk_than_a_cheap_one():
    """sigma peaks at 50c. This is why 'risk 1% per trade' is meaningless on
    a binary: 3c and 60c with equal dollars are different risks."""
    mid = ru_per_contract(0.50, spread_cents=2.0, void_rate=0.0)
    cheap = ru_per_contract(0.05, spread_cents=2.0, void_rate=0.0)
    assert mid > cheap * 5


def test_the_no_side_uses_its_own_capital_at_risk():
    """Buying NO at 90c risks 10c, not 90c."""
    yes_at_90 = ru_per_contract(0.90, spread_cents=2.0, void_rate=0.05, side="yes")
    no_at_90 = ru_per_contract(0.90, spread_cents=2.0, void_rate=0.05, side="no")
    assert no_at_90 < yes_at_90


def test_a_wide_book_is_dominated_by_the_exit_cost():
    """Measured spreads run 5-9c on futures books and 23-79c on illiquid
    court rungs. On a wide book this term alone can exceed any edge."""
    tight = ru_per_contract(0.50, spread_cents=2.0, void_rate=0.0)
    wide = ru_per_contract(0.50, spread_cents=40.0, void_rate=0.0)
    assert wide > tight * 1.5


def test_the_void_term_scales_with_the_measured_rate():
    """The same edge in esports must clear a ~10% chance of not being paid
    on the thesis at all."""
    mlb = ru_per_contract(0.50, spread_cents=2.0, void_rate=0.005)
    esports = ru_per_contract(0.50, spread_cents=2.0, void_rate=0.099)
    assert esports > mlb


def test_prices_outside_zero_to_one_are_rejected():
    """Cents leaking in where dollars are expected is the likeliest caller bug."""
    with pytest.raises(ValueError):
        ru_per_contract(50.0, spread_cents=2.0, void_rate=0.0)
    with pytest.raises(ValueError):
        ru_per_contract(-0.1, spread_cents=2.0, void_rate=0.0)


def test_an_unknown_side_is_rejected():
    with pytest.raises(ValueError):
        ru_per_contract(0.5, spread_cents=2.0, void_rate=0.0, side="none")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_risk_unit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.risk_unit'`

- [ ] **Step 3: Write minimal implementation**

```python
# agent/risk_unit.py
"""The Risk Unit: position sizing for binary contracts.

"Risk 1% per trade" is meaningless here. Buying YES at 3c and at 60c with the
same dollars are entirely different risks: the first has 3c of downside and a
tiny chance of 97c, the second 60c down against 40c up. So the unit is
EXPECTED ADVERSE EXCURSION, not notional.

    1 RU = $1 of expected adverse move over the holding period.

Per contract, at price p (DOLLARS 0-1):

    RU = p * k * sqrt(p(1-p))        volatility-scaled capital at risk
       + (half-spread + fee)         certain round-trip cost
       + p * v                       abandonment haircut

See docs/superpowers/specs/2026-08-19-prediction-market-fund-design.md section 5.
"""
from __future__ import annotations

import math

# The planned adverse traverse, in standard deviations. Tuned ONLY by the
# monthly offline re-fit (spec section 7.4), never by the online learner.
SIGMA_MULTIPLE: float = 2.0

# Placeholder until the real Kalshi schedule is read and encoded -- spec
# section 12, open question 2. Deliberately non-zero so sizing is never
# optimistic about costs.
FEE_PER_CONTRACT_USD: float = 0.01


def ru_per_contract(price: float, spread_cents: float, void_rate: float,
                    side: str = "yes") -> float:
    """Risk Units carried by ONE contract.

    price        entry price in DOLLARS 0-1 (not cents)
    spread_cents bid-ask spread in CENTS, as the API reports it
    void_rate    measured abandonment rate for the vertical, 0-1
    side         "yes" or "no" -- decides which end is capital at risk
    """
    if not 0.0 <= price <= 1.0:
        raise ValueError(f"price must be dollars 0-1, got {price!r} "
                         "(did you pass cents?)")
    if side not in ("yes", "no"):
        raise ValueError(f"side must be 'yes' or 'no', got {side!r}")
    if spread_cents < 0 or not 0.0 <= void_rate <= 1.0:
        raise ValueError("spread_cents must be >=0 and void_rate 0-1")

    capital = price if side == "yes" else (1.0 - price)
    sigma = math.sqrt(price * (1.0 - price))

    vol_term = capital * SIGMA_MULTIPLE * sigma
    cost_term = 0.5 * spread_cents / 100.0 + FEE_PER_CONTRACT_USD
    void_term = capital * void_rate
    return vol_term + cost_term + void_term
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_risk_unit.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add agent/risk_unit.py tests/test_risk_unit.py
git commit -m "feat(risk): per-contract Risk Unit with volatility, cost and void terms"
```

---

### Task 3: Risk Unit — sizing and the two hard refusals

**Files:**
- Modify: `agent/risk_unit.py`
- Modify: `tests/test_risk_unit.py`

**Interfaces:**
- Consumes: `ru_per_contract` (Task 2), `agent.void_rates` (Task 1)
- Produces:
  - `Sizing` dataclass with fields `contracts: int`, `ru_per_contract: float`, `total_ru: float`, `refused: bool`, `reason: str`
  - `MIN_PRICE_DOLLARS: float`
  - `UNSIZEABLE_STRUCTURES: frozenset[str]`
  - `size_position(ru_budget, price, spread_cents, void_rate, structure="threshold_ladder", side="yes") -> Sizing`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_risk_unit.py
from agent.risk_unit import (MIN_PRICE_DOLLARS, UNSIZEABLE_STRUCTURES, Sizing,
                             size_position)


def test_sizing_spends_the_budget_in_risk_units_not_dollars():
    s = size_position(ru_budget=10.0, price=0.50, spread_cents=2.0,
                      void_rate=0.0)
    assert not s.refused
    assert s.contracts >= 1
    assert s.total_ru <= 10.0 + 1e-9
    # one more contract would breach the budget
    assert (s.contracts + 1) * s.ru_per_contract > 10.0


def test_a_wide_book_gets_a_smaller_position_for_the_same_budget():
    tight = size_position(10.0, 0.50, spread_cents=2.0, void_rate=0.0)
    wide = size_position(10.0, 0.50, spread_cents=40.0, void_rate=0.0)
    assert wide.contracts < tight.contracts


def test_a_high_void_vertical_gets_a_smaller_position():
    """Esports at 9.9% must be sized smaller than MLB at 0.5% for the same
    budget, automatically."""
    mlb = size_position(10.0, 0.50, spread_cents=2.0, void_rate=0.005)
    esports = size_position(10.0, 0.50, spread_cents=2.0, void_rate=0.099)
    assert esports.contracts < mlb.contracts


def test_sub_three_cent_positions_are_refused_not_sized():
    """A percentage stop is sub-tick there: 50% of 1.3c is not a price level.
    These are hold-to-resolution, premium spent -- not a position managed."""
    s = size_position(10.0, price=0.013, spread_cents=1.0, void_rate=0.0)
    assert s.refused
    assert s.contracts == 0
    assert "sub" in s.reason.lower()
    assert MIN_PRICE_DOLLARS == 0.03


def test_unknown_structure_is_refused_not_sized():
    """If the exposure is not known it cannot be sized. Spec section 5."""
    for structure in ("disputed", "indeterminate"):
        s = size_position(10.0, 0.50, spread_cents=2.0, void_rate=0.0,
                          structure=structure)
        assert s.refused, structure
        assert s.contracts == 0
        assert "structure" in s.reason.lower()
    assert UNSIZEABLE_STRUCTURES == frozenset({"disputed", "indeterminate"})


def test_a_known_structure_is_sized_normally():
    for structure in ("threshold_ladder", "exclusive_field",
                      "two_sided_handicap", "independent_basket",
                      "fixed_cardinality", "standalone_binary"):
        s = size_position(10.0, 0.50, spread_cents=2.0, void_rate=0.0,
                          structure=structure)
        assert not s.refused, structure


def test_a_budget_too_small_for_one_contract_is_refused():
    s = size_position(ru_budget=0.001, price=0.50, spread_cents=2.0,
                      void_rate=0.0)
    assert s.refused
    assert s.contracts == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_risk_unit.py -v`
Expected: FAIL with `ImportError: cannot import name 'MIN_PRICE_DOLLARS'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to agent/risk_unit.py
from dataclasses import dataclass

# Below this, a percentage stop is smaller than one tick, so the position
# cannot be managed -- only held to resolution. Matches the existing
# RiskLimits.min_price_cents = 3.0.
MIN_PRICE_DOLLARS: float = 0.03

# Structures whose true exposure is unknown. Refused, never sized.
UNSIZEABLE_STRUCTURES: frozenset[str] = frozenset({"disputed", "indeterminate"})


@dataclass(frozen=True)
class Sizing:
    """The result of sizing one candidate. `refused` is not an error --
    refusing is a normal, frequent outcome."""
    contracts: int
    ru_per_contract: float
    total_ru: float
    refused: bool
    reason: str


def size_position(ru_budget: float, price: float, spread_cents: float,
                  void_rate: float, structure: str = "threshold_ladder",
                  side: str = "yes") -> Sizing:
    """How many contracts fit inside `ru_budget` Risk Units.

    RU is linear in contract count, so sizing is a division -- but the two
    refusals below are checked FIRST and are not overridable by a larger
    budget.
    """
    if structure in UNSIZEABLE_STRUCTURES:
        return Sizing(0, 0.0, 0.0, True,
                      f"unknown structure: {structure!r} -- exposure is not "
                      "known well enough to size")

    capital = price if side == "yes" else (1.0 - price)
    if capital < MIN_PRICE_DOLLARS:
        return Sizing(0, 0.0, 0.0, True,
                      f"sub-{MIN_PRICE_DOLLARS * 100:.0f}c position: a "
                      "percentage stop would be sub-tick; hold-to-resolution "
                      "only")

    per = ru_per_contract(price, spread_cents, void_rate, side)
    contracts = int(ru_budget // per)
    if contracts < 1:
        return Sizing(0, per, 0.0, True,
                      f"budget {ru_budget:.4f} RU is below one contract "
                      f"at {per:.4f} RU")
    return Sizing(contracts, per, contracts * per, False, "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_risk_unit.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add agent/risk_unit.py tests/test_risk_unit.py
git commit -m "feat(risk): RU sizing with sub-3c and unknown-structure refusals"
```

---

### Task 4: Portfolio-level RU aggregation

**Files:**
- Modify: `agent/risk_unit.py`
- Modify: `tests/test_risk_unit.py`

**Interfaces:**
- Consumes: `Sizing` (Task 3)
- Produces:
  - `cluster_key(event_ticker: str, settlement_source: str) -> str`
  - `portfolio_ru(positions: list[tuple[str, float]]) -> float`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_risk_unit.py
import math as _math

from agent.risk_unit import cluster_key, portfolio_ru


def test_positions_in_one_cluster_get_no_diversification_credit():
    """Alcaraz at 61c to compete and 19c to win is ONE position, not two."""
    same = [("c1", 3.0), ("c1", 4.0)]
    assert portfolio_ru(same) == pytest.approx(7.0)


def test_positions_across_clusters_are_root_sum_squared():
    across = [("c1", 3.0), ("c2", 4.0)]
    assert portfolio_ru(across) == pytest.approx(5.0)


def test_clustering_is_by_event_or_by_settlement_source():
    """Two contracts on one event are correlated; so are two contracts that
    depend on the same authority publishing."""
    assert cluster_key("KXATP-26USO", "ATP") == cluster_key("KXATP-26USO", "ATP")
    assert cluster_key("KXATP-26USO", "ATP") != cluster_key("KXNFL-27", "ATP")


def test_an_empty_book_carries_no_risk():
    assert portfolio_ru([]) == 0.0


def test_aggregation_never_exceeds_the_linear_sum():
    """Sanity: sqrt-combining across clusters cannot invent risk."""
    positions = [("a", 2.0), ("b", 3.0), ("c", 6.0)]
    assert portfolio_ru(positions) <= sum(ru for _, ru in positions)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_risk_unit.py -v`
Expected: FAIL with `ImportError: cannot import name 'cluster_key'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to agent/risk_unit.py
import math as _math
from collections import defaultdict


def cluster_key(event_ticker: str, settlement_source: str) -> str:
    """Positions sharing an EVENT or a SETTLEMENT SOURCE are not independent.

    The vault documents why: Alcaraz priced 61c to compete and 19c to win is
    one position; and every contract settled by one authority shares that
    authority's failure mode.
    """
    return f"{event_ticker or '?'}|{settlement_source or '?'}"


def portfolio_ru(positions: list[tuple[str, float]]) -> float:
    """Total Risk Units across a book.

    LINEAR within a cluster (no diversification credit), ROOT-SUM-SQUARE
    across clusters.
    """
    if not positions:
        return 0.0
    by_cluster: dict[str, float] = defaultdict(float)
    for key, ru in positions:
        by_cluster[key] += ru
    return _math.sqrt(sum(v * v for v in by_cluster.values()))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_risk_unit.py -v`
Expected: 19 passed

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: 580 passed

- [ ] **Step 6: Commit**

```bash
git add agent/risk_unit.py tests/test_risk_unit.py
git commit -m "feat(risk): portfolio RU aggregation, linear within cluster"
```

---

### Task 5: Book recorder — snapshot extraction

**Files:**
- Create: `book_recorder.py`
- Test: `tests/test_book_recorder.py`

**Interfaces:**
- Consumes: `momentum_filter._bid_cents`, `momentum_filter._ask_cents`
- Produces:
  - `snapshot_from_market(market: dict, ts: int) -> dict | None`
  - `SNAPSHOT_FIELDS: tuple[str, ...]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_book_recorder.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from book_recorder import SNAPSHOT_FIELDS, snapshot_from_market


def _market(**over):
    m = {"ticker": "KXMLBGAME-26AUG22ATLMIL-MIL",
         "event_ticker": "KXMLBGAME-26AUG22ATLMIL",
         "yes_bid_dollars": "0.4500", "yes_ask_dollars": "0.4700",
         "open_interest_fp": "6460.04", "volume_24h_fp": "6923.25"}
    m.update(over)
    return m


def test_a_snapshot_carries_every_declared_field():
    snap = snapshot_from_market(_market(), ts=1_700_000_000)
    assert set(snap) == set(SNAPSHOT_FIELDS)


def test_prices_are_read_from_the_dollars_strings_and_stored_as_cents():
    """The payload has NO yes_bid/yes_ask keys -- only the _dollars strings."""
    snap = snapshot_from_market(_market(), ts=1)
    assert snap["yes_bid_c"] == 45.0
    assert snap["yes_ask_c"] == 47.0
    assert snap["spread_c"] == 2.0


def test_size_fields_are_read_from_the_fp_strings():
    """open_interest / volume_24h DO NOT EXIST; only the _fp string forms."""
    snap = snapshot_from_market(_market(), ts=1)
    assert snap["oi"] == 6460.04
    assert snap["v24"] == 6923.25


def test_the_plain_field_names_are_ignored_even_if_present():
    """Guards against a future payload where both exist and disagree."""
    snap = snapshot_from_market(
        _market(open_interest=1.0, volume_24h=2.0), ts=1)
    assert snap["oi"] == 6460.04


def test_a_market_with_no_quotes_is_dropped():
    """A book with no bid AND no ask carries no information to record."""
    assert snapshot_from_market(
        _market(yes_bid_dollars=None, yes_ask_dollars=None), ts=1) is None


def test_the_series_is_derived_from_the_ticker():
    snap = snapshot_from_market(_market(), ts=1)
    assert snap["series"] == "KXMLBGAME"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_book_recorder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'book_recorder'`

- [ ] **Step 3: Write minimal implementation**

```python
# book_recorder.py
"""Record order-book snapshots so the fast markets become backtestable.

Kalshi's candle history is thin and WORST where liquidity is best: measured
2026-08-19, KXALIENS (long-dated) has 555 hourly candles over 30 days while
KXBTCD (a daily ladder) has ZERO at every window. The markets with the most
tradeable flow leave the least history, so any backtest built only on
available candles is biased toward slow, thin, long-dated contracts.

The only fix is to start recording now. This script has no execution path and
places no orders.

    python book_recorder.py --series KXBTCD --series KXMLBGAME --interval 60
"""
from __future__ import annotations

from momentum_filter import _ask_cents, _bid_cents

SNAPSHOT_FIELDS: tuple[str, ...] = (
    "ts", "series", "ticker", "event_ticker",
    "yes_bid_c", "yes_ask_c", "spread_c", "oi", "v24",
)


def _fp(value) -> float:
    """A `_fp` string field as a float. These ship as STRINGS."""
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def snapshot_from_market(market: dict, ts: int) -> dict | None:
    """One row of the recording, or None if the book carries no quote.

    Reads ONLY the `_dollars` and `_fp` forms: the plain `yes_bid`,
    `yes_ask`, `open_interest` and `volume_24h` keys DO NOT EXIST on this
    payload and reading them returns None or 0 silently.
    """
    bid = _bid_cents(market)
    ask = _ask_cents(market)
    if bid is None and ask is None:
        return None
    ticker = market.get("ticker") or ""
    return {
        "ts": ts,
        "series": ticker.split("-", 1)[0],
        "ticker": ticker,
        "event_ticker": market.get("event_ticker") or "",
        "yes_bid_c": bid,
        "yes_ask_c": ask,
        "spread_c": (ask - bid) if (bid is not None and ask is not None) else None,
        "oi": _fp(market.get("open_interest_fp")),
        "v24": _fp(market.get("volume_24h_fp")),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_book_recorder.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add book_recorder.py tests/test_book_recorder.py
git commit -m "feat(data): book snapshot extraction using the _fp/_dollars fields"
```

---

### Task 6: Book recorder — append writer and CLI

**Files:**
- Modify: `book_recorder.py`
- Modify: `tests/test_book_recorder.py`

**Interfaces:**
- Consumes: `snapshot_from_market` (Task 5), `kalshi_client.KalshiClient`, `find_momentum._all_open_markets`
- Produces:
  - `append_snapshots(path: Path, snapshots: list[dict]) -> int`
  - `record_once(client, series_list: list[str], path: Path, ts: int) -> int`
  - `main() -> int`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_book_recorder.py
import json

from book_recorder import append_snapshots, record_once


def test_snapshots_append_as_jsonl_without_rewriting(tmp_path):
    p = tmp_path / "book.jsonl"
    assert append_snapshots(p, [{"ts": 1, "ticker": "A"}]) == 1
    assert append_snapshots(p, [{"ts": 2, "ticker": "B"}]) == 1
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["ticker"] == "A"
    assert json.loads(lines[1])["ticker"] == "B"


def test_appending_nothing_creates_no_file(tmp_path):
    p = tmp_path / "book.jsonl"
    assert append_snapshots(p, []) == 0
    assert not p.exists()


def test_record_once_writes_one_row_per_quoted_market(tmp_path):
    class FakeClient:
        pass

    calls = []

    def fake_all_open(client, series):
        calls.append(series)
        return [{"ticker": f"{series}-X", "event_ticker": f"{series}-E",
                 "yes_bid_dollars": "0.4000", "yes_ask_dollars": "0.4200",
                 "open_interest_fp": "10", "volume_24h_fp": "5"}]

    import book_recorder
    original = book_recorder._all_open_markets
    book_recorder._all_open_markets = fake_all_open
    try:
        p = tmp_path / "book.jsonl"
        n = record_once(FakeClient(), ["KXA", "KXB"], p, ts=99)
    finally:
        book_recorder._all_open_markets = original

    assert n == 2
    assert calls == ["KXA", "KXB"]
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]
    assert {r["series"] for r in rows} == {"KXA", "KXB"}
    assert all(r["ts"] == 99 for r in rows)


def test_a_dead_series_does_not_abort_the_sweep(tmp_path):
    """Invariant J: announce, do not crash. One bad series must not lose the
    whole recording pass."""
    import book_recorder

    def fake_all_open(client, series):
        if series == "KXBAD":
            raise RuntimeError("boom")
        return [{"ticker": f"{series}-X", "event_ticker": "E",
                 "yes_bid_dollars": "0.4000", "yes_ask_dollars": "0.4200",
                 "open_interest_fp": "1", "volume_24h_fp": "1"}]

    original = book_recorder._all_open_markets
    book_recorder._all_open_markets = fake_all_open
    try:
        p = tmp_path / "book.jsonl"
        n = record_once(object(), ["KXBAD", "KXGOOD"], p, ts=1)
    finally:
        book_recorder._all_open_markets = original
    assert n == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_book_recorder.py -v`
Expected: FAIL with `ImportError: cannot import name 'append_snapshots'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to book_recorder.py
import argparse
import json
import time
from pathlib import Path

from find_momentum import _all_open_markets
from kalshi_client import KalshiClient


def append_snapshots(path: Path, snapshots: list[dict]) -> int:
    """Append rows as JSONL. Never rewrites, so a long recording is safe to
    interrupt at any moment."""
    if not snapshots:
        return 0
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for snap in snapshots:
            fh.write(json.dumps(snap) + "\n")
    return len(snapshots)


def record_once(client, series_list: list[str], path: Path, ts: int) -> int:
    """One sweep over the watchlist. Returns rows written.

    A series that errors is skipped and ANNOUNCED -- it must not abort the
    pass, or one dead ticker costs the whole recording window.
    """
    rows: list[dict] = []
    for series in series_list:
        try:
            markets = _all_open_markets(client, series)
        except Exception as exc:                      # noqa: BLE001
            print(f"  skip {series}: {type(exc).__name__}")
            continue
        for market in markets or []:
            snap = snapshot_from_market(market, ts)
            if snap is not None:
                rows.append(snap)
    return append_snapshots(path, rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--series", action="append", required=True,
                    help="series ticker to record; repeatable")
    ap.add_argument("--out", default="state/book_recording.jsonl")
    ap.add_argument("--interval", type=int, default=60,
                    help="seconds between sweeps")
    ap.add_argument("--sweeps", type=int, default=0,
                    help="number of sweeps; 0 means run until interrupted")
    args = ap.parse_args()

    client = KalshiClient.from_env()
    path = Path(args.out)
    swept = 0
    try:
        while args.sweeps == 0 or swept < args.sweeps:
            ts = int(time.time())
            n = record_once(client, args.series, path, ts)
            swept += 1
            print(f"[{ts}] sweep {swept}: {n} rows -> {path}")
            if args.sweeps and swept >= args.sweeps:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\nstopped after {swept} sweeps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_book_recorder.py -v`
Expected: 10 passed

- [ ] **Step 5: Smoke-test the CLI against the live API**

Run: `PYTHONIOENCODING=utf-8 python book_recorder.py --series KXMLBGAME --sweeps 1 --out state/_smoke.jsonl`
Expected: prints `sweep 1: N rows` with N > 0, exit 0

- [ ] **Step 6: Commit**

```bash
rm -f state/_smoke.jsonl
git add book_recorder.py tests/test_book_recorder.py
git commit -m "feat(data): book recorder CLI with resilient per-series sweep"
```

---

### Task 7: RU calibration harness

**Files:**
- Create: `ru_calibration.py`
- Test: `tests/test_ru_calibration.py`

**Interfaces:**
- Consumes: `agent.risk_unit.ru_per_contract`, `agent.void_rates.void_rate_for_series`
- Produces:
  - `adverse_excursion(entry_price_c: float, path_c: list[float], side: str = "yes") -> float`
  - `BreachStats` dataclass with `n: int`, `breaches: int`, `rate: float`, `nominal: float`
  - `breach_stats(observations: list[tuple[float, float]], nominal: float) -> BreachStats`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ru_calibration.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from ru_calibration import BreachStats, adverse_excursion, breach_stats


def test_adverse_excursion_is_the_worst_drawdown_for_a_yes_long():
    """Entered at 50c, the path dipped to 38c: 12c of adverse move."""
    assert adverse_excursion(50.0, [50.0, 46.0, 38.0, 61.0]) == pytest.approx(0.12)


def test_a_path_that_never_goes_against_you_has_zero_excursion():
    assert adverse_excursion(50.0, [50.0, 55.0, 70.0]) == 0.0


def test_the_no_side_measures_the_opposite_direction():
    """Short YES / long NO is hurt when the price RISES."""
    assert adverse_excursion(50.0, [50.0, 72.0], side="no") == pytest.approx(0.22)


def test_an_empty_path_has_no_measurable_excursion():
    assert adverse_excursion(50.0, []) == 0.0


def test_breach_rate_counts_positions_whose_move_exceeded_their_RU():
    """(realised adverse excursion, predicted RU) pairs."""
    obs = [(0.30, 0.20), (0.10, 0.20), (0.05, 0.20), (0.50, 0.20)]
    stats = breach_stats(obs, nominal=0.05)
    assert stats.n == 4
    assert stats.breaches == 2
    assert stats.rate == pytest.approx(0.5)
    assert stats.nominal == 0.05


def test_an_empty_sample_reports_no_rate_rather_than_zero():
    """Zero breaches out of zero observations is not a 0% breach rate."""
    stats = breach_stats([], nominal=0.05)
    assert stats.n == 0
    assert stats.rate is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ru_calibration.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ru_calibration'`

- [ ] **Step 3: Write minimal implementation**

```python
# ru_calibration.py
"""Validate the RISK model without any alpha model.

These are different questions and conflating them is a common failure:

    alpha validation -- does the signal predict direction?
    risk validation  -- does a position sized at 1 RU actually realise about
                        $1 of adverse excursion out of sample?

The second needs no alpha at all: replay recorded books, take systematic
entries, and compare realised adverse excursion against the RU prediction. If
the void term is right, esports positions should breach their RU far more
often than MLB games. That is directly falsifiable.

A calibrated risk model is worth more than an uncalibrated alpha model,
because it is what keeps the account solvent while the alpha search runs.

Spec section 7.3.
"""
from __future__ import annotations

from dataclasses import dataclass


def adverse_excursion(entry_price_c: float, path_c: list[float],
                      side: str = "yes") -> float:
    """Worst move AGAINST the position, in DOLLARS per contract.

    entry_price_c  entry price in cents
    path_c         subsequent prices in cents, in time order
    side           "yes" (hurt by falls) or "no" (hurt by rises)
    """
    if not path_c:
        return 0.0
    if side == "yes":
        worst = min(path_c)
        move_c = max(0.0, entry_price_c - worst)
    else:
        worst = max(path_c)
        move_c = max(0.0, worst - entry_price_c)
    return move_c / 100.0


@dataclass(frozen=True)
class BreachStats:
    """How often realised adverse excursion exceeded the RU prediction.

    `rate` is None for an empty sample: zero breaches out of zero
    observations is not a 0% breach rate, and reporting it as one would be
    the same survivorship error the repo already documents.
    """
    n: int
    breaches: int
    rate: float | None
    nominal: float


def breach_stats(observations: list[tuple[float, float]],
                 nominal: float) -> BreachStats:
    """observations: (realised_adverse_excursion_usd, predicted_ru_usd) pairs.

    `nominal` is the breach rate the model implies, so the caller can compare
    observed against expected rather than eyeballing a bare number.
    """
    n = len(observations)
    if n == 0:
        return BreachStats(0, 0, None, nominal)
    breaches = sum(1 for realised, predicted in observations
                   if realised > predicted)
    return BreachStats(n, breaches, breaches / n, nominal)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ru_calibration.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add ru_calibration.py tests/test_ru_calibration.py
git commit -m "feat(risk): RU calibration primitives -- adverse excursion and breach rate"
```

---

### Task 8: Calibration replay CLI and the execution-gate guard

**Files:**
- Modify: `ru_calibration.py`
- Modify: `tests/test_ru_calibration.py`

**Interfaces:**
- Consumes: `adverse_excursion`, `breach_stats` (Task 7), `agent.risk_unit.ru_per_contract`, `agent.void_rates.void_rate_for_series`, `agent.void_rates.DEFAULT_VOID_RATE`
- Produces:
  - `load_recording(path: Path) -> dict[str, list[dict]]`
  - `calibrate(by_ticker: dict[str, list[dict]], horizon: int) -> dict[str, BreachStats]`
  - `main() -> int`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_ru_calibration.py
import json

from ru_calibration import calibrate, load_recording


def _row(ticker, ts, bid, ask, series=None):
    return {"ts": ts, "ticker": ticker,
            "series": series or ticker.split("-", 1)[0],
            "event_ticker": "E", "yes_bid_c": bid, "yes_ask_c": ask,
            "spread_c": ask - bid, "oi": 1000.0, "v24": 100.0}


def test_a_recording_loads_grouped_by_ticker_in_time_order(tmp_path):
    p = tmp_path / "rec.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in [
        _row("KXA-1", 3, 40, 42), _row("KXA-1", 1, 50, 52),
        _row("KXB-1", 2, 10, 12)]), encoding="utf-8")
    by_ticker = load_recording(p)
    assert set(by_ticker) == {"KXA-1", "KXB-1"}
    assert [r["ts"] for r in by_ticker["KXA-1"]] == [1, 3]


def test_calibration_reports_breaches_per_vertical(tmp_path):
    """A book that collapses 50c -> 5c must breach its RU; a flat one must not."""
    p = tmp_path / "rec.jsonl"
    rows = []
    for ts, price in enumerate([50, 45, 30, 5], start=1):
        rows.append(_row("KXMLBGAME-X", ts, price - 1, price + 1,
                         series="KXMLBGAME"))
    for ts, price in enumerate([50, 50, 50, 50], start=1):
        rows.append(_row("KXMLBGAME-Y", ts, price - 1, price + 1,
                         series="KXMLBGAME"))
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    stats = calibrate(load_recording(p), horizon=3)
    assert "mlb_game" in stats
    assert stats["mlb_game"].n == 2
    assert stats["mlb_game"].breaches == 1


def test_a_ticker_with_too_short_a_path_is_skipped(tmp_path):
    p = tmp_path / "rec.jsonl"
    p.write_text(json.dumps(_row("KXMLBGAME-Z", 1, 49, 51,
                                 series="KXMLBGAME")), encoding="utf-8")
    stats = calibrate(load_recording(p), horizon=3)
    assert stats == {} or stats["mlb_game"].n == 0


def test_execution_stays_disabled_throughout_this_plan():
    """GLOBAL CONSTRAINT: nothing in Plan 1 may enable execution."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from agent.risk import RISK
    assert RISK.is_live() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ru_calibration.py -v`
Expected: FAIL with `ImportError: cannot import name 'load_recording'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to ru_calibration.py
import argparse
import json
from collections import defaultdict
from pathlib import Path

from agent.risk_unit import ru_per_contract
from agent.void_rates import DEFAULT_VOID_RATE, vertical_for_series, void_rate_for_series

# With SIGMA_MULTIPLE = 2.0 the model plans for a two-sigma adverse traverse,
# so a well-calibrated book should breach only occasionally. This is the
# number the observed rate is compared against, not a target to hit.
NOMINAL_BREACH_RATE = 0.05


def load_recording(path: Path) -> dict[str, list[dict]]:
    """Recorded JSONL grouped by ticker, each series sorted by timestamp."""
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            by_ticker[row["ticker"]].append(row)
    for rows in by_ticker.values():
        rows.sort(key=lambda r: r["ts"])
    return dict(by_ticker)


def calibrate(by_ticker: dict[str, list[dict]],
              horizon: int) -> dict[str, BreachStats]:
    """Systematic entry at each ticker's first quote, held `horizon` steps.

    NO ALPHA MODEL: every ticker is entered, so this measures the RISK model
    alone. Grouped by vertical because the void term is vertical-specific.
    """
    obs_by_vertical: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for ticker, rows in by_ticker.items():
        if len(rows) < 2:
            continue
        entry, path = rows[0], rows[1:1 + horizon]
        if not path:
            continue
        ask = entry.get("yes_ask_c")
        spread = entry.get("spread_c")
        if ask is None or spread is None:
            continue

        series = entry.get("series") or ticker.split("-", 1)[0]
        vertical = vertical_for_series(series)
        rate = void_rate_for_series(series)
        if rate is None:
            vertical, rate = "unmeasured", DEFAULT_VOID_RATE

        predicted = ru_per_contract(ask / 100.0, spread_cents=spread,
                                    void_rate=rate)
        mids = [r["yes_ask_c"] for r in path if r.get("yes_ask_c") is not None]
        realised = adverse_excursion(ask, mids)
        obs_by_vertical[vertical].append((realised, predicted))

    return {v: breach_stats(obs, NOMINAL_BREACH_RATE)
            for v, obs in obs_by_vertical.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recording", default="state/book_recording.jsonl")
    ap.add_argument("--horizon", type=int, default=10,
                    help="snapshots held after entry")
    args = ap.parse_args()

    by_ticker = load_recording(Path(args.recording))
    stats = calibrate(by_ticker, args.horizon)
    if not stats:
        print("no ticker had enough snapshots to measure -- record longer")
        return 0

    print(f"RU calibration over {len(by_ticker)} tickers, "
          f"horizon {args.horizon} snapshots")
    print(f"{'vertical':22} {'n':>6} {'breaches':>9} {'rate':>8} {'nominal':>8}")
    for vertical, s in sorted(stats.items()):
        rate = "n/a" if s.rate is None else f"{s.rate:.1%}"
        print(f"  {vertical:20} {s.n:6} {s.breaches:9} {rate:>8} "
              f"{s.nominal:8.1%}")
    print("\nA rate far ABOVE nominal means RU is under-stating risk; far "
          "BELOW means it is over-stating and positions are too small.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ru_calibration.py -v`
Expected: 10 passed

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: 594 passed

- [ ] **Step 6: Verify the execution gate is untouched**

Run: `python -c "import sys;sys.path.insert(0,'.');from agent.risk import RISK;print('is_live =',RISK.is_live())"`
Expected: `is_live = False`

- [ ] **Step 7: Commit**

```bash
git add ru_calibration.py tests/test_ru_calibration.py
git commit -m "feat(risk): RU calibration replay CLI grouped by vertical"
```

---

## Self-Review

**Spec coverage:**

| spec section | task |
|---|---|
| §5 RU formula (three terms) | Task 2 |
| §5 two hard refusals | Task 3 |
| §5 portfolio aggregation | Task 4 |
| §3.2 measured void rates | Task 1 |
| §6 Track 2 recorder | Tasks 5–6 |
| §7.3 risk validation without alpha | Tasks 7–8 |
| §9.3 execution gate unchanged | Task 8, Step 6 |

Deliberately **not** covered here — they belong to Plans 2 and 3: contract-keyed retrieval (§4.1), estimator (§4.2), Stage C strategy (§10), the learner (§8), DSR (§7.2). §6 Track 1 backtesting is unblocked by this plan but not implemented in it.

**Placeholder scan:** `FEE_PER_CONTRACT_USD` is a named placeholder, flagged in spec §12 open question 2 and set non-zero so sizing is never optimistic about costs. No `TBD`/`TODO` markers.

**Type consistency:** `ru_per_contract(price, spread_cents, void_rate, side)` is used with identical argument names in Tasks 3 and 8. `Sizing` fields match between Task 3's definition and its tests. `BreachStats.rate` is `float | None` in Task 7 and handled as `None` in Task 8's `main()`. `snapshot_from_market` returns the keys `load_recording`/`calibrate` read (`ts`, `ticker`, `series`, `yes_ask_c`, `spread_c`).

**Units:** `ru_per_contract` takes DOLLARS and raises on out-of-range input; `adverse_excursion` takes CENTS and returns DOLLARS; `calibrate` converts explicitly at the call site.
