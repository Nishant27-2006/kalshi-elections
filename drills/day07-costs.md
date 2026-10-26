# Day 7 — The arithmetic that kills strategies

1. Kalshi's fee is 0.07 * C * P * (1-P). Where is it maximised in P, and
   what is the maximum in cents per contract? At what two prices does it
   equal 1 cent? agent/risk_unit.py:32 has the answer. Derive it first,
   then check.

2. You cross a 2c spread to enter and 2c to exit. Add the fee on both legs
   at P = 0.5. Write your total round-trip cost in probability points. Now
   write the gross edge you need just to break even.

3. Compare that breakeven to the IC you measured on Day 6. Translate: an
   IC of 0.03 on a cross-section with return std of 4 probability points
   gives what expected edge per name? Does it clear the cost?

4. TURNOVER. If you rebalance hourly you pay that round trip about 6,000
   times a year. Daily, about 250. Write annual return as
   (edge_per_trade - cost) * turnover. Sketch it against turnover. Where is
   the maximum, and why is "trade more" not the answer?

5. Now explain in two sentences, to a PM, why AGENT.md's momentum result
   losing MORE at higher triggers is partly a COST story and not purely a
   signal story.

## Build

Write `eqr/costs.py`. Make these pass:

    python -m pytest tests/eqr/test_costs.py -v

## Defense

1. Take your Day 6 IC. Convert it to an expected edge per name. Run
   net_edge. Is your strategy alive? Say the number out loud.
2. You want to trade 3c longshots because the fee is small there. What is
   the spread as a FRACTION of price at 3c, and does that save you?
3. Give me the turnover that maximises annual return. Now tell me why that
   answer is a trap when your edge estimate has a standard error.
