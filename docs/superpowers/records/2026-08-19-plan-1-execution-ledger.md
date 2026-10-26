# SDD ledger — plan: docs/superpowers/plans/2026-08-19-fund-plan-1-foundation.md

Spec: docs/superpowers/specs/2026-08-19-prediction-market-fund-design.md (read)
Branch: fund/plan-1-foundation
Baseline commit: c688143 (557 tests passing, is_live=False)

## Setup rulings

Ruling: branched to `fund/plan-1-foundation` and committed the session's work
as baseline c688143 instead of creating a git worktree — `momentum_filter.py`,
`agent/history.py` and the entire `tests/` tree were UNTRACKED, so a worktree
from HEAD would have contained neither the modules the plan imports nor the
557-test baseline it measures against. `main` is untouched at 8fe8384.
Cost if wrong: the operator wanted the session work left out of git or wanted
a separate worktree; both are undone with `git branch -D` / `git reset`, and
`main` never moved.

## Pre-flight conflict scan

### Cross-task rows (pairs sharing a file or an interface)

| pair | produces → consumes | finding |
|---|---|---|
| T1 → T2 | `void_rate_for_series`, `DEFAULT_VOID_RATE` → T2 "Consumes" block | **CONFLICT**: T2's Interfaces block claims it consumes `agent.void_rates`, but T2's implementation code imports nothing from it. T2 takes `void_rate` as a caller-supplied float. |
| T1 → T8 | `vertical_for_series`, `void_rate_for_series`, `DEFAULT_VOID_RATE` → `calibrate()` | clean — all three are in T1's Produces and all three are imported in T8 |
| T2 → T3 | `ru_per_contract` → `size_position` | clean — same file, same signature and arg names |
| T3 → T4 | `Sizing` → aggregation helpers | clean — T4 adds functions only, does not alter `Sizing` |
| T2 → T8 | `ru_per_contract(price, spread_cents, void_rate)` → `calibrate()` | clean — identical keyword names at the call site |
| T5 → T6 | `snapshot_from_market`, `SNAPSHOT_FIELDS` → `record_once` | clean — T6 appends to the same module; T6's test monkeypatches `book_recorder._all_open_markets`, which T6 itself imports |
| T5 → T8 | snapshot keys `ts/ticker/series/yes_ask_c/spread_c` → `load_recording`/`calibrate` | clean — every key T8 reads is in `SNAPSHOT_FIELDS` |
| T7 → T8 | `adverse_excursion`, `breach_stats`, `BreachStats` → `calibrate`, `main` | clean — same file; `BreachStats.rate` is `float \| None` in T7 and handled as `None` in T8's `main()` |

### Per-task self-consistency rows

| task | tests vs code | files created vs later touched | finding |
|---|---|---|---|
| T1 | 4 tests match 4 exported names | creates `agent/void_rates.py`, never modified later | clean |
| T2 | 7 tests, all against `ru_per_contract` | creates `agent/risk_unit.py`, modified by T3 and T4 as declared | clean |
| T3 | 7 tests; imports `Sizing` and uses it only as a type reference | modifies `agent/risk_unit.py` | minor: unused-ish import, harmless |
| T4 | 5 tests; block re-imports `math as _math` without using it | modifies `agent/risk_unit.py` | minor: dead import in test block |
| T5 | 6 tests match the snapshot contract | creates `book_recorder.py`, modified by T6 | clean |
| T6 | 4 tests incl. a resilience test | modifies `book_recorder.py` | clean |
| T7 | 6 tests match 3 exported names | creates `ru_calibration.py`, modified by T8 | clean |
| T8 | 4 tests incl. the `is_live()` guard | modifies `ru_calibration.py` | **CONFLICT**: Step 5 expects "594 passed"; the arithmetic gives 600 |

### Rulings on the scan

Ruling: T2's "Consumes: agent.void_rates" line is documentation drift, not a
requirement — `ru_per_contract` correctly takes `void_rate` as a plain float
parameter, which keeps the math module pure and testable without the data
table. Implementers follow the CODE in the task body, not the Interfaces
header. No change to T2's implementation.
Cost if wrong: none functionally; at worst the Interfaces header stays
slightly misleading for a future reader.

Ruling: T8 Step 5's expected total of "594 passed" is arithmetically wrong.
New tests are T1=4, T2=7, T3=7, T4=5, T5=6, T6=4, T7=6, T8=4 → 43 new against
a 557 baseline → **600**. Implementers are told to expect 600 and to report
the actual number rather than force a match.
Cost if wrong: if the real total differs, it signals a test that did not run
or an accidental collection change — which is exactly what we want surfaced
rather than papered over.

Ruling: the two dead imports in T3/T4 test blocks are Minor and deferred to
the final review rather than fixed pre-emptively.
Cost if wrong: trivial lint noise.

## Task progress

Ruling: dispatching by MODULE rather than one subagent per plan task —
T1 solo, then T2-T4 (agent/risk_unit.py), T5-T6 (book_recorder.py),
T7-T8 (ru_calibration.py). Each batch is one coherent module with its full
test suite, which is a meaningful review surface; splitting them would have a
reviewer judging half a module. Implementers are instructed to make the
per-task commits the plan specifies, so commit granularity is preserved.
Cost if wrong: a reviewer wanting to reject one task while approving its
neighbour must reject the module; rework is one module, not one function.

Task 1: complete (commits c688143..2243acf, review clean) — 4 new tests, 561 total.
  Reviewer independently traced all 9 rates to LOOP_LOG.md and scripted the
  prefix-ordering check.
Task 1: minor (deferred): agent/void_rates.py:98-99 — the ordering-rationale
  comment cites a "KXMLB game rule" conflict that does not exist in the
  current 19-entry table (no prefix is genuinely a prefix of another). Reads
  as documenting a live conflict when it is future-proofing. Copied verbatim
  from the brief, not introduced by the implementer.
Ruling: task-2-brief's `test_a_wide_book_is_dominated_by_the_exit_cost` was a
  PLAN DEFECT — it asserted `wide > tight * 1.5` where the formula yields
  1.365x (verified: tight=0.5200, wide=0.7100). The implementer correctly
  diagnosed it but fixed it by weakening the threshold to 1.35x, which leaves
  a test whose NAME claims domination while asserting a ratio that is not
  domination. Cause: the volatility term does not move with spread, so at
  p=0.50 the ratio is capped regardless of how wide the book is.
  Decided: replace the test with one that demonstrates the real danger — on a
  CHEAP contract with a wide book the cost term exceeds the volatility term
  outright (verified p=0.10, spread=60c -> cost 0.3100 vs vol 0.0600). That is
  the actual condition under which a book is untradeable, and it is the thing
  the spec's 23-79c observed spreads warn about.
  Cost if wrong: a slightly different test of the same property; the shipped
  formula is unchanged either way.
Ruling: the fix-round amend left misleading history — 0f4b0ea and 6f36090
  carried IDENTICAL messages and Task 4's commit (2b757fe) was orphaned, so
  the head commit claimed "per-contract Risk Unit" while containing portfolio
  aggregation. Squashed to ONE commit with an accurate message covering tasks
  2-4. Rationale: these three were deliberately batched into a single review
  surface, so one honest commit matches that decision better than three where
  two share a message and one is lost. Content is byte-identical (verified by
  diff --stat and 580 passing before and after); only the commit graph moved.
  Cost if wrong: per-task commit granularity is lost for this module; the
  plan's task boundaries remain visible in the briefs and this ledger.
Task 2-4: fix round 1/5 (1 addressed, 0 open — brief's wide-book test asserted
  a ratio the formula cannot produce; replaced with a cheap-contract test that
  proves cost > volatility; commits 0f4b0ea..2116224)
Ruling: PLAN DEFECT, load-bearing — `cluster_key` implements AND
  (`f"{event}|{source}"`) so two positions cluster only if BOTH match. Spec §5
  says positions sharing an event OR a settlement source are not independent.
  Under AND, two different matches both settled by "ATP" get different keys
  and are credited as diversified via root-sum-square — systematically
  UNDERSTATING correlated risk, which is the single thing this aggregation
  exists to prevent. The brief's own test asserted the opposite of its name.
  Spec is the binding authority, so the code changes, not the spec.
  Decided: replace key-based clustering with CONNECTED COMPONENTS (union-find)
  over positions, linked by shared event or shared source, and change
  `portfolio_ru` to take (event, source, ru) triples. `cluster_key` is removed
  rather than kept, because a helper whose semantics are wrong is a trap for
  the next caller. Transitive grouping is deliberate and conservative: it
  groups more and credits less diversification; under-grouping is the
  dangerous direction.
  Cost if wrong: the aggregation is more conservative than strictly necessary,
  so positions are sized slightly smaller than optimal. That is the safe
  direction to be wrong in, and Plan 2 can revisit it with live fills.
Task 2-4: fix round 2/5 (3 addressed, 0 open — AND->OR clustering via
  union-find, duplicate math import, NO-side refusal test; commit 56c057a)
Task 2-4: minor (deferred): my fix instruction told the implementer to delete
  five Task-4 tests and supplied six replacements, but omitted a replacement
  for `test_aggregation_never_exceeds_the_linear_sum` (RSS <= linear sum).
  Minor coverage regression, my omission not the implementer's. Flag to the
  final review.
Task 2-4: complete (commits 2243acf..56c057a, review clean) — 21 tests in
  test_risk_unit.py, 582 total.
Ruling: PLAN DEFECT — task-6-brief's `test_a_dead_series_does_not_abort_the_sweep`
  documents "Invariant J: announce, do not crash" but asserts only `n == 1`.
  Deleting the `print` in record_once's except branch would leave the test
  green while silently reverting the announce half of the invariant — the
  third test-name/body mismatch this plan has produced. Decided: add a capsys
  assertion that the skipped ticker is named on stdout.
  Cost if wrong: none; the assertion only pins behaviour that already exists.
Ruling: bundling the Minor .gitignore gap into the same fix dispatch rather
  than deferring it. `main()`'s default output is `state/book_recording.jsonl`,
  which matches none of the existing state/ ignore patterns, so a real
  multi-day recording sits one `git add -A` away from the repo. The fix loop
  was already running for the Important, so this does not extend it.
  Cost if wrong: one extra ignore line.
Ruling: verified fix round 1 INLINE instead of dispatching a scoped re-review.
  The diff is 11 lines across .gitignore and one test docstring/assert block,
  it is my own fix instruction applied verbatim, and the only question worth
  answering was whether the new assertion actually bites. Answered by
  MUTATION rather than by reading: deleted the `print` in record_once's
  except branch and re-ran the test — it FAILED with "the skipped series must
  be named on stdout", then restored and confirmed 592 passing with a clean
  tree. A reviewer seat would have re-read 11 lines I can see in full.
  Cost if wrong: an 11-line test-only diff goes to the final whole-branch
  review without an intermediate second opinion.
Task 5-6: fix round 1/5 (1 Important + 1 Minor addressed, 0 open — capsys
  assertion on the announce invariant, mutation-verified; state/book_recording*
  .jsonl ignored; commit bab0930)
Task 5-6: complete (commits 56c057a..bab0930, review clean) — 10 tests in
  test_book_recorder.py, 592 total.
Ruling: PLAN DEFECT confirmed, implementer was RIGHT — task-8-brief's
  `test_calibration_reports_breaches_per_vertical` asserted `breaches == 1`
  on a book entered at ask 51c. Independently verified against the shipped
  formula: predicted RU at 51c is 0.5324 while the MAXIMUM POSSIBLE loss on a
  51c yes contract is 0.5100. A breach there is not unlikely, it is
  ARITHMETICALLY IMPOSSIBLE. The implementer's correction to `breaches == 0`
  stands.
  The finding generalises and is worth keeping: with SIGMA_MULTIPLE=2.0 the
  RU EXCEEDS the maximum possible loss for mid-priced contracts, so breaches
  can only occur at the extremes (verified: impossible at 51c, possible at
  70c/91c/96c). Mid-priced positions are structurally over-margined.
Ruling: LOAD-BEARING GAP the review must not inherit — with that assertion at
  0, no test anywhere drives `calibrate()` down a path where realised exceeds
  predicted. `breach_stats` is unit-tested at 2 breaches, but the INTEGRATION
  is not: inverting the tuple to (predicted, realised) at
  ru_calibration.py:130 would leave every test green while the harness
  reported perfect calibration forever — silently defeating the module's only
  purpose. Decided: keep the corrected 0-breach case, rename it to state what
  it proves, and ADD a 91c favourite collapsing to 2c (realised 0.89 vs
  predicted 0.5454) that genuinely breaches.
  Cost if wrong: one extra test on a path that already works.
Task 7-8: fix round 1/5 (1 Important + 1 Minor addressed, 0 open — added a
  92c->2c favourite that genuinely breaches (realised 0.89 vs predicted
  0.5238), renamed the 51c case to state the property it actually proves,
  hoisted six mid-file imports to the top; commit 3b21539)
Ruling: mutation-verified the new breach test rather than taking it on
  report. Inverted the tuple at ru_calibration.py:129 to
  (predicted, realised) and re-ran: FAILED, 2 breaches where 0 expected.
  Restored, 603 passing, clean tree. The argument-order inversion the test
  was added for is now genuinely caught.
Ruling: T7-8 review returned Spec OK / Approved-with-findings, no Critical.
  The single Important is an arithmetic slip in the implementer's REPORT
  (realised stated as 0.46, actually 0.45 — the +1 ask offset applied to the
  entry but not to the path low), not in shipped code; the conclusion it
  supports is unaffected. Ordinarily a report-only defect in a scratch file
  that gets deleted at plan end would be deferred, but a wrong number in the
  record is exactly what a later reader would cite, so it is corrected in the
  same round as the two Minors rather than left standing.
Ruling: taking one more fix round for the UNMEASURED-SERIES FALLBACK, which
  the review found ships untested. When void_rate_for_series returns None,
  calibrate substitutes DEFAULT_VOID_RATE = 0.099 — the MAXIMUM measured rate,
  not a mean — and buckets the position under "unmeasured". That is a
  deliberate safety choice: an unknown vertical is priced as the worst one
  observed. It is worth a test precisely because a future refactor that made
  the fallback a mean, or let None through to ru_per_contract, would be
  invisible today. Verified the inputs myself: vertical_for_series and
  void_rate_for_series both return None for KXZZUNKNOWN, and predicted RU at
  ask 51c on the default rate is 0.5804 against 0.5324 on the mlb_game rate.
  Cost if wrong: one test on a path that already behaves correctly.
Ruling: also tightening the brief-inherited `assert stats == {} or
  stats["mlb_game"].n == 0` in the short-path test. The review showed the
  right-hand branch is UNREACHABLE — a ticker either contributes n>=1 or is
  absent entirely — so the or-assertion can only ever be satisfied by its
  left half while reading as though it tolerates two outcomes. A disjunction
  where one side cannot occur is a weaker assertion than it appears.
Ruling: MY OWN DEFECT, caught by mutation — the unmeasured-fallback test I
  specified in fix round 2 asserted
  `ru_per_contract(..., DEFAULT_VOID_RATE) > ru_per_contract(..., 0.005)`,
  which is a property of ru_per_contract's monotonicity and says NOTHING
  about which rate calibrate() actually used. Verified by setting the
  fallback to 0.0: all 12 tests stayed green. This is the same
  name-promises-more-than-body defect I have now flagged four times in other
  people's work, written by me.
  Fixed IN PLACE rather than by a round-3 dispatch: the defect is mine, the
  correction is one test body, and I had already computed the discriminating
  prices. Entry 92c collapsing to 35c puts realised (0.5700) BETWEEN the RU
  on a near-zero rate (0.5192) and on DEFAULT_VOID_RATE (0.6103), so the
  breach count flips with the rate. Mutation-verified against both 0.0 and a
  mean-like 0.03 — each now FAILS. Commit is test-only; ru_calibration.py
  restored byte-identical.
  Cost if wrong: a controller-authored commit sits in a branch otherwise
  written by implementers; the final whole-branch review still sees it.
Task 7-8: fix round 2/5 (1 Important + 2 Minor addressed, 0 open — report
  arithmetic corrected to 0.45, unmeasured-fallback test added, unreachable
  disjunction tightened; commit d6da439) plus controller fix 35b778d.
Task 7-8: complete (commits bab0930..35b778d, review clean) — 13 tests in
  test_ru_calibration.py, 604 total.
ALL TASKS COMPLETE. Branch fund/plan-1-foundation, baseline c688143 (557) ->
  35b778d (604). Modules: agent/void_rates.py, agent/risk_unit.py,
  book_recorder.py, ru_calibration.py. is_live=False throughout.
Carry into the final whole-branch review:
  - deferred minor (T1): agent/void_rates.py:98-99 comment cites a prefix
    conflict that does not exist in the current table.
  - deferred minor (T2-4): no replacement was supplied for
    test_aggregation_never_exceeds_the_linear_sum (RSS <= linear sum);
    coverage regression from my own fix instruction.
  - controller-authored commit 35b778d (test-only) needs the same scrutiny
    as implementer work, not less.
  - finding worth carrying to Plan 2: with SIGMA_MULTIPLE=2.0 the RU EXCEEDS
    the maximum possible loss for mid-priced contracts (impossible to breach
    at 51c; possible at 70c+), so mid-priced positions are structurally
    over-margined.

## Final whole-branch review — Approved-with-findings

Ruling: NOT changing SIGMA_MULTIPLE, and escalating finding 1 to the operator
  instead. Independently reproduced the reviewer's table: a YES breach is
  arithmetically impossible from 3c-63c (mlb_game), 3c-71c (atp_match) and
  3c-77c (esports_series). The band is WIDEST for esports, which inverts
  ru_calibration.py's own stated falsifiable claim that esports should breach
  more often than MLB — the higher void rate and wider spread RAISE predicted
  RU and push breaches further out of reach.
  I checked whether a cap fixes it. It does not: at p=0.50 the volatility
  term ALONE (capital * 2 * sqrt(p(1-p))) equals capital exactly, so no
  ceiling at max-loss can bring RU below the realised excursion. The cause is
  that for a BOUNDED binary a two-sigma move is definitionally the entire
  distance to settlement; SIGMA_MULTIPLE=2.0 is a normal-distribution
  intuition applied to a support of [0,1].
  The only real fix is a smaller multiple (~1.0), which HALVES predicted RU
  and therefore DOUBLES every position size. That is a change to the fund's
  core risk parameter, it moves sizing in the DANGEROUS direction, and spec
  §7.4 assigns parameter revision to the monthly human-approved offline
  re-fit, not to an agent mid-plan. Escalating rather than ruling.
  Cost of not fixing now: the calibration harness cannot discriminate
  verticals in the price band where the volume is, so Plan 2 must not treat a
  clean calibration run as evidence the RU is trustworthy. Recorded as the
  Plan 2 entry gate. No capital is at risk in Plan 1.
Ruling: fixing everything else in ONE dispatch per the skill's final-review
  step — findings 2, 4, 5, 6, 9 and minors 7, 8, 11, 12, 13. Finding 2
  (calibrate manufacturing a measured non-breach out of a fully unquoted
  path) and finding 6 (portfolio_ru under-grouping on unnormalised source
  labels) are both real and both bias toward "the model is fine", which is
  the direction my earlier union-find ruling called dangerous.
Final fixes: commit b3b17d1, 604 -> 609 tests. Mutation-verified by me, not
  taken on report: halving NO-side capital fails exactly 1 test; removing the
  .strip().upper() normalisation fails exactly 1; neutralising the
  unquoted-path guard fails exactly 1. All three bite.
Note (pre-existing, NOT this branch): state/audit.jsonl and
  state/open_election_events.json are tracked, added by the original import
  commit 8fe8384 which predates this plan's baseline. Verified this branch
  added nothing under state/ and that neither file contains secret-shaped
  content. Untracking them is out of scope here and destructive; flagged to
  the operator instead.
Ruling: re-review returned all six findings CLOSED with one Important
  residual — and it was MY error. The correction text I dictated said the
  breach-impossible region was "roughly 3c-63c" / "roughly 3c-77c", implying
  one contiguous band. I had produced those numbers by printing band[0] and
  band[-1] of a FILTERED LIST, which reports the endpoints of a possibly
  non-contiguous set. That is precisely the defect the text existed to fix,
  reintroduced by my own verification method.
  Measured properly by contiguous runs: the region depends on the spread and
  is not contiguous at tight ones — mlb_game at 2c is breachable from ~3.1c
  to 32c, so a cheap longshot on a tight book CAN breach while the same
  contract on a wide book cannot. Full 2c/6c/8c table now in the module
  docstring. Fixed in place (documentation only, commit c2234fa).
  The load-bearing conclusion survives at every spread: esports has the
  WIDER no-breach zone, so it breaches LESS than MLB at mid prices.
  Method note for the record: "compute the endpoints of the set" is not the
  same as "compute the set". Two reviewers and I all reported endpoints; only
  the third pass checked continuity.
FINAL REVIEW CLEAN. Branch fund/plan-1-foundation: c688143 (557 tests) ->
  c2234fa (609 tests), 14 commits. All 8 plan tasks complete, all findings
  closed or ruled. is_live=False. Nothing new under state/.
ESCALATED TO OPERATOR, not ruled: SIGMA_MULTIPLE=2.0 makes mid-price breaches
  arithmetically impossible and inverts the harness's vertical
  discrimination. Fixing it doubles position size, which spec 7.4 assigns to
  the human-approved monthly re-fit. This is the Plan 2 entry gate.
