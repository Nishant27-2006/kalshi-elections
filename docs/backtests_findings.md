## Findings (updated 2026-10-09 after the full-data rerun; the table above is the full-data run)

**Full-data rerun.** The first pass used 18,290 of 19,488 markets, because the candle fetch was stopped for low
memory. After the fetch completed, all 26 configs were re-scored on the full set (cutoff 2026-06-19, 10,754 train /
4,231 test markets). Both passes are in `docs/backtest_runs.jsonl`. Changes from the first pass:
- **B0:** skill +1.00% → **+0.91%**, CI still excludes zero. P&L +$3.16 → **+$3.12** (90 trades, CI [−8.1c, +15.3c]).
- **V18 (tight books):** +$6.86 → **+$6.25** (60 trades, CI [−2.8c, +23.8c]). Still the best, still not significant.
- **V11 (min_edge 2c):** turned negative (−$1.28 on 283 trades). **V12 (min_edge 10c)** now makes no trades.
- **V20 (maker):** −$22.24 → **−$15.04** on 930 fills; still the worst.
- **V25 (knowledge prior):** +0.30% skill, CI now touches zero.
- **Sophistication:** the composite terciles now show a monotone skill gradient (low +1.25%, mid +1.10%, high
  +0.39%). See docs/participants.md.

Numbers in points 1–6 below are from the first pass; the direction of every finding is unchanged on full data.

**Against the success criterion, "better calibrated than the market price, after fees":** calibration is better,
by a small amount that clears the bootstrap. Profit after fees is **not** established; no configuration's P&L CI
is above zero.

1. **The old plan's estimator (B0) beats the market's Brier on held-out data.** Brier skill is +1.0% (0.08957 vs
   0.09047) and the event-bootstrap CI of the difference is [−0.00147, −0.00034]. The gain is small.
   - **What drives it:** mostly the favourite-longshot correction. One global recalibration curve (V02) gets
     +0.47%; per-archetype intercepts (B0) roughly double that. Fitting only the most recent year of train (V10)
     is the best forecaster at +1.07%.
   - **Calibration table (B0 section):** the market's 10–30c contracts resolved YES 3–5 points less often than
     their price, and its 60–70c contracts 2.8 points more often.
   - **External replication:** Bürgi et al.'s published politics coefficients, applied with no fitting (V05),
     also beat the market (+0.33%, CI < 0). An external estimate reproduced the direction.
   - **Isotonic recalibration (V04) overfits:** −0.11% skill, a CI that spans zero.
2. **No strategy makes money with confidence.**
   - **B0:** +$3.16 on 88 one-contract trades (+3.6c/trade, CI [−8.5c, +14.6c]). 62% of that P&L is one event.
   - **Closest to significance:** tight books only (V18), +$6.86 on 57 trades, CI [−0.7c, +26.3c], with no event
     above 19% of P&L. It is a lead worth re-testing on fresh data, not a result.
   - **Fees decide a lot:** the zero-fee counterfactual (V24) earns +$5.26 against +$3.16.
   - **Lower thresholds dilute:** min_edge 2c (V11) trades 3× as often for half the P&L.
3. **Maker execution loses money: −$22.24 over 824 fills (V20), −2.7c/fill, CI [−5.4c, +0.3c].** Fills are simulated only when the price
   trades through our resting bid, so we get filled exactly when the market moves against us. With no maker fee on
   political series, cost isn't the problem; adverse selection is. That answers the open question in the 2026-08-19
   live-backtest record ("model a maker fill"): on daily data, naive passive quoting is worse than taking.
4. **The knowledge layer does not earn its place in mechanical form (V25).**
   - Adding the best retrieved `base_rate:` line as a feature gives +0.40% skill. That is below global Platt with no
     knowledge at all (+0.47%), and far below B0.
   - Two reasons. Most resolved markets (primaries, policy events, visits) have no matching base rate. And the
     race-specific notes are dated October 2026, so the as-of filter rightly hides them from every backtest
     snapshot.
   - The fund design's own test ("if context never improves on the base rate, the knowledge layer is not earning
     its place") is **failed for now**. The knowledge files still matter going forward, for 2026 markets and for an
     LLM judgment step, which remains untested.
5. **Mean reversion, again.** The reversion term (V07) improves Brier over plain recalibration (+0.66% vs +0.47%),
   the same sign as the repo's earlier finding that momentum loses on Kalshi political books.
6. **Sophistication:** see docs/participants.md. Edge does not concentrate in low-sophistication terciles (V21–V23
   skill +0.96%, +1.17%, +0.63%; no P&L CI above zero).

**Rows that match B0 by construction:**
- V08: the blend picked w = 1, i.e. pure B0, on its validation tail.
- V17: every B0 trade was already priced 15–85c.
- V11–V17, V20, V24 reuse B0's estimator, so their Brier equals B0's; only the trade rule differs.

**Process disclosures:**
- Before the final run, an unlogged preliminary pass of three configs (B0, V01, V02) on a 4k-market partial sample
  was used to debug the pipeline. After it, the archetype regexes were expanded so that "other" fell from 27% to 10%
  of markets. That change used title text only, not results, but it was made after seeing preliminary test numbers.
- Candle data covers 18,290 of 19,488 universe markets. The fetch was stopped by the session for low system memory
  and not restarted. The missing tail is concentrated in the largest series (approval ladders).
- 26 configurations were scored on one test set. The Brier "wins" are many near-copies of the same recalibration
  idea, not independent confirmations.

## Walk-forward re-test of the leads (earlier periods only; locked test set untouched)

`python -m forecast.walkforward`. Train events (before the 2026-06-19 outer cutoff) are cut into 5 blocks by close; fold i fits on blocks 1..i and scores block i+1 (snapshots after the last fitting event closed). These periods played no part in picking the leads.

| fold | scored from | strategy | markets | Brier skill | ΔBrier CI95 | trades | P&L $ | P&L/trade | P&L/trade CI95 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2025-01-03 | B0 old plan Stage A | 1363 | -0.0590 | [0.00293, 0.01202] | 342 | -20.879 | -0.061 | [-0.126, 0.0124] |
| 1 | 2025-01-03 | V18 tight books only (spread<=4c) | 935 | -0.0365 | [-0.0011, 0.0085] | 240 | -2.612 | -0.0109 | [-0.0753, 0.0628] |
| 1 | 2025-01-03 | L1 low-efficiency tercile | 747 | -0.0673 | [0.00259, 0.01425] | 181 | -9.072 | -0.0501 | [-0.1333, 0.0417] |
| 2 | 2025-06-05 | B0 old plan Stage A | 1704 | +0.0038 | [-0.00328, 0.00252] | 111 | 6.246 | 0.0563 | [-0.12, 0.222] |
| 2 | 2025-06-05 | V18 tight books only (spread<=4c) | 1006 | +0.0006 | [-0.00339, 0.00394] | 75 | 7.255 | 0.0967 | [-0.1367, 0.3095] |
| 2 | 2025-06-05 | L1 low-efficiency tercile | 975 | +0.0034 | [-0.00404, 0.00332] | 75 | 9.863 | 0.1315 | [-0.1089, 0.3238] |
| 3 | 2026-01-01 | B0 old plan Stage A | 1345 | +0.0166 | [-0.00385, 0.00016] | 111 | 10.34 | 0.0932 | [-0.0338, 0.1994] |
| 3 | 2026-01-01 | V18 tight books only (spread<=4c) | 1000 | +0.0176 | [-0.00377, 0.00034] | 95 | 8.068 | 0.0849 | [-0.0253, 0.1757] |
| 3 | 2026-01-01 | L1 low-efficiency tercile | 561 | +0.0322 | [-0.00683, -0.00087] | 40 | 8.674 | 0.2168 | [0.0804, 0.3433] |
| 4 | 2026-04-12 | B0 old plan Stage A | 2347 | +0.0126 | [-0.00169, -0.0002] | 69 | 16.777 | 0.2432 | [0.1153, 0.3606] |
| 4 | 2026-04-12 | V18 tight books only (spread<=4c) | 1964 | +0.0124 | [-0.00165, -1e-05] | 56 | 13.236 | 0.2364 | [0.0883, 0.3639] |
| 4 | 2026-04-12 | L1 low-efficiency tercile | 1267 | +0.0152 | [-0.00235, -0.00023] | 31 | 9.745 | 0.3143 | [0.1748, 0.441] |

Totals across the 4 folds: B0 old plan Stage A: $+12.48 on 633 trades; V18 tight books only (spread<=4c): $+25.95 on 466 trades; L1 low-efficiency tercile: $+19.21 on 327 trades.

**Reading.**
- **The leads depend on the period.** In fold 1 (fit on 2021–2024, scored from 2025-01-03) every strategy is *worse* than the market: B0 skill −5.9%, with a CI excluding zero in the wrong direction, and −$20.88 on 342 trades. Low-efficiency and tight books lose too.
- **Folds 3–4 (2026) are positive.** In fold 4 all three strategies have P&L CIs above zero, and low-efficiency is also above zero in fold 3.
- **Likely cause.** A model fit on the thin 2021–24 political book does not transfer to the 2025 explosion in listings. Once 2025 data is in the fit, the recalibration works and makes money in the folds after it.
- **What this means.** The edge is recent and depends on refitting. It is not established as stable. The held-out test (cutoff 2026-06-19) continues the positive 2026 pattern but with CIs spanning zero.
- **Low-efficiency tercile:** the most consistent of the three in 2026 (CI > 0 in folds 3 and 4), but negative in fold 1. Keep it as the lead to re-test first on post-2026-10-09 settlements.

## Multiple-comparisons correction (details: docs/multiple_testing.md)

Holm and Benjamini–Hochberg, applied separately to the 37 Brier tests and the 31 P&L tests (26 held-out runs plus
the 12 tercile cuts; p-values approximated from the bootstrap CIs):
- **Brier:** 7 of 37 survive Holm and 30 survive BH. Survivors under Holm include recency (V10), global Platt (V02),
  the paper's fixed coefficients (V05), reversion (V07) and sum-to-one (V09). **B0 survives BH but not Holm**
  (Holm-adjusted p = 0.07). Forecasting better than the raw price by recalibrating it is a robust result.
- **P&L: 0 of 31 survive either correction.** The low-efficiency tercile (raw p ≈ 0.036) adjusts to Holm 1.0 /
  BH 0.82. **No profit claim survives correction for the number of looks.**
- V22 and the composite-mid tercile are the same test counted twice, which makes the correction slightly conservative.
