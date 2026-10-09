# Participant sophistication — submodels and where the edge sits

Generated 2026-10-09 08:55 UTC by `python -m forecast.participants_report`. Same split as docs/backtests.md (cutoff 2026-06-24); cut points and z-scores fit on TRAIN.

## Submodels (all observable at decision time T)

- **liquidity** = z(log 7-day volume) + z(log open interest) − z(spread)
- **efficiency** = −z(|lag-1 autocorrelation of daily mid changes, last 30d|) − z(share of moves that reverse next day)
  — a book where moves stick is pricing information; one where moves bounce back is noise or overreaction
- **activity** = z(log days traded in last 30) − z(days since the last candle)
- **composite** = mean of the three (each re-standardised). Depth is NOT in the score: there is no historical order-book
  depth on the API, only current books, and using today's depth for a 2025 snapshot would leak.

Correlation between submodels (train snapshots):

| | liquidity | efficiency | activity |
|---|---|---|---|
| liquidity | 1.0 | -0.04 | 0.61 |
| efficiency | -0.04 | 1.0 | -0.05 |
| activity | 0.61 | -0.05 | 1.0 |

## 1. Validation on train: is a low-score book worse calibrated?

Headroom = Brier of the mid minus Brier after a Platt recalibration fit inside that tercile (in-sample, so an upper bound).

| composite tercile | markets | Brier of mid | recalibration headroom |
|---|---|---|---|
| low | 5498 | 0.11932 | 0.0003 |
| mid | 7563 | 0.10871 | 8e-05 |
| high | 5255 | 0.08918 | 0.00059 |

## 2. Held-out test: B0 (old-plan estimator) by tercile

| submodel | tercile | markets | events | Brier mkt | Brier B0 | skill | ΔBrier CI95 | trades | P&L $ | P&L/trade | P&L/trade CI95 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| composite | low | 1757 | 645 | 0.10098 | 0.10001 | +0.0096 | [-0.00194, 6e-05] | 11 | 0.231 | 0.021 | [-0.3592, 0.2635] |
| composite | mid | 2522 | 838 | 0.09313 | 0.09204 | +0.0117 | [-0.00175, -0.00052] | 41 | 0.542 | 0.0132 | [-0.155, 0.1835] |
| composite | high | 1651 | 696 | 0.08653 | 0.08598 | +0.0063 | [-0.00133, 0.00023] | 36 | 2.382 | 0.0662 | [-0.0928, 0.2249] |
| liquidity | low | 1643 | 578 | 0.11092 | 0.10984 | +0.0097 | [-0.002, -5e-05] | 13 | -0.205 | -0.0157 | [-0.3955, 0.253] |
| liquidity | mid | 2352 | 785 | 0.08888 | 0.08799 | +0.0100 | [-0.00164, -0.00014] | 36 | -1.065 | -0.0296 | [-0.1883, 0.1621] |
| liquidity | high | 1757 | 685 | 0.08282 | 0.08189 | +0.0113 | [-0.00158, -0.00018] | 39 | 4.426 | 0.1135 | [-0.0332, 0.2585] |
| efficiency | low | 1853 | 736 | 0.09121 | 0.09017 | +0.0114 | [-0.00177, -0.00033] | 10 | 0.443 | 0.0443 | [-0.0903, 0.1896] |
| efficiency | mid | 2936 | 866 | 0.1026 | 0.10132 | +0.0124 | [-0.00203, -0.00055] | 53 | 3.078 | 0.0581 | [-0.09, 0.2125] |
| efficiency | high | 1688 | 691 | 0.0882 | 0.0879 | +0.0034 | [-0.00111, 0.00051] | 25 | -0.366 | -0.0146 | [-0.185, 0.1852] |
| activity | low | 2009 | 631 | 0.09899 | 0.0981 | +0.0090 | [-0.00176, -0.00012] | 24 | 3.102 | 0.1293 | [-0.0971, 0.2855] |
| activity | mid | 2381 | 820 | 0.09816 | 0.09775 | +0.0042 | [-0.00121, 0.00038] | 38 | -2.411 | -0.0634 | [-0.2441, 0.1006] |
| activity | high | 1343 | 591 | 0.09968 | 0.09879 | +0.0090 | [-0.00187, -9e-05] | 26 | 2.464 | 0.0948 | [-0.0661, 0.2435] |

## 3. Trade sizes (261 random test markets, prints before the first test snapshot)

- median print size: median across markets 18.50 contracts
- share of fractional (<1 contract) prints: median 0.00
- share of >=100-contract prints: median 0.18

Spearman correlation with the composite score:

| | composite | median_size | frac_share | big_share |
|---|---|---|---|---|
| composite | 1.0 | 0.04 | 0.2 | 0.17 |
| median_size | 0.04 | 1.0 | -0.22 | 0.82 |
| frac_share | 0.2 | -0.22 | 1.0 | -0.03 |
| big_share | 0.17 | 0.82 | -0.03 | 1.0 |

## What this says

**The submodels measure different things, but "sophistication" did not validate.**
- Liquidity and activity are correlated (0.61); efficiency is independent of both (−0.04).
- On train, a low composite score does not mean a more recalibratable book. In-sample headroom is 0.0003 (low),
  0.0001 (mid) and 0.0006 (high). If anything, the most liquid, active books carry the most fixable
  favourite-longshot bias, consistent with Bürgi et al.'s finding that the bias survives in high-volume Kalshi contracts.
- The low tercile's higher raw Brier (0.119 vs 0.089) reflects its prices sitting nearer 50c (more uncertain
  questions), not worse calibration.

**Does our edge concentrate in low-sophistication markets? No, on this evidence.**
- **Composite score:** B0's Brier skill is +0.96% (low), +1.17% (mid), +0.63% (high), and the low and high CIs
  both include zero.
- **P&L:** no tercile of any submodel has a P&L CI above zero. The largest point estimate is in the *high*-liquidity
  tercile (+$0.11/trade on 39 trades, CI [−0.03, +0.26]), the opposite of the hypothesis.
- **The one direction-consistent hint is the efficiency submodel.** Skill is +1.1% and +1.2% where moves reverse or
  trickle (low and mid efficiency), against +0.34% (CI includes zero) where moves stick. So the forecaster may be
  correcting noise, not information. That is one of 12 tercile cuts, so treat it as a lead.

**Trade size is not a sophistication signal here.**
- Spearman ρ with the composite score is 0.04.
- Kalshi's fractional-contract prints are slightly *more* common in high-score books (ρ = 0.20). That fits
  fractional trading arriving with newer, busier markets, not marking retail-only books.
- Both points agree with Bürgi et al. (largest-trade-size quintile had the largest bias slope).

**Limits.**
- No historical depth exists, so depth is absent from the score.
- News-reaction speed is proxied by daily autocorrelation. True reaction speed needs intraday data around timestamped
  news. The repo's book recorder captures that going forward, but there is no history for resolved political markets.
- A market can sit in different terciles in different weeks, so tercile market counts sum to more than the 3,778
  test markets.
