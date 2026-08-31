# Day 3 — Greeks of a digital, and the two things that will bite you

Depends on Day 1: `fd_delta` and `fd_vega` are finite differences over your
own `eqr/gbm.py`. Finish that first or nothing here can run.

## Drill — on paper, before any code

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

4. THE QUANTISATION PROBLEM, and this is the one worth understanding.
   You will estimate delta by bumping F and re-simulating. The payoff is an
   INDICATOR, so the difference between the two runs is not a smooth
   derivative — it is a COUNT of how many paths crossed the strike inside
   the bump window.

   Work it out. With n = 400,000 paths, what fraction of probability does
   one path represent? The true delta at F = K = 100, sigma = 0.5,
   T = 0.25 is about 0.0158. With a bump of h, the price moves by about
   delta * 2h. So how many paths cross when h = 1e-4? Now state what your
   estimator can possibly return.

   Measured for you on 2026-08-30 at h = 1e-4, n = 400,000:

       K = 90    delta error   -18%
       K = 100   delta error   -21%
       K = 115   delta error  -100%   (zero paths crossed; estimate was 0)

   Now solve for the h that puts roughly 5,000 paths in the window, and
   compare it to the h = 0.5 default in the stub. Then say which way the
   BIAS goes as h grows, and why the variance term blows up faster than
   the bias term when the payoff is discontinuous.

5. COMMON RANDOM NUMBERS. Pass the same seed to both runs so the draws
   cancel. Measured: at h = 0.5, CRN gives 1.3% error against 4.6% with
   independent draws. At h = 0.05, 4.4% against 46%. Explain why the
   benefit grows as h shrinks.

6. Why is the payoff an indicator a problem for PATHWISE differentiation,
   and what does that force you into instead? (Name the two standard
   alternatives to bumping. You do not have to implement them, but you
   should be able to say why a practitioner reaches for them on digitals.)

## Build

Write `eqr/greeks.py`. Three functions, contracts in the docstrings:

    fd_delta(forward, strike, sigma, t_years, h=0.5,  n_paths=400_000, seed=31) -> float
    fd_vega (forward, strike, sigma, t_years, h=0.01, n_paths=400_000, seed=31) -> float
    vega_sign(forward, strike, sigma, t_years) -> int

Run:

    python -m pytest tests/eqr/test_greeks.py -v

Eight tests. `fd_delta` and `fd_vega` must match agent/digital.py's closed
forms to 5% and 8%. `vega_sign` must use the ANALYTIC vega — a finite
difference near the zero crossing is noise around zero and returns the
wrong sign about half the time.

Note the defaults are DIFFERENT for the two functions. A forward of 100 and
a volatility of 0.5 do not take the same bump, and being able to say why is
part of the point.

## What the tests do not prove

`test_common_random_numbers_are_used` only checks that the same seed gives
the same answer twice. Every seeded implementation passes that, including a
wrong one. The tests that actually enforce CRN are the two accuracy tests —
break CRN and they drift out of tolerance. Do not read that green test as
evidence you got this right.

## Defense

1. Break common random numbers on purpose. Show me the delta estimate at
   h = 0.05. Now explain the variance to me in terms of the two runs.
2. You are long a Kalshi YES at 15c and vol doubles. Which way does your
   mark move? Would vanilla-options intuition have told you? Now do it for
   a YES at 85c.
3. fd_vega is allowed 8% and fd_delta only 5%. Why is vega harder here?
4. Push h to 5.0 and report the delta error. It does not blow up the way a
   naive bias argument says it should. Why not?
5. You are hedging a digital that expires in one hour, spot sitting on the
   strike. What is your delta, and what actually happens when you try to
   trade it?
