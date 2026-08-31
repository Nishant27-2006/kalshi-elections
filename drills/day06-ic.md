# Day 6 — Information coefficient, and whether yours is real

1. Define the information coefficient. Spearman or Pearson? Say which you
   are using and why cross-sectional alpha research usually prefers rank
   correlation.

2. The Fundamental Law of Active Management: IR is roughly
   IC * sqrt(breadth). You have a few hundred liquid Kalshi markets and
   you rebalance hourly. Write your breadth per year. Now: what IC do you
   need for an IR of 1.0? Is that number plausible? Be honest.

3. SIGNIFICANCE. You compute an IC at each of N rebalances and average.
   Write the t-stat of the mean IC. If your mean IC is 0.02 with a
   cross-sectional std of 0.15 over 200 rebalances, is it significant?

4. BREADTH IS A LIE when names are correlated. All your KXBTCD rungs are
   driven by one Bitcoin price. What is your EFFECTIVE breadth? How does
   that change your answer to question 2?

5. IC DECAY. Sketch what IC against horizon should look like for (a) a
   microstructure reversal signal and (b) a slow fundamental signal. Which
   one is AGENT.md's momentum result, and which way does it point?

## Build

Write `information_coefficient` and `quantile_spread` in `eqr/evaluate.py`,
then `eqr/signals/alpha_01_reversal.py` and
`eqr/signals/alpha_02_spread.py`. Make these pass:

    python -m pytest tests/eqr/test_evaluate.py tests/eqr/test_alphas.py -v

State each hypothesis in the module docstring BEFORE you code it, and do
not edit it afterwards.

## Defense

1. Your IC is 0.03. Run ic_t_stat. Now tell me your effective breadth given
   every KXBTCD rung tracks one Bitcoin price. Is 0.03 significant against
   THAT?
2. You flipped alpha_02's sign after seeing the IC, did you not. Is that
   one trial or two? Feed the honest number to deflated_sharpe.
3. Your quantile spread is positive but your IC is near zero. What does
   that combination mean, and is it tradeable?
