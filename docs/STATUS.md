# STATUS — politics forecasting system

Branch: `forecast/politics-calibration` (cut from `fund/plan-1-foundation` @ 6e9e208).
Started 2026-10-09. Kalshi API is used **read-only**; no order is placed anywhere in this work.

## What "the old plan" is

No file is literally named old-plan.md. Two documents together are the plan this work picks up:

- `docs/superpowers/specs/2026-08-19-prediction-market-fund-design.md` (the fund design). Its Stage A
  strategy is the one backtested here: an archetype base rate `p0`, a context-adjusted estimate `p1`,
  and a trade only when `p1` beats the market by `min_edge` net of fee and spread.
- `research/2026-10-06/NOVEMBER_PLAYBOOK.md` (dry-run trade list for Nov 3, 2026). Its section C bet
  ("2026 polls overstate Democrats here") is a knowledge-driven tilt that the backtests test as a variation.

## What's built (before this branch)

- `kalshi_client.py`: signed client for Trade API v2. Works unauthenticated for market data. No key in `.env`.
- `agent/`: headline → vault retrieval → LLM judgment → risk gate pipeline. LLM tiers never run (no
  `ANTHROPIC_API_KEY`). Retrieval is headline-keyed (entity index), not market-keyed.
- Obsidian vault (`Desktop/obsidian-personal-space/vault`, 279 notes): 50 state notes, 15 polling-accuracy
  notes, 35 county notes, patterns, 114 market notes for other verticals. Timeline entries are dated and
  sourced; most body prose is **not** per-claim sourced or dated, so it cannot be used in a leakage-free
  backtest as-is.
- `backtest.py`, `ladder_backtest.py`, `ru_calibration.py`, `eqr/`: momentum and intraday backtests on
  recorded books. The finding of record is that momentum loses and fees (0.07·P·(1−P)) dominate.
- `research/2026-10-06/`: November playbook, structural scans, a tail-spike base rate.

## What's stale

- AGENT.md: limitation 4 is out of date (`/events?with_nested_markets=true` now enumerates fine);
  `kalshi_client.get_trades` hits `/trades` (404), the working path is `/markets/trades`.
- Fee model assumes taker-only. Kalshi began charging makers after April 2025 (Bürgi et al., p.6).
- Markets settled before 2026-08-09 moved to `/historical/*` endpoints; existing scripts only read the
  live endpoints, so they never saw most resolved political markets.
- The vault's politics notes were last refreshed 2026-10-06 (timelines only).

## Plan (next)

1. Knowledge: `knowledge/politics/` in the repo, same frontmatter + wikilink + `## Timeline` format as the
   vault, plus a per-claim `(as_of: YYYY-MM-DD; source: URL)` tag so the retriever can drop anything written
   after a market's decision time. Priority: topics behind open Kalshi political markets, then base rates.
2. Retrieval: market (title, rules, close date) → top-k chunks, with an `as_of < T` filter. Eval set of
   ≥50 market→file pairs, recall@5 logged per change in `docs/retrieval.md`.
3. Backtests: resolved Kalshi political markets from both live and `/historical` endpoints, decision
   snapshot taken from candles before close. Most recent 30% by close time is a locked test set. Brier vs
   market, calibration by bucket, P&L net of fee and spread. Each variation logged in `docs/backtests.md`.
4. Market mechanics note + participant-sophistication submodels; test whether edge concentrates in
   low-sophistication markets.

## Workstream 1 notes (2026-10-09)

- 71 notes: 15 Senate races, 15 governor races + LA mayor, 6 chamber/seat-count, 4 nomination (2028), 7 policy,
  7 international, 8 base-rate (151 machine-readable `base_rate:` lines), 3 mechanics, 4 past-cycle results.
- Written by 9 parallel research subagents; every claim bullet carries `(as_of; source)`. The session's web
  search budget ran out partway, so later facts came from direct page fetches (mostly Wikipedia + primary
  sources). Several agents flagged facts they could only see in search snippets; those are marked in-file.
- Where a source had no exact date, agents used a later conservative as_of (never earlier), so a backtest
  can under-use but not leak.
- Known data issues flagged by agents: SENATELA-26-R rules say "Senator of Kentucky" (Kalshi template typo);
  NE Senate D contract still names a withdrawn candidate; GOVPARTYMI-26 still lists Duggan.

## Race-analog engine (operator request, 2026-10-09)

`forecast/analogs.py` + `knowledge/politics/data/races_*.csv` (218 races, 2016–2026); results in
`docs/analogs.md`. In walk-forward tests, literal analogs beat no adjustment by a small margin (MAE 3.05 vs 3.26,
CI clears 0); the mirrored version does not. The dominant pattern is cycle-level: polls overstated
Democrats in all three Trump-on-ballot years but not in the 2018/2022 midterms. The most robust race-level
pattern, that polls understate a state's partisan lean, is already priced by Kalshi.

## Next (not done)

- Knowledge coverage extended 2026-10-09: 90 notes (+19: remaining Senate/governor seats, PA-07/PA-08/WA-03, Trump-admin
  actions/tenure/travel/personnel, McConnell/Walz, Nobel, Abraham Accords, Taiwan advisory, CA Prop 40, Citrini).
- Re-test V18 — BLOCKED until post-2026-10-09 settlements accumulate (bulk after Nov 3).

- Re-test V18 (tight books only) on data that did not exist when it was chosen (post-2026-10-09 settlements).
- ~~Fresh retrieval eval set~~ done 2026-10-09: v2 recall@5 1.000 (0.933 on existing topics before new notes); see docs/retrieval.md.
- ~~Finish the remaining candle fetches~~ done: 19,488/19,488; suite re-scored on full data.
- LLM judgment step over retrieved chunks: untested (no ANTHROPIC_API_KEY), and the only path by which the
  knowledge layer could still beat plain recalibration.

## Workstream status

| # | Workstream | Status |
|---|---|---|
| 0 | Paper reviews (5 PDFs → `docs/papers/`) | done |
| 1 | Knowledge files | done — 71 notes in `knowledge/politics/` (≈1,500 dated+sourced claims), `knowledge/markets/how-prediction-markets-work.md` |
| 2 | Retrieval + eval | done — BM25 + as-of filter; 74 markets / 78 pairs; recall@5 0.953 (R0) → 0.993 (R5, eval-tuned). `docs/retrieval.md` |
| 3 | Backtests | done — 26 logged runs (B0 + 25 one-change variations) on a locked 30% test set; B0 beats market Brier (+1.0% skill, CI excludes 0); no P&L CI above 0. `docs/backtests.md` |
| 4 | Market mechanics + participant models | done — `knowledge/markets/how-prediction-markets-work.md`; liquidity/efficiency/activity submodels; edge does NOT concentrate in low-sophistication markets; trade size uncorrelated with sophistication. `docs/participants.md` |
