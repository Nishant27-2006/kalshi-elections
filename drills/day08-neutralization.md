# Day 8 — Neutralization, and admitting how many things you tried

1. Your Kalshi cross-section contains dozens of KXBTCD rungs, dozens of
   KXETHD rungs, and a tail of political markets. If Bitcoin rallies, what
   happens to the IC of ANY signal that happens to load on the BTC group?
   Is that alpha?

2. Write the operation that removes it. Demeaning within series is the
   crude version; regressing the signal on group dummies is the general
   one. Show they are the same when the only factors are group dummies.

3. Why z-score AFTER demeaning and not before?

4. MULTIPLE TESTING. Count honestly: how many signal variants have you run
   since Day 6? Include every sign flip, every parameter, every "let me
   just try". Feed that count to deflated_sharpe. What survives?

5. Write the sentence you would say to a Citadel interviewer who asks "how
   do you know this is not overfit?" It must contain a number.

## Build

Write `eqr/neutralize.py`, then `eqr/signals/alpha_03_neutral.py` reusing
it. Make these pass:

    python -m pytest tests/eqr/test_neutralize.py -v

## Defense

1. Report your IC before and after neutralization. If it collapsed, what
   were you actually measuring for two days?
2. How many variants have you run in total? Not the number you would like.
   The number. Run deflated_sharpe with it.
3. Your group dummies are rank-deficient once you add an intercept. Did
   lstsq warn you? Would normal equations have?
