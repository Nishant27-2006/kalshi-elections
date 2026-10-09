## Findings (written 2026-10-09 after the 26 runs; numbers are from the table above)

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
