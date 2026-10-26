# Day 5 — The three ways your backtest lies

1. LOOKAHEAD. You build a panel at time t and join a forward return from
   t + h. Name three fields on a snapshot that, if you take them from the
   t + h row instead of the t row, would leak the answer. For each, say
   how large the fake IC would be.

2. SURVIVORSHIP. Your recorder only has markets that were OPEN when it
   swept. Which markets are systematically missing from your history, and
   which direction does that bias a mean-reversion result?

3. THE LIQUIDITY SCREEN TRAP. You screen on v24 > 1000. v24 is 24-hour
   volume AS OF THE SNAPSHOT. Is that point-in-time? Now suppose you
   screened on "markets that ever exceeded 1000 volume". Explain precisely
   why the second is a disaster and the first is not.

4. RESOLUTION CONTAMINATION. A contract settling inside your forward
   window goes to exactly 0 or 1. That is a real return. Why is it not a
   TRADEABLE return, and what happens to your Sharpe if you leave those
   rows in?

5. Write the one-line test that would catch you if you got question 1
   wrong. Then read `test_planted_lookahead_signal_scores_near_zero` in
   tests/eqr/test_panel.py and see whether you wrote the same test.

## Build

Write `eqr/universe.py` and `eqr/panel.py`. Make these pass:

    python -m pytest tests/eqr/test_panel.py -v

## Defense

1. Delete one line so `build` copies v24 from the forward snapshot. Which
   test catches you? If none does, the canary is too weak. Strengthen it.
2. Your recorder only saw open markets. Name the markets missing from your
   history and the direction of the bias.
3. You screened v24 > 1000. How many names survive at a random asof? If
   it is 30, your cross-section is too thin for an IC and you have to say
   so out loud.
