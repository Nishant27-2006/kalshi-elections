# The 24/7 agent

News scraper → knowledge graph → LLM judgment → risk gate → Kalshi.

## Architecture (funnel, not pipeline)

The whole design goal is that the *expensive* step runs almost never:

```
T0  RSS poll (every 5 min)         FREE     ~100 headlines/pull, deduped by hash
T1  Vault entity match             FREE     IDF-weighted; kills ~95%
T2  Cheap LLM triage (Haiku)       ~$0.001  "concrete, market-moving?"
T3  Knowledge-graph retrieval      FREE     wikilink BFS over 130 vault notes
T4  Kalshi market lookup           FREE     cached open-events + orderbook
T5  Claude judgment (Sonnet)       ~$0.02   direction + fair value + confidence
T6  Risk gate                      FREE     DETERMINISTIC PYTHON — not the LLM
T7  Execute
```

Implemented as a LangGraph `StateGraph` (`agent/graph.py`) with conditional
edges that short-circuit to `END` at every tier. `run_sequential()` runs the
identical node functions without LangGraph — used by tests and the backtest.

## The safety model

**The LLM never sizes a position and cannot override a limit.** It returns
only `{should_trade, side, fair_value_cents, confidence, reasoning}`.
Everything else is deterministic code in `agent/risk.py`:

- per-trade cap, daily-loss cap (halts for the day), max open positions
- total-capital ceiling, duplicate-position guard
- min confidence, min edge vs fair value
- max spread, min book depth, min/max entry price (no dust, no near-resolved)
- kill switch: `touch KILL` and the loop stops
- every decision *including rejections* appended to `state/audit.jsonl`

`risk.py` is pure and I/O-free, so the backtest exercises the exact code path
live trading would.

Fail-closed by design: an LLM error, a missing API key, or a parse failure
produces **no trade**, never a default trade.

## Current posture (deliberately locked down)

| Setting | Value | Meaning |
|---|---|---|
| `EXECUTION_ENABLED` | `false` | dry-run only; logs what it *would* do |
| `KALSHI_ENV` | `demo` | paper sandbox |
| `TOTAL_CAPITAL_USD` | `100` | placeholder — set your real ceiling |
| `MAX_POSITION_USD` | `10` | per-trade cap |
| `MAX_DAILY_LOSS_USD` | `25` | daily halt |

It also cannot trade today regardless: no Kalshi API key and no
`ANTHROPIC_API_KEY` are loaded.

## Run it

```bash
python -m agent.runner --once --refresh-markets   # one cycle
python -m agent.runner                            # continuous
python backtest.py --days 7 --move 5              # backtest
touch KILL                                        # emergency stop
```

## Verified working

- Knowledge graph: 130 notes, 254 aliases, 1,069 links parsed. Retrieval
  scored **9/9** on a match/skip test set (matches Miller/El-Sayed/Maricopa/
  Georgia/Bucks; correctly skips Fauci/Taylor Swift/Fed/Lakers).
- Risk gate: all 11 rejection paths verified; sizing scales monotonically
  with confidence and caps at `MAX_POSITION_USD`.
- Full graph: compiles, runs end-to-end, terminates at the right tier.
- Live cycle: fetched real news, cached ~900KB of open Kalshi election
  events, wrote 35 audit records.

## Known limitations (read before trusting it)

1. **T4 market matching is the weak link.** Keyword overlap between a
   headline and event titles produces loose matches (a Boebert story matched
   a DC-statehood market). The curated `watchlist.py` tickers are reliable;
   the fuzzy fallback is not. This needs an explicit entity→ticker mapping
   before live trading.
2. **The LLM tiers have never actually run** — no `ANTHROPIC_API_KEY`. T2/T5
   are written and wired but unexercised against the real API.
3. **The backtest does not validate LLM judgment** — see below.
4. Kalshi's `?series_ticker=` filter silently returns empty for several real
   election series; `?event_ticker=` works. Hence the local event cache.

## Backtest result — read this before enabling execution

`backtest.py` replays **real** Kalshi hourly candles (12 markets, 7 days) with
a mechanical momentum rule through the production risk gate.

**Momentum chasing lost money at short horizons in every configuration:**

| Trigger | n | 1h win | 4h win | 4h P&L |
|---|---|---|---|---|
| ≥3¢ | 54 | 31.5% | 40.4% | +$4.30 |
| ≥5¢ | 45 | 28.9% | 34.9% | +$1.08 |
| ≥8¢ | 25 | 28.0% | 26.1% | **−$14.61** |
| ≥10¢ | 24 | 33.3% | 31.8% | **−$13.50** |

Median P&L was negative at 1h and 4h in *every* config, and **raising the
trigger made results worse** — the signature of mean reversion, not momentum.

The headline case: `KXDROPOUTPRIMARY-26-MMIL2` (Max Miller dropout) ran
**25¢ → 52¢ → 47¢ → 1¢ (resolved NO)**. Momentum entries on it returned
**−$48.51 at a 17% win rate**, the worst in the universe.

A long-horizon "+$217 / 75.6% win rate" figure also appears — **it is an
artifact.** The winners had resolved to 1¢/99¢; that measures holding to
expiry, not edge. Any backtest reporting long-horizon win rates on resolved
contracts is measuring survivorship.

Written up in the vault as
`Pattern: Momentum Chasing Fails on Scandal Deadline Contracts`.
