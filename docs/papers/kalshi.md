# Makers and Takers: The Economics of the Kalshi Prediction Market

## 1. Citation

Constantin Bürgi, Wanying Deng, Karl Whelan (University College Dublin). "Makers and Takers: The Economics of the Kalshi Prediction Market." Working paper, January 2026. No arXiv id, journal or venue is printed in the PDF. JEL: G14, G23, G40. The PDF has 44 pages, and every page was read for this summary.

## 2. Summary

The authors pull transaction-level data from Kalshi's API covering 2021 through April 2025. This is the first systematic study of Kalshi pricing, and the dataset has 46,282 Yes contracts across 12,403 events. Prices are informative and get more accurate as markets near close. They also show a clear favorite-longshot bias (FLB): cheap contracts win much less often than their price implies, and expensive contracts win slightly more often. The bias holds in every contract type, category, volume quintile, trade-size quintile, horizon and year. It may be getting weaker in 2025. Kalshi's API labels which side of each trade was the Maker and which was the Taker. Makers earn much more than Takers (-9.64% vs -31.46%), but both groups show the FLB. A quote-driven matching model fits the data. In it, agents with heterogeneous beliefs sort into making or taking, and the model needs a small tendency to overweight small probabilities (beta about 0.09). Heterogeneous beliefs alone cannot reproduce the pattern.

## 3. Data and method

- Source: the Kalshi API, pulled with Python. It covers transaction-level data from Kalshi's 2021 start through April 2025 (p.9). The cutoff is April 2025 because Kalshi started charging Makers fees after that (p.6).
- Filters (p.9): final total volume of at least $1,000; final bid-ask spread of 20c or less; hourly-reset markets (crypto and index) excluded, so every market was open at least 24 hours. Sixty-three Yes contracts whose transaction data did not match Kalshi's reported final prices and volumes were dropped (p.9, fn 2).
- Sample: 46,282 Yes contracts in 12,403 events. Prices were sampled at close and at 24-hour intervals back to 10 days before close, using the last trade before the same clock time each day (p.9, fn 3). That gives 156,986 Yes prices, an average of 3.5 per contract, or 313,972 prices once the No side is added (p.9).
- Horizon availability (p.11, Table 1): 19,338 contracts have a closing-day price only, 12,861 have closing day plus the day before, and 6,754 have the full 10 days.
- Price distribution (p.12, Table 2): 33.8% of observations are in 1-10c and 33.8% are in 90-99c. Only 8,351 fall in 50-59c.
- Volume (p.10; p.13, Table 3): median staked per contract is $8,982. Decile 1 averages $1,199, decile 10 averages $526,245, and the overall mean is $61,977. Mean transaction size is $100 and the median is $35. On average 3.7 Yes contracts trade per event on the final day (p.10).
- Categories (p.24, Table 8): Financials, Climate & Weather, Crypto, Politics (26,819 obs), Entertainment, Economics and Other. Sports was added in January 2025, and the results hold when sports or post-December-2024 data are excluded (p.9).
- Methods: calibration curve of win rate vs price (Fig 3); MAE by horizon (Fig 4); post-fee return by 10c bin (Fig 5); Mincer-Zarnowitz regression Y - P = alpha + psi*P, with the joint F-test alpha = psi = 0, run on Yes contracts only and clustered by event and contract (pp.18-19); split by Maker and Taker (Section 4); a structural model calibrated by grid search (Section 5).

## 4. Key quantitative findings

- Pre-fee average return across all contracts is -20% (p.17). The abstract and p.3 call this "about minus 20%".
- Contracts priced 10c or less lose more than 60% on average after fees (p.3, p.17). Post-fee returns are small and positive above 50c, and statistically significant above 70c (p.17, Fig 5).
- Worked examples (p.17): a 5c contract that wins 3% of the time returns -40% pre-fee. A 95c contract that wins 98% of the time returns +3.1% pre-fee.
- Mincer-Zarnowitz, full sample (p.20, Table 4): psi = 0.034 (SE 0.005), constant = -1.736 (0.153), N = 156,986, F p = 0.000. Single-contract events have psi = 0.045 with a constant of -0.595 that is not significant. Mutually exclusive numerical events have psi = 0.014.
- Units: the coefficients appear to be in cents. If so, the zero-profit crossing for the full sample is about 1.736/0.034 ≈ 51c. This is our own arithmetic, not a number the paper reports.
- By horizon (p.22, Table 5): the null is rejected at every horizon from 0 to 10 days. At day 0, psi = 0.036 and the constant is -2.025 (N = 46,282). At day 1, psi = 0.017.
- MAE falls smoothly as close approaches, then drops steeply on the final day: from roughly 11-14 one day out to roughly 6 at close (p.16, Fig 4; values read off the chart, so approximate).
- Volume quintiles (p.23, Table 6): psi goes 0.045 / 0.039 / 0.032 / 0.036 / 0.032. The lowest-volume quintile has the largest bias, and above it volume brings no clear improvement (p.21).
- Trade-size quintiles (p.23, Table 7): psi goes 0.036 / 0.033 / 0.038 / 0.034 / 0.043. The largest mean trade size shows the largest bias, so bigger trades are not more accurate (p.21).
- Category (p.24, Table 8): Politics psi = 0.022 (SE 0.021, not significant) with constant -1.912 (SE 0.340, significant at 1%). The joint F-test still rejects (p = 0.000). Entertainment psi = 0.020 (not significant), Crypto 0.058, Other 0.053, Financials 0.032, Climate/Weather 0.031, Economics 0.034. The paper says psi is "smaller for politics and entertainment" (p.21).
- Year (p.25, Table 9): psi is 0.041 in 2021, 0.023 in 2022, 0.036 in 2023, 0.048 in 2024 and 0.021 in 2025 (significant only at 10%). The authors read this as some weakening in 2025 (p.21).
- Model calibration (p.36): beta is tightly identified, between 0.06 and 0.12 across the top 5% of fits. The preferred values are beta = 0.09, theta (match rate) = 0.60 and sigma (belief dispersion) = 0.107. Theta and sigma correlate at 0.80, so they are not separately identified.

## 5. Microstructure: fees, spreads, FLB, makers and takers

- Fees (p.6, p.17): Takers paid $0.07 × P × (1 - P) per contract, with the total rounded up to the nearest cent, and Makers paid nothing during the sample. On a 100-contract order at 50c the fee is 1.77% of price, compared with 1.75% without rounding. Post-fee Taker return is R = (Y - P - C)/(P + C) (p.17, eq 2). Relative to price, the fee costs most on cheap contracts (p.36).
- Spreads: the paper drops markets whose final spread exceeds 20c. In the model, low match probability produces wider spreads (thin equilibrium), and the fixed disagreement width makes spreads a larger share of price for cheap contracts (p.34, p.36). Spreads themselves get no empirical analysis.
- Maker share of buying rises with price (p.26, Table 10). Makers do 43.5% of the buying in 1-10c and 56.5% in 90-99c, so cheap longshots are mostly bought by Takers.
- Returns (p.27): Makers average -9.64% and Takers -31.46%, and the F-test rejects equality. Makers buying at 50c or above earn +2.6% (p.27, p.40), with a standard deviation of 33% (p.40). Read off the charts (approximate), the 1-10c bin returns about -0.73 for Takers and -0.35 for Makers (Figs 6 and 9, pp.28, 38).
- Closing-day effect (p.27, Figs 7 and 8): at day 0, Maker losses on cheap contracts look like Taker losses. Makers lose money on 10c-and-under contracts at a statistically significant level on 5 of the 6 horizons shown. The authors connect this to Page's "Yogi Berra" effect, where longshots are overpriced late in the market.

## 6. Implications for our system

**Backtests to run, each one testable:**
1. Fit a calibration-by-price-bin correction before adding any knowledge-file signal. Compare (a) the raw market price, (b) the price after a Mincer-Zarnowitz or logistic recalibration fit on earlier data, and (c) our model. Score them with Brier and log loss, plus post-fee P&L. The model has to beat (b), not only (a).
2. Run the FLB test on politics alone. In the paper the politics slope is not significant (p.24), so check whether our political sample has a significant psi or only a level shift in the constant.
3. Score each horizon separately: day 0, day 1, days 2-5 and days 6-10, using a daily snapshot rule like the paper's (p.9, fn 3). Accuracy jumps on the final day (Fig 4), so model edge should concentrate at longer horizons.
4. Simulate each trade both ways. As a Taker, pay the ceiling-rounded fee 0.07·P(1-P)·n plus half the spread. As a Maker, earn no fee before April 2025, apply the actual Maker fee after that date, and use a fill probability somewhere in 0.4-0.8 (the paper's theta = 0.60 is a calibration choice, not a measured rate).
5. Bucket results by price: 1-10c, 11-20c, 20-50c, 50-90c and 90-99c. Check that apparent edge on "No" longshots, which means selling cheap Yes, survives fees and remains after 2025.
6. Run the regression by year. If the 2025 weakening (p.25) continues into 2026, a fixed FLB prior will overcorrect.
7. Repeat everything with 20c and 5c spread filters to see whether results depend on the liquidity screen.

**Features for the participant-sophistication model:** the Maker share of volume for each contract and price bin (taken from the API side flag, so no Lee-Ready inference is needed), log total volume (the bias is largest in the lowest volume quintile), mean and median trade size, quoted spread and spread as a fraction of price, top-of-book depth, days to close, contract structure (single, non-exclusive, mutually exclusive numerical, other), category and calendar year. Two cautions from the paper: larger trades did not mean better prices (p.21), and above the lowest quintile, volume does not reduce the bias. The paper never measures news-reaction speed, so that feature has no support here.

**Pitfalls:**
- Lookahead: use only the last trade before a fixed cutoff time (fn 3). Final volume and final spread are not known until the market closes, so filtering a backtest on them leaks future information. Use volume and spread as of the snapshot.
- Survivorship and selection: the sample includes only contracts with at least $1,000 final volume and spreads of 20c or less, so illiquid political markets are underrepresented.
- Correlated outcomes: in mutually exclusive events, at most one contract wins, and repeated daily snapshots of one contract are positively correlated. Cluster by event and by contract, and do not double-count Yes/No mirrors (p.19).
- Fee regime: the Maker fee arrived after April 2025, and Taker fee totals round up. Apply the schedule that was in force at each trade's timestamp.
- The last traded price is not the price you can trade at. It may sit on the bid or the ask (p.6), so value at the quoted side.

## 7. Limitations and caveats

- This is a working paper with no peer review shown in the PDF. Many numbers come from figures and are approximate.
- Data stop in April 2025, before the Maker-fee regime and most sports volume. Political results cover the 2024 cycle and may not generalize.
- Only traded prices are used. There is no order-book depth, spread history or account-level data. "Sophistication" here means the Maker/Taker role, not identity.
- Snapshots are daily only, and fewer than 15% of contracts have the full 10-day history (6,754 of 46,282).
- The model is a one-shot game with exogenous match rates. It has multiple equilibria and weak identification of theta and sigma (pp.34, 36).
- Politics' own slope is imprecise (SE 0.021), so the FLB magnitude for political markets is uncertain.
- The authors suggest the bias may fade now that it is published (p.41).
