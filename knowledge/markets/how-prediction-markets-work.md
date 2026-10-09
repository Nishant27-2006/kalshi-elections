---
aliases:
  - "Market Mechanics: How Kalshi Prediction Markets Work"
  - "Kalshi Microstructure, Fees and Biases"
tags:
  - markets
  - mechanics
  - fees
  - microstructure
  - calibration
created: 2026-10-09
as_of: 2026-10-09
markets:
  - CONTROLH
  - CONTROLS
  - KXPRESPARTY
  - KXHOUSE
---

# Market Mechanics: How Kalshi Prediction Markets Work

Back to [[Politics Knowledge Index]]

Scope: how the Kalshi order book, fee schedule, settlement rules, liquidity and known pricing biases set the hurdle that any forecast has to clear before it becomes a trade.

## Claims

### 1. Order book

- Kalshi's orderbook endpoint returns only bids, for YES and for NO. A YES bid at X is the same as a NO ask at $1.00 − X. (as_of: 2026-10-09; source: https://docs.kalshi.com/getting_started/orderbook_responses)
- The implied YES ask is $1.00 minus the best NO bid. Kalshi's example is a best NO bid of $0.56, which gives a YES ask of $0.44. (as_of: 2026-10-09; source: https://docs.kalshi.com/getting_started/orderbook_responses)
- Each book level is a `[price_dollars, count_fp]` pair of strings, such as `"0.4200"` and `"13.00"`. The string format supports subpenny prices and fractional contracts. (as_of: 2026-10-09; source: https://docs.kalshi.com/getting_started/orderbook_responses)
- `*_dollars` price fields carry up to 4 decimal places. `*_fp` quantity fields always emit 2 decimals, and the smallest unit is 0.01 contracts. (as_of: 2026-10-09; source: https://docs.kalshi.com/getting_started/fixed_point_migration)
- The bare `yes_bid`/`yes_ask`/`volume` keys now read as `None`. Code has to read `yes_bid_dollars`, `volume_fp`, `open_interest_fp`, and for candles `price.close_dollars`. (as_of: 2026-08-17; source: AGENT.md, "Update 2026-08-17")
- `linear_cent` uses a $0.01 tick and `deci_cent` a $0.001 tick. Whole-cent prices are valid in every price-level structure. (as_of: 2026-10-09; source: https://docs.kalshi.com/getting_started/fixed_point_migration)
- `tapered_deci_cent` ticks are $0.001 between $0.00 and $0.10, $0.01 between $0.10 and $0.90, and $0.001 between $0.90 and $1.00. (as_of: 2026-10-09; source: https://docs.kalshi.com/getting_started/fixed_point_migration)
- Among the active Elections and Politics markets in our open-events snapshot, 17,228 use `linear_cent`, 7,566 use `tapered_deci_cent` and 5 use `deci_cent`. (as_of: 2026-10-09; source: GET https://api.elections.kalshi.com/trade-api/v2/events?status=open&with_nested_markets=true, first 12,000 events)
- CONTROLH-2026-D quoted YES 0.900 bid / 0.901 ask on `tapered_deci_cent`. The best YES bid had 160,929 contracts and the best NO bid (0.099) had 81,173. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/markets/CONTROLH-2026-D/orderbook?depth=5)
- CONTROLH-2028-D quoted 0.74 bid / 0.76 ask on `linear_cent`, with 431 contracts on the best YES bid and 19.51 on the best NO bid. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/markets/CONTROLH-2028-D/orderbook?depth=5)
- The 2023 CONTROL contract filing gives a $0.01 minimum tick, while the live CONTROLH-2026 markets use sub-cent ticks. Read the tick from `price_level_structure` and `price_ranges` on the live market, not from the filing. (as_of: 2026-10-09; source: https://assets.kalshi.com/regulatory/product-certifications/CONTROL.pdf and GET /markets?series_ticker=CONTROLH)
- Order `time_in_force` takes one of `fill_or_kill`, `good_till_canceled` or `immediate_or_cancel`. A resting order with an expiry is `good_till_canceled` plus `expiration_time`, and IOC cannot be combined with `expiration_time`. (as_of: 2026-10-09; source: https://docs.kalshi.com/api-reference/orders/create-order-v2.md)
- Orders also accept `post_only` and `reduce_only`. A `reduce_only` order is rejected unless it is `immediate_or_cancel`. (as_of: 2026-10-09; source: https://docs.kalshi.com/api-reference/orders/create-order-v2.md)
- Resting orders queue by price-time priority. (as_of: 2026-10-09; source: https://docs.kalshi.com/llms.txt, "Get Order Queue Position")

### 2. Fees

- Takers pay `round up(0.07 × C × P × (1−P))`, where P is the price in dollars, C is the number of contracts, and the total rounds up to the next cent. (as_of: 2025-10-01; source: https://web.archive.org/web/20251202003606/https://kalshi.com/docs/kalshi-fee-schedule.pdf)
- On series that carry maker fees, makers pay `round up(0.0175 × C × P × (1−P))`, one quarter of the taker coefficient. The fee is charged only when a resting order fills, and cancelling is free. (as_of: 2025-10-01; source: https://web.archive.org/web/20251202003606/https://kalshi.com/docs/kalshi-fee-schedule.pdf)
- Resting orders on series without maker fees pay no trading fee. (as_of: 2025-10-01; source: https://web.archive.org/web/20251202003606/https://kalshi.com/docs/kalshi-fee-schedule.pdf)
- Kalshi charges no settlement fee. (as_of: 2025-10-01; source: https://web.archive.org/web/20251202003606/https://kalshi.com/docs/kalshi-fee-schedule.pdf)
- S&P 500 (INX*) and Nasdaq-100 markets use a 0.035 coefficient. (as_of: 2025-10-01; source: https://web.archive.org/web/20251202003606/https://kalshi.com/docs/kalshi-fee-schedule.pdf)
- The schedule's own 100-contract table lists fees of $0.34 at 5c, $1.32 at 25c, $1.75 at 50c and $0.63 at 90c. For a single contract the fee is $0.01 at 5c, $0.02 at 25c, $0.02 at 50c and $0.01 at 90c. (as_of: 2025-10-01; source: https://web.archive.org/web/20251202003606/https://kalshi.com/docs/kalshi-fee-schedule.pdf)
- Under current API docs, the trade fee rounds up to $0.000001. Balances then align to $0.0001 for direct members and $0.01 for non-direct members, and a per-order accumulator rebates any rounding overpayment. (as_of: 2026-10-09; source: https://docs.kalshi.com/getting_started/fee_rounding.md)
- Bürgi, Deng and Whelan date maker fees to after April 2025 and end their sample there for that reason. Before that, makers paid nothing. (as_of: 2026-01-31; source: docs/papers/kalshi.md, Bürgi/Deng/Whelan "Makers and Takers" p.6)
- Every series sets its fee through `fee_type`, which takes one of `quadratic`, `quadratic_with_maker_fees`, `quadratic_with_combo_maker_fees` or `flat`, plus a `fee_multiplier`. Events can override both. (as_of: 2026-10-09; source: https://docs.kalshi.com/api-reference/market/get-series and https://docs.kalshi.com/llms.txt "Get Event Fee Changes")
- KXPRESPARTY, CONTROLH, CONTROLS and KXHOUSE are all `fee_type = quadratic` with `fee_multiplier = 1`, meaning taker fees only and no maker fee. (as_of: 2026-10-09; source: GET https://api.elections.kalshi.com/trade-api/v2/series/{ticker})
- The series fee-change log has 107 entries. Its earliest `quadratic_with_maker_fees` switch is dated 2025-10-04, and the only election-named series in the log is KXELECTIRAN. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/series/fee_changes?show_historical=true)
- The 2024 presidential market charged no transaction fees. (as_of: 2026-01-05; source: docs/papers/2601.01706.md, Gebele & Matthes p.23)
- In a 1c-wide recorded book, the round trip costs 30.27% of price at 5c, 14.21% at 25c, 8.91% at 50c and 2.50% at 90c. At 50c the fee is 3.5x the spread. (as_of: 2026-08-19; source: docs/superpowers/records/2026-08-19-first-live-backtest.md §1)
- Across 158,083 recorded trades held 360s, the null strategy netted −7.002% per trade: +0.185% direction, −2.717% spread, −4.464% fees. (as_of: 2026-08-19; source: docs/superpowers/records/2026-08-19-first-live-backtest.md §2)

**Worked cost table.** This uses the 100-lot taker fee from the schedule above, a 1c quoted spread, and the same fee on both legs. Arithmetic is ours (as_of: 2026-10-09; source: fee schedule above). Hurdle means the minimum |forecast − mid| in probability points needed to break even. A political maker entry has no fee on `quadratic` series, but it carries fill risk and adverse selection.

| Price | Taker fee/contract | Fee % of price | 1-lot fee % | Hold-to-settle hurdle (½ spread + 1 fee) | Round trip (spread + 2 fees) | Round trip % of price |
|---|---|---|---|---|---|---|
| 5c | 0.34c | 6.8% | 20% | 0.84c | 1.68c | 33.6% |
| 25c | 1.32c | 5.3% | 8% | 1.82c | 3.64c | 14.6% |
| 50c | 1.75c | 3.5% | 4% | 2.25c | 4.50c | 9.0% |
| 90c | 0.63c | 0.7% | 1.1% | 1.13c | 2.26c | 2.5% |

These round-trip percentages match the measured table in the backtest record to within 3.5 percentage points.

### 3. Resolution rules

- `rules_primary` holds the most important market terms in plain language, and `rules_secondary` holds the secondary terms. (as_of: 2026-10-09; source: https://docs.kalshi.com/api-reference/market/get-market)
- CONTROLH-2026 `rules_secondary` reads: "This market may be determined early based on a consensus of media calls projecting control of the U.S. House... Otherwise, victory will be determined by the party identification of the Speaker of the House on February 1, 2027." (as_of: 2026-10-09; source: GET https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=CONTROLH&status=open)
- CONTROLH-2026 markets have `can_close_early = true`, `close_time = 2027-02-01T15:00Z` and `settlement_timer_seconds = 3600`. (as_of: 2026-10-09; source: same)
- Under the CONTROL filing, the Source Agency is congress.gov and the contract expires on February 1 of the year the term begins, at 10:00 AM ET. (as_of: 2023-06-12; source: https://assets.kalshi.com/regulatory/product-certifications/CONTROL.pdf)
- The KXHOUSE series metadata lists the FAA as its settlement source and links ROCKET.pdf, which is a metadata error. Settle from rules text and contract terms, never from `settlement_sources` alone. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/series/KXHOUSE)
- A market's lifecycle runs initialized → active → closed → determined → finalized, with `disputed` and `amended` possible after determination. A dispute can lead to re-determination, and the settlement timer then restarts. (as_of: 2026-10-09; source: https://docs.kalshi.com/getting_started/market_lifecycle.md)
- When `can_close_early` is true, `close_time` can move earlier, so a market can close ahead of schedule and before determination. Resting orders are cancelled after close. (as_of: 2026-10-09; source: https://docs.kalshi.com/getting_started/market_lifecycle.md)
- `result` takes one of `yes`, `no`, `scalar` or empty. The API has no separate "void" value, and `settlement_value_dollars` is filled in only after determination. (as_of: 2026-10-09; source: https://docs.kalshi.com/api-reference/market/get-market)
- Settlement floors, which allow partial early payout on scalar markets, are documented but not live yet. (as_of: 2026-10-09; source: https://docs.kalshi.com/getting_started/settlement_bounds.md)
- Before settlement, Kalshi may at its discretion start a Market Outcome Review. The Outcome Review Committee decides within 24 hours, and its decision is final. (as_of: 2023-02-16; source: https://www.cftc.gov/filings/orgrules/rule022123kexdcm002.pdf, Rule 7.1)
- If the source agency becomes unreliable, Rule 7.2 lets Kalshi designate a new Source Agency and Underlying after trading has begun. (as_of: 2023-02-16; source: same, Rule 7.2)
- Kalshi resolved the 2024 presidential market on inauguration and Polymarket on the media call. This mismatch kept a Kalshi–Polymarket spread of about $0.03, peaking near $0.07, before election night. (as_of: 2026-01-05; source: docs/papers/2601.01706.md p.23)

### 4. Liquidity

- In our snapshot, the median quoted spread on two-sided active Elections markets is 9c, and only 9% quote at 2c or tighter. The median spread is 6c for Politics, 6c for Sports and 8c for Financials. (as_of: 2026-10-09; source: GET /events snapshot as above, our computation)
- Elections markets with at least 10,000 contracts of lifetime volume (n = 1,042) have a median spread of 1c. Politics markets above the same volume threshold (n = 561) have a median of 2.5c. (as_of: 2026-10-09; source: same)
- 54% of active Elections markets have zero lifetime volume, and the top 1% by volume hold 92% of all Elections volume. (as_of: 2026-10-09; source: same)
- Median spreads in two-sided political markets by days to close: 7c for 30 days or less (71% with no 24h volume), 5.6c for 31–365 days (75%), and 9c beyond 365 days (92%). The >365d bucket includes placeholder close dates in 2099. (as_of: 2026-10-09; source: same)
- In the Bürgi/Deng/Whelan sample, the median contract has $8,982 staked and the mean trade is $100 (median $35). (as_of: 2026-01-31; source: docs/papers/kalshi.md p.10, p.13)
- Kalshi pays interest on cash and on the collateral behind open positions, at 3.50% APY for balances of $250 or more. It accrues daily on net portfolio value at 12am ET and pays monthly. (as_of: 2026-10-09; source: https://help.kalshi.com/en/articles/13823847-apy-on-kalshi)
- Gebele & Matthes list locked capital, differing resolution rules and regulatory segmentation as the frictions that keep equivalent contracts 2–4% apart across venues. (as_of: 2026-01-05; source: docs/papers/2601.01706.md p.20)
- CONTROL position limits are $125,000 per individual member, $5,000,000 per entity and $50,000,000 per ECP. Those with demonstrated hedging need get double. (as_of: 2023-06-12; source: https://assets.kalshi.com/regulatory/product-certifications/CONTROL.pdf)
- A 2023 rulebook amendment replaced the uniform $25,000 position limit in Rule 5.14(a). (as_of: 2023-02-16; source: https://www.cftc.gov/filings/orgrules/rule022123kexdcm002.pdf)

### 5. Known biases

- Wolfers & Zitzewitz show that under broad conditions, prediction-market prices are usually close to traders' mean beliefs. They name risk aversion and the distribution of beliefs as the key drivers, and call prices "useful (albeit sometimes biased)". (as_of: 2006-05-31; source: https://www.nber.org/papers/w12200)
- In horse racing, longshots are overbet and favorites underbet. Snowberg & Wolfers find that misperception of probabilities explains this better than risk-love. (as_of: 2010-08-01; source: Snowberg & Wolfers, JPE 118(4):723–746; https://www.nber.org/papers/w15923)
- Page & Clemen find prediction markets reasonably well calibrated close to expiry but significantly biased toward favorite/longshot further out. Once the time value of money is counted, the bias is exploitable only by traders with low discount rates. (as_of: 2013-05-01; source: Economic Journal 123(568):491–513; https://scholars.duke.edu/publication/765630)
- On Kalshi from 2021 to April 2025 (46,282 YES contracts), the average pre-fee return is about −20%. Contracts at 10c or below lose more than 60% after fees. (as_of: 2026-01-31; source: docs/papers/kalshi.md p.3, p.17)
- In the paper's worked example, a 5c contract that wins 3% of the time returns −40% pre-fee, and a 95c contract that wins 98% returns +3.1%. (as_of: 2026-01-31; source: docs/papers/kalshi.md p.17)
- The full-sample Mincer-Zarnowitz fit of Y − P = α + ψP gives ψ = 0.034 (SE 0.005) and α = −1.736 (SE 0.153), with N = 156,986. (as_of: 2026-01-31; source: docs/papers/kalshi.md p.20 Table 4)
- For Politics, ψ = 0.022 (SE 0.021, not significant) and α = −1.912 (SE 0.340, significant at 1%), with the joint F-test p = 0.000 on 26,819 observations. (as_of: 2026-01-31; source: docs/papers/kalshi.md p.24 Table 8)
- ψ by year is 0.041 in 2021, 0.023 in 2022, 0.036 in 2023, 0.048 in 2024 and 0.021 in 2025, the last significant only at 10%. The authors read this as some weakening in 2025. (as_of: 2026-01-31; source: docs/papers/kalshi.md p.25 Table 9)
- ψ is largest in the lowest-volume quintile (0.045). Above that quintile, more volume does not reduce the bias. (as_of: 2026-01-31; source: docs/papers/kalshi.md p.23 Table 6)
- Mean returns are −9.64% for Makers and −31.46% for Takers. Makers buying at 50c or above earn +2.6%. (as_of: 2026-01-31; source: docs/papers/kalshi.md p.27)
- Makers do 43.5% of the buying at 1–10c and 56.5% at 90–99c. On closing day, Makers lose on contracts priced at 10c or below, much as Takers do, which the authors tie to Page's late-longshot "Yogi Berra" effect. (as_of: 2026-01-31; source: docs/papers/kalshi.md p.26–27)
- Mean absolute error falls from roughly 11–14 one day out to roughly 6 at close (values read off a chart). (as_of: 2026-01-31; source: docs/papers/kalshi.md p.16 Fig 4)
- On Polymarket, buying NO was the most profitable realized arbitrage strategy, at $17.3M of about $39.6M total. 662 of 1,578 multi-outcome markets had at least one sum-to-one violation. (as_of: 2025-08-05; source: docs/papers/2508.03474.md p.17, p.20–21)
- Across 1,055 mutually exclusive political Kalshi events with two or more active markets, the median sum of YES asks is 1.031. The 10th percentile is 1.00 and the 90th is 1.19, with missing asks counted as $1. The median sum of YES bids is 0.96, and 2.7% of events have bids summing above 1. (as_of: 2026-10-09; source: GET /events snapshot, our computation)
- In 6.9% of those events the YES asks sum below 1. Some of these events are not exhaustive, so a low sum is not automatically an arbitrage. (as_of: 2026-10-09; source: same)
- Across 41 Florida-primary events, best asks summed to at least 101c everywhere. The one event whose bids summed above 100 (FL-23 D, 100.4c) came to −4.6c after fees. (as_of: 2026-08-17; source: AGENT.md)
- Momentum entries on political contracts lost at every trigger from 3c to 10c, and losses grew as the trigger rose (FL primary, n = 67–123), which is a sign of mean reversion. No verified study measures election-night overreaction on Kalshi. (as_of: 2026-08-17; source: AGENT.md "Backtest re-run")

## Base rates

- base_rate: kalshi_flb_mz_slope_all = 0.034; n = 156986; window = 2021-2025-04; (as_of: 2026-01-31; source: docs/papers/kalshi.md p.20 Table 4)
- base_rate: kalshi_flb_mz_const_all_cents = -1.736; n = 156986; window = 2021-2025-04; (as_of: 2026-01-31; source: docs/papers/kalshi.md p.20 Table 4)
- base_rate: kalshi_flb_mz_slope_politics = 0.022; n = 26819; window = 2021-2025-04; (as_of: 2026-01-31; source: docs/papers/kalshi.md p.24 Table 8)
- base_rate: kalshi_flb_mz_const_politics_cents = -1.912; n = 26819; window = 2021-2025-04; (as_of: 2026-01-31; source: docs/papers/kalshi.md p.24 Table 8)
- base_rate: kalshi_flb_mz_slope_2025 = 0.021; window = 2025-01-2025-04; (as_of: 2026-01-31; source: docs/papers/kalshi.md p.25 Table 9)
- base_rate: kalshi_maker_mean_return = -0.0964; window = 2021-2025-04; (as_of: 2026-01-31; source: docs/papers/kalshi.md p.27)
- base_rate: kalshi_taker_mean_return = -0.3146; window = 2021-2025-04; (as_of: 2026-01-31; source: docs/papers/kalshi.md p.27)

## Implications for our forecaster

- The benchmark is the recalibrated price, not the raw one. If the Politics coefficients are in cents (the paper does not state units, so this is our reading), α + ψP gives an expected YES excess of −1.80c at 5c, −1.36c at 25c, −0.81c at 50c and +0.07c at 90c, crossing zero near 87c. A forecast that only rediscovers this has no edge. (as_of: 2026-10-09; source: our arithmetic on docs/papers/kalshi.md p.24)
- Fit the recalibration on earlier data only, and refit by year. ψ fell from 0.048 in 2024 to 0.021 in 2025, so a fixed FLB prior can overcorrect. (as_of: 2026-01-31; source: docs/papers/kalshi.md p.25)
- The cost hurdle depends on price. Holding to settlement after a taker entry in a 1c book needs an edge of about 0.84c at 5c, 1.82c at 25c, 2.25c at 50c and 1.13c at 90c. Flipping before settlement roughly doubles that (worked table, §2). (as_of: 2026-10-09; source: fee schedule, our arithmetic)
- A 9c spread, the median for Elections markets, puts the hold-to-settle hurdle at about 4.5c plus the fee. Most long-dated political books are untradeable as a taker unless the edge exceeds 5–7 points. (as_of: 2026-10-09; source: GET /events snapshot plus fee schedule, our arithmetic)
- Edge is most likely to survive fees on the NO side of cheap political longshots. Using the coefficients above, NO bought at 95c expects about +1.80c pre-fee, which is about +0.96c after a 0.34c fee and a 0.5c half-spread, or roughly 1% on capital. That return is small, needs depth, and must clear the time to resolution. (as_of: 2026-10-09; source: our arithmetic on docs/papers/kalshi.md p.24 and the fee schedule)
- Political series are `quadratic`, so resting orders pay no fee. Maker entry is the structural way to cut the hurdle to near the half-spread, provided the fill model accounts for adverse selection. (as_of: 2026-10-09; source: GET /series; docs/superpowers/records/2026-08-19-first-live-backtest.md §5)
- Capital lock-up costs less on Kalshi than Page & Clemen's time-value argument implies, because positions earn 3.50% APY. Report every edge both per contract and annualized to `close_time`, and treat `can_close_early` media-call rules as a shorter effective horizon. (as_of: 2026-10-09; source: help.kalshi.com APY page; CONTROLH rules_secondary)
- Before scoring a forecast against a multi-outcome event, renormalize the event's prices, since sums of asks commonly run 1.00–1.19. Never count a sum-to-one gap as edge without netting fees and the spread on every leg. (as_of: 2026-10-09; source: GET /events snapshot; AGENT.md FL-23 D example)

## Related

- [[Mechanics: Kalshi Political Market Settlement]]
- [[Base Rate: Poll and Forecast Favorites]]
- [[Base Rate: Polling Error]]
- [[Politics Knowledge Index]]

## Timeline

- [2026-10-09] Data: open-events snapshot (12,000 events), CONTROLH orderbooks, series fee types https://api.elections.kalshi.com/trade-api/v2/events?status=open&with_nested_markets=true
- [2026-08-19] Record: first live backtest cost table docs/superpowers/records/2026-08-19-first-live-backtest.md
- [2026-08-17] Record: fixed-point migration, FL primary momentum and sum-to-one checks AGENT.md
- [2026-01-31] Paper: Bürgi/Deng/Whelan, Makers and Takers (January 2026) docs/papers/kalshi.md
- [2026-01-05] Paper: Gebele & Matthes, law of one price across venues https://arxiv.org/abs/2601.01706
- [2025-10-04] Fees: first `quadratic_with_maker_fees` switch in the series fee-change log https://api.elections.kalshi.com/trade-api/v2/series/fee_changes?show_historical=true
- [2025-10-01] Fees: schedule effective (taker 0.07, maker 0.0175, INX/NASDAQ100 0.035) https://web.archive.org/web/20251202003606/https://kalshi.com/docs/kalshi-fee-schedule.pdf
- [2025-08-05] Paper: Saguillo et al., Polymarket arbitrage https://arxiv.org/abs/2508.03474
- [2023-06-12] Filing: CONTROL contract terms (congress.gov source, position limits) https://assets.kalshi.com/regulatory/product-certifications/CONTROL.pdf
- [2023-02-16] Filing: rulebook position-limit amendment, Rules 7.1/7.2 https://www.cftc.gov/filings/orgrules/rule022123kexdcm002.pdf
- [2013-05-01] Paper: Page & Clemen, calibration vs time to expiry https://scholars.duke.edu/publication/765630
- [2010-08-01] Paper: Snowberg & Wolfers, FLB from misperceptions https://www.nber.org/papers/w15923
- [2006-05-31] Paper: Wolfers & Zitzewitz, prices as probabilities https://www.nber.org/papers/w12200
