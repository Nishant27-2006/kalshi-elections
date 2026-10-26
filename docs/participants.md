# Participant sophistication — submodels and where the edge sits

Generated 2026-10-09 20:16 UTC by `python -m forecast.participants_report`. Same split as docs/backtests.md (cutoff 2026-06-19); cut points and z-scores fit on TRAIN.

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
| low | 5787 | 0.12128 | 0.00043 |
| mid | 7960 | 0.1104 | 8e-05 |
| high | 5224 | 0.08901 | 0.00062 |

## 2. Held-out test: B0 (old-plan estimator) by tercile

| submodel | tercile | markets | events | Brier mkt | Brier B0 | skill | ΔBrier CI95 | trades | P&L $ | P&L/trade | P&L/trade CI95 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| composite | low | 1913 | 692 | 0.09847 | 0.09724 | +0.0125 | [-0.0021, -0.00031] | 10 | 0.859 | 0.0859 | [-0.2373, 0.3132] |
| composite | mid | 2809 | 928 | 0.09163 | 0.09063 | +0.0110 | [-0.00158, -0.00041] | 41 | 1.253 | 0.0306 | [-0.1352, 0.1827] |
| composite | high | 1858 | 778 | 0.08526 | 0.08493 | +0.0039 | [-0.00105, 0.00037] | 39 | 1.009 | 0.0259 | [-0.1324, 0.2058] |
| liquidity | low | 1789 | 623 | 0.11056 | 0.10922 | +0.0121 | [-0.00235, -0.00028] | 15 | 0.566 | 0.0377 | [-0.2752, 0.2492] |
| liquidity | mid | 2602 | 869 | 0.08582 | 0.08507 | +0.0088 | [-0.00138, -0.00019] | 36 | -1.121 | -0.0311 | [-0.1952, 0.1436] |
| liquidity | high | 2012 | 761 | 0.08202 | 0.08132 | +0.0085 | [-0.00142, -0.00012] | 39 | 3.675 | 0.0942 | [-0.0599, 0.2747] |
| efficiency | low | 2074 | 810 | 0.087 | 0.08592 | +0.0125 | [-0.00178, -0.00039] | 14 | 2.485 | 0.1775 | [0.0155, 0.3465] |
| efficiency | mid | 3226 | 933 | 0.10078 | 0.09972 | +0.0106 | [-0.00177, -0.00037] | 48 | 0.58 | 0.0121 | [-0.1475, 0.1849] |
| efficiency | high | 1909 | 773 | 0.08714 | 0.08703 | +0.0013 | [-0.00083, 0.00069] | 28 | 0.056 | 0.002 | [-0.1764, 0.2131] |
| activity | low | 2139 | 673 | 0.09784 | 0.09671 | +0.0116 | [-0.00189, -0.00032] | 21 | 3.864 | 0.184 | [-0.0302, 0.3428] |
| activity | mid | 2713 | 903 | 0.09503 | 0.09478 | +0.0027 | [-0.00088, 0.00034] | 42 | -2.703 | -0.0644 | [-0.2194, 0.0972] |
| activity | high | 1485 | 656 | 0.09703 | 0.09615 | +0.0090 | [-0.00171, -0.00016] | 27 | 1.96 | 0.0726 | [-0.1122, 0.2529] |

## 3. Trade sizes (271 random test markets, prints before the first test snapshot)

- median print size: median across markets 17.00 contracts
- share of fractional (<1 contract) prints: median 0.00
- share of >=100-contract prints: median 0.18

Spearman correlation with the composite score:

| | composite | median_size | frac_share | big_share |
|---|---|---|---|---|
| composite | 1.0 | 0.03 | 0.31 | 0.12 |
| median_size | 0.03 | 1.0 | -0.14 | 0.8 |
| frac_share | 0.31 | -0.14 | 1.0 | -0.01 |
| big_share | 0.12 | 0.8 | -0.01 | 1.0 |

## What this says (full data, 19,488 markets; first-pass 18,290-market version kept in git history)

**The sophistication score still doesn't validate on train.** Recalibration headroom by composite tercile is 0.0004
(low), 0.0001 (mid) and 0.0006 (high), not decreasing with sophistication. The low tercile's higher raw Brier
(0.121 vs 0.089) reflects prices nearer 50c, not worse calibration.

**Forecasting skill does lean toward less sophisticated books.** B0's Brier skill by composite tercile is
+1.25% (low), +1.10% (mid), +0.39% (high). Low and mid have CIs excluding zero; high includes zero.
- The gradient is clearest on the **efficiency** submodel: +1.25% where moves reverse, +1.06% mid, +0.13% where moves
  stick.
- In the 18,290-market first pass the composite gradient was flatter (+0.96 / +1.17 / +0.63). Treat the ordering as
  suggestive, not settled.

**Money mostly does not follow.**
- Of 12 tercile cuts, one P&L CI clears zero: **low efficiency, +17.8c/trade on 14 trades, CI [+1.6c, +34.7c]**.
  With 12 cuts tested, one false positive at 95% would not be surprising. It is a lead to re-test on post-2026-10-09
  settlements, not an edge.
- The composite low tercile earns +8.6c/trade on 10 trades, CI [−23.7c, +31.3c].

**Trade size is not a sophistication signal.** Spearman ρ with the composite is 0.03. Fractional-contract prints are
*more* common in high-score books (ρ = 0.31), consistent with Bürgi et al.

**Limits.**
- No historical depth exists, so depth is absent from the score.
- Reaction speed is proxied by daily autocorrelation; true reaction speed needs intraday data.
- A market can sit in different terciles in different weeks, so tercile counts sum to more than the 4,231 test
  markets.
