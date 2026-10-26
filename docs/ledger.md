# Forward paper-forecast ledger

`forecast/ledger/ledger.jsonl` is append-only, timestamped forecasts made **before** markets resolve, so it is the
only test here that cannot leak. Git history proves when each row was written. No orders exist; this is paper only.

```
python -m forecast.ledger snapshot     # add B0 + analog forecasts for every covered open market
python -m forecast.ledger add F.jsonl  # add externally made (LLM) forecasts
python -m forecast.ledger score        # grade rows whose markets have settled -> forecast/ledger/scores.json
```

## First entries (2026-10-09 ~23:40 UTC)

| forecaster | rows | what it is |
|---|---|---|
| B0 | 1,056 | old-plan estimator (archetype intercept + market slope), refit on all 19,488 resolved markets; every open market listed in a note's `markets:` with a two-sided quote |
| analog_lean | 27 | polls + state-lean model from docs/analogs.md, D legs of 2026 Senate/governor markets |
| llm:batch1–4 | 64 | **the first run of the LLM judgment step.** Four subagents, 16 markets each, one leg per event (closest to 50c within 8–92c). Each saw ONLY the market rules, bid/ask and the top-8 knowledge chunks dated before now (packets in `forecast/ledger/packets/`). No web, no API. Reasoning and the notes used are logged per row. |

**What the LLM forecasters did:**
- **Direction:** mean deviation from the market mid is −2.4c. 40 markets went down, 6 up and 18 stayed within 1c. Mean
  |deviation| is 2.8c.
- **Pattern:** almost every move shades a YES price down. The rule text is stricter than the headline (Alito must
  actually *retire* before the date; a Greenland *purchase* needs a sale, not a basing deal; an "election emergency"
  needs a signed declaration), or district ratings (TX-15, FL-25, VA-2 as Toss-ups) look cheaper than the price.
- **Knowledge use:** all 64 rows cite at least one knowledge note.
- **Agreement with B0:** on the same 64 markets B0 moves the price by only −0.55c on average, and the two disagree on
  direction (correlation of deviations −0.16). The ledger therefore tests two genuinely different forecasters against
  the market.

**Rows are unscored until markets settle.** Most of these settle in November 2026–January 2027.

## Caveats

- The subagents' training data runs to mid-2026, so they bring background knowledge beyond the packets. They were told
  to defer to dated chunks. That can't be enforced, but forward-only scoring means it can't leak outcomes.
- One leg per event, chosen nearest 50c, makes this a sample of contested markets, not of the whole board.
- Brier is scored against the mid at forecast time. Fee-aware P&L needs the bid/ask stored with each row; the scorer
  does not compute it yet.
