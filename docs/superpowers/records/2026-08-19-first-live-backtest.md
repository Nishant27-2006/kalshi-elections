# First live backtest — measured results, 2026-08-19

Recording: 37 minutes, 132 snapshots at 18s, 1,786 tickers, 198,074 rows
(49 MB, untracked) across KXMLBGAME, KXMLBTOTAL, KXMLBSPREAD, KXMLBHR,
KXNFLGAME, KXWNBAGAME, KXATPMATCH, KXMLSGAME, KXNCAAFGAME, KXBTCD.
`is_live=False` throughout. No order was placed.

## 1. The cost floor dominates everything

Round trip on a flat 1c-wide market:

| price | spread | fee | total |
|---|---|---|---|
| 5c | 18.18% | 12.08% | **30.27%** |
| 25c | 3.92% | 10.29% | 14.21% |
| 50c | 1.98% | 6.93% | 8.91% |
| 90c | 1.10% | 1.39% | **2.50%** |

**The fee dominates the spread**, by 3.5x at 50c. Kalshi charges
`0.07*P*(1-P)`, which peaks exactly at the mid prices where the liquid
books are. Two consequences:

- Cost is **minimised on heavy favourites**, not on mid-priced contracts.
- A resting **limit** order pays neither the spread nor the taker fee. That
  is the only structural way out of this table.

## 2. The null strategy — the bar any signal must clear

101,189 trades, 122 portfolio buckets, whole recording, 360s hold:

    direction (mid-to-mid)   +0.322%
    spread paid              -2.703%
    fees paid                -4.428%
    net                      -6.819%   per trade on capital
    Sharpe (per bucket)      -8.20
    mean RU                   0.354 per contract
    return per RU           -63.3%

Over 18s to 216s the market's mean directional move is **under 0.1%** while
the cost is **7.1%**. At these horizons no signal of any kind can pay for
itself. A strategy is only possible where |direction| can exceed cost.

## 3. Momentum — rejected, and the reason matters

Grid of 20 configurations fitted on the first 60% by clock, best scored once
on the held-out tail. Best on train: lookback 8 bars (144s), threshold 5c.

    mean net return    +19.88%  per trade      <- looks like a real edge
    hit rate            44.3%
    Sharpe (bucket)      0.36
    Deflated Sharpe     -1.54                  <- fails after 20 configs
    top 5% PnL share      90%                  <- twenty trades
    mean ex-top-5%       +2.15%
    distinct events         22

The top 5% were **all the same baseball game** (Athletics–Kansas City),
contracts running 17c to 99c as the total resolved. That is one event, not a
strategy. The Deflated Sharpe rejected it independently.

**Verdict: no momentum edge is established.** 22 distinct events is not a
sample. This is not evidence momentum fails — it is evidence 37 minutes
cannot answer the question.

## 4. RU is calibrated to a far longer horizon than we recorded

Breaches: 1 in 1,583 tickers, in every vertical, at every horizon measured.

Excursion versus holding time does **not** follow a power law. The fitted
exponent slides 0.98 -> 0.44 as the window extends and R^2 falls 0.95 ->
0.81. Measured directly, mean excursion is 0.0176 at 1242s and **0.0161 at
2448s — it goes down.** Prices revert.

    18s held  -> excursion 0.0008   RU is 488x larger
   630s held  -> excursion 0.0128   RU is  31x larger
  2448s held  -> excursion 0.0161   RU is  25x larger

**A correction I made mid-session:** fitted on the first 8 minutes alone the
exponent read 0.68 and I reported "these markets trend, moves persist". With
the full recording it reads 0.44 — mean-reverting. The first number was an
artefact of the window. The harness now refuses to extrapolate from a fit
that is not scale-free, and says so.

Mean reversion is **bad for momentum** and **good for fading moves and for
resting quotes** — which points the same direction as the cost table.

## 5. What this does and does not license

Does not: any live capital, any momentum sizing, any claim that RU is
validated.

Does: the recorder works, the cost structure is now quantified rather than
assumed, and the two strategy directions worth testing next are both
maker-side — post-and-fade rather than take-and-chase.

Next measurement, in priority order:

1. Record **to settlement** on a handful of games. RU is a to-settlement
   measure and intraday snapshots cannot validate it (spec 10b).
2. Re-run momentum across **hundreds of distinct events**, not 22.
3. Model a **maker** fill — the only branch where the cost table is
   survivable.
