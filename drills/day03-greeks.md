# Day 3 — Greeks of a digital, and the sign that catches people

1. Write dPrice/dF for the digital analytically. Note it is a PDF, not a
   CDF. Sketch it against F. Why is this a spike rather than a ramp, and
   why does that make a digital brutal to hedge near expiry?

2. Vega. Show d(N(d2))/d(sigma) = -phi(d2) * d1 / sigma. Vega therefore has
   the sign of -d1. Where is d1 = 0? Write that strike in terms of F, sigma
   and T.

3. Sign table. For F = 100, T = 0.25, sigma = 0.5, state the sign of vega
   at K = 80, K = 100, K = 130. Then explain to an interviewer, in two
   sentences and no equations, why buying vol helps you on one of these and
   hurts you on another.

4. Common random numbers. You will estimate delta by bumping F and
   re-simulating. If you draw FRESH randoms for the bumped run, your finite
   difference is (signal + noise)/h with h tiny. Estimate how bad that is.
   What must you do instead?

5. Why is mc_digital_call's payoff an indicator, and what does that do to
   pathwise differentiation? This is why you are bumping rather than
   differentiating the payoff.

## Build

Write `eqr/greeks.py`. Make these pass:

    python -m pytest tests/eqr/test_greeks.py -v

## Defense

1. Break common random numbers on purpose. Show me the delta estimate.
   Now explain the variance.
2. You are long a Kalshi YES at 15c and vol doubles. Which way does your
   mark move? Would vanilla-options intuition have told you?
3. fd_vega matched to 8% but fd_delta to 5%. Why is vega harder?
