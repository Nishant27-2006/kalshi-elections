# Whole-branch code review fixes -- fund/plan-1-foundation

Base: `35b778d`, 604 tests passing. All six fixes applied independently, full
suite kept green after each. Final suite: **609 passed** (5 new tests added:
1 in Fix 1, 1 in Fix 2, 1 in Fix 4, 2 in Fix 5; Fix 3 and Fix 6 strengthened
existing tests / comments without adding new ones).

`SIGMA_MULTIPLE` and every other constant in `agent/risk_unit.py`'s RU
formula were left untouched, per instruction. `agent/config.py` and
`agent/risk.py` were not touched. `RISK.is_live()` still returns `False`
(verified by the existing `test_execution_stays_disabled_throughout_this_plan`
test, which still passes). No third-party dependencies were added. Nothing
under `state/` was created or committed; a scratch `tmp_rec.jsonl` used to
manually verify `main()`'s new output was deleted before committing.

---

## FIX 1 -- `calibrate()` no longer fabricates a non-breach from missing data

**File:** `ru_calibration.py`

Renamed `mids` -> `path_asks` (it holds asks, not mids) and added a guard:
if every row in the held path is unquoted, `path_asks` is empty and the
ticker is now skipped (`continue`) instead of being scored with
`adverse_excursion(ask, [])` == `0.0`, a clean but fabricated non-breach.

```python
path_asks = [r["yes_ask_c"] for r in path
            if r.get("yes_ask_c") is not None]
if not path_asks:
    # Every row in the held path is unquoted: this is MISSING DATA,
    # not a measured non-breach. Scoring it as 0.0 excursion would
    # silently bias the breach rate downward, and books go unquoted
    # precisely when risk is real.
    continue
realised = adverse_excursion(ask, path_asks)
```

**Test added:** `tests/test_ru_calibration.py::test_a_path_that_loses_all_its_quotes_is_skipped_not_scored_as_zero`

**Mutation verification:** reverted the guard (restored the old
`mids`/no-skip behaviour) and reran just the new test.

```
$ python -m pytest tests/test_ru_calibration.py -q -k "loses_all_its_quotes"
FAILED tests/test_ru_calibration.py::test_a_path_that_loses_all_its_quotes_is_skipped_not_scored_as_zero
AssertionError: an unquoted path must not be scored as a non-breach
assert {'mlb_game': BreachStats(n=1, breaches=0, rate=0.0, nominal=0.05)} == {}
```

Confirmed the test fails under the old behaviour, then restored the fix.

---

## FIX 2 -- NO-side capital magnitude now has an exact pinned test

**File:** `tests/test_risk_unit.py`

Kept `test_the_no_side_uses_its_own_capital_at_risk` (the ordering test)
unchanged. Added a new test beside it,
`test_the_no_side_capital_at_risk_is_pinned_to_10c_not_90c`, that computes
`ru_per_contract(0.90, spread_cents=2, void_rate=0.005, side="no")` by hand
from the formula in `agent/risk_unit.py`:

```
capital   = 1 - 0.90                        = 0.10
sigma     = sqrt(0.90 * 0.10)                = 0.3
vol_term  = capital * SIGMA_MULTIPLE * sigma = 0.10 * 2.0 * 0.3 = 0.06
cost_term = 0.5 * 2 / 100 + FEE_PER_CONTRACT_USD (0.01)         = 0.02
void_term = capital * void_rate (0.005)                         = 0.0005
RU        = 0.06 + 0.02 + 0.0005                                 = 0.0805
```

**Expected value pinned: 0.0805** (`pytest.approx`), confirmed against a live
call to `ru_per_contract` before writing the assertion:

```
$ python -c "from agent.risk_unit import ru_per_contract; \
  print(ru_per_contract(0.90, spread_cents=2, void_rate=0.005, side='no'))"
0.08049999999999999
```

**Mutation verification:** changed `capital = price if side == "yes" else
(1.0 - price)` to `... * 0.5` and reran the whole file.

```
$ python -m pytest tests/test_risk_unit.py -q
FAILED tests/test_risk_unit.py::test_the_no_side_capital_at_risk_is_pinned_to_10c_not_90c
assert 0.05024999999999999 == 0.0805
1 failed, 21 passed
```

Exactly the new test failed; the other 21 (including the original ordering
test) still passed under the mutation, matching the review's description.
Mutation reverted afterward.

---

## FIX 3 -- `book_recorder.snapshot_from_market`'s docstring is now true

**Files:** `book_recorder.py`, `tests/test_book_recorder.py`

`snapshot_from_market` no longer delegates to `momentum_filter._ask_cents` /
`_bid_cents` (which check the plain `yes_bid`/`yes_ask` keys FIRST). It now
reads `yes_bid_dollars` / `yes_ask_dollars` directly via a small local
helper `_dollars_to_cents`, multiplying by 100.0 for cents, preserving the
existing `None`-when-unquoted behaviour and the existing `_fp` handling for
`oi`/`v24`. The `momentum_filter` import was removed (no longer used).

Strengthened `test_the_plain_field_names_are_ignored_even_if_present`: it
previously asserted only `snap["oi"]`. It now also passes disagreeing plain
`yes_bid`/`yes_ask` keys (90.0 / 10.0, which would go NEGATIVE if the plain
keys won) alongside the correct `_dollars` values (45c bid / 47c ask), and
asserts the `_dollars` values win and `spread_c` is non-negative:

```python
snap = snapshot_from_market(
    _market(open_interest=1.0, volume_24h=2.0,
           yes_bid=90.0, yes_ask=10.0),
    ts=1)
assert snap["oi"] == 6460.04
assert snap["yes_bid_c"] == 45.0
assert snap["yes_ask_c"] == 47.0
assert snap["spread_c"] == 2.0
assert snap["spread_c"] >= 0
```

**Mutation verification:** temporarily restored the old
delegate-to-momentum_filter implementation and reran the strengthened test.

```
$ python -m pytest tests/test_book_recorder.py -q -k plain_field_names
FAILED tests/test_book_recorder.py::test_the_plain_field_names_are_ignored_even_if_present
assert snap["yes_bid_c"] == 45.0
AssertionError: assert 90.0 == 45.0
```

Confirmed the plain keys win under the old code (and would have produced a
negative spread in an unlucky ordering), then restored the fix.

---

## FIX 4 -- `portfolio_ru` normalises event/source labels before unioning

**File:** `agent/risk_unit.py`

In the union-find loop, `event` and `source` are now normalised with
`.strip().upper()` before being used as union-find keys, with the
emptiness check running on the normalised value so the existing
blank-field behaviour (blank fields do not merge unrelated positions) is
unchanged:

```python
event_key = event.strip().upper() if event else event
source_key = source.strip().upper() if source else source
if event_key:
    union(node, f"event:{event_key}")
if source_key:
    union(node, f"source:{source_key}")
```

**Test added:** `tests/test_risk_unit.py::test_labels_that_differ_only_in_case_or_whitespace_still_cluster`

```python
assert portfolio_ru([("E1", "ATP", 3.0), ("E2", "atp", 4.0)]) == pytest.approx(7.0)
assert portfolio_ru([("E1", "ATP", 3.0), ("E2", "ATP ", 4.0)]) == pytest.approx(7.0)
```

**Mutation verification:** reverted the normalisation (raw-string union)
and reran the full file.

```
$ python -m pytest tests/test_risk_unit.py -q
FAILED tests/test_risk_unit.py::test_labels_that_differ_only_in_case_or_whitespace_still_cluster
assert 5.0 == 7.0
1 failed, 22 passed
```

Only the new test failed; `test_blank_fields_do_not_merge_unrelated_positions`
and all other clustering tests still passed. Mutation reverted afterward.

---

## FIX 5 -- replay-side skips are now counted and announced

**File:** `ru_calibration.py`

Added a `SkipCounts` dataclass (`too_few_rows`, `empty_path`,
`missing_quote`, `unquoted_path`, `sizing_error`, plus a `.total` property).
`calibrate()`'s return type is unchanged (`dict[str, BreachStats]`); a new
optional `skips: SkipCounts | None = None` keyword-only-in-practice
parameter is populated in place if the caller passes one, so existing
callers (including all pre-existing tests) are unaffected. Every existing
`continue` in the per-ticker loop now increments the matching counter.

`ru_per_contract` is now called inside a `try/except ValueError`: on
failure the ticker is announced (`skip {ticker}: {ExceptionType}: {msg}`)
and counted as `sizing_error`, so one malformed row (e.g. a negative spread
slipping through) cannot abort the whole replay.

`main()` now computes `measured = sum(s.n for s in stats.values())` and
prints the measured count and dropped count explicitly instead of the raw
ticker count:

```
RU calibration: {measured} tickers measured, {skips.total} dropped, out of
{len(by_ticker)} tickers loaded, horizon {N} snapshots
```

Manually verified against a small synthetic recording (1 healthy ticker + 1
too-short ticker):

```
RU calibration: 1 tickers measured, 1 dropped, out of 2 tickers loaded, horizon 3 snapshots
```

**Tests added:**
- `test_a_malformed_row_is_skipped_not_allowed_to_abort_the_replay` -- a
  ticker with a negative `spread_c` (bid > ask) raises inside
  `ru_per_contract`; asserts it is skipped, counted under
  `skips.sizing_error`, announced on stdout with the ticker name and
  `ValueError`, and that a healthy ticker in the same batch is still
  measured.
- `test_skip_counts_add_up_to_the_gap_between_loaded_and_measured` --
  asserts `measured + skips.total == len(by_ticker)` for a batch mixing a
  too-short ticker, a missing-quote ticker, and a healthy one.

No separate mutation test was requested for this fix (it is Minor); both
new tests pass against the implemented code.

---

## FIX 6 -- comment/docstring corrections, no behaviour change

**`agent/void_rates.py`** (~line 37): replaced the false "longer prefixes
first, because KXMLBHR must not match the KXMLB* game rule" comment (no
entry's prefix is a prefix of another's today, and the list isn't sorted
longest-first) with an accurate statement: the table is checked in order,
first match wins, and a FUTURE entry whose prefix is itself a prefix of an
earlier entry's prefix would need to be placed after it. Table order was
not changed.

**`tests/test_ru_calibration.py`** (`test_a_collapsing_favourite_breaches_its_RU`):
corrected the docstring's claim of being "the only test that proves
calibrate() compares realised against predicted in that order rather than
the reverse." Verified this is false by reversing the comparison in
`breach_stats` (`predicted > realised` instead of `realised > predicted`)
and rerunning the suite:

```
$ python -m pytest tests/test_ru_calibration.py -q
FAILED test_a_mid_priced_book_cannot_breach_its_own_RU
FAILED test_an_unmeasured_series_falls_back_to_the_worst_known_void_rate
2 failed, 13 passed
```

`test_a_collapsing_favourite_breaches_its_RU` passed under the reversal
(its fixture has exactly one clear breach and one clear non-breach either
way: n=2, breaches=1 regardless of direction), while the two tests above
caught it. The docstring now names those two tests and describes what this
test actually demonstrates (a genuine collapse breaches while a flat book
in the same batch does not).

**`ru_calibration.py`** module docstring: replaced the falsifiable-but-false
claim ("esports positions should breach their RU far more often than MLB
games") with the measured result: as the RU formula stands, a breach is
impossible across a band of mid prices for both verticals, and that
no-breach band is WIDER for esports (~3c-77c) than for mlb_game (~3c-63c) --
confirmed directionally by a standalone scan of `ru_per_contract` against
the maximum-possible-drawdown bound across 3c-97c for both verticals'
measured void rates (esports_series=0.099, mlb_game=0.005) at a 2c spread,
which reproduced the mlb_game bound exactly (3-63) and the esports bound
closely (3-74 vs the reported 3-77, difference attributable to
spread/rounding assumptions -- the qualitative finding, esports's no-breach
band is wider than mlb's, held at every spread tested). So esports breaches
LESS often than MLB at mid prices under the current formula, the opposite
of what the harness was built to show. No code was changed to address this;
per the task, that decision belongs to the operator.

---

## Final verification

```
$ python -m pytest tests/ -q
609 passed in 0.9s
```

Files changed (all in scope, none outside the six fixes):

- `agent/risk_unit.py` (Fix 4)
- `agent/void_rates.py` (Fix 6)
- `book_recorder.py` (Fix 3)
- `ru_calibration.py` (Fixes 1, 5, 6)
- `tests/test_book_recorder.py` (Fix 3)
- `tests/test_risk_unit.py` (Fixes 2, 4)
- `tests/test_ru_calibration.py` (Fixes 1, 5, 6)

`agent/config.py`, `agent/risk.py`, `SIGMA_MULTIPLE`, and every other RU
formula constant were left untouched. No files under `state/`, no `.env`,
no `*.pem` were created or committed.
