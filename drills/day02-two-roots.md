# Day 2 — Why a digital has two implied vols

On paper first.

1. Fix F = 100, K = 125, T = 0.25. Compute the digital price N(d2) at
   sigma = 0.1, 0.5, 1.0, 2.0, 5.0. Sketch price against sigma.
   It is NOT monotone. Describe the shape in one sentence.

2. Explain economically why more vol first RAISES an out-of-the-money
   digital and then LOWERS it. What is the limiting price as sigma goes to
   infinity, and why is it that number and not 1?

3. Differentiate the digital price with respect to sigma and show that vega
   has the sign of -d1. Where does vega vanish? Confirm your answer equals
   agent/digital.py's `peak_vol`.

4. Consequence for inversion: given an out-of-the-money digital quote below
   the peak price, how many sigmas reproduce it? Above the peak price?
   Exactly at it?

5. agent/digital.py:178 returns the LOW root and says so. Why is the low
   root the right default for building a surface? What would a surface
   built from the high root look like as strikes cross the forward?

## Build

Write `eqr/surface.py`. Make these pass:

    python -m pytest tests/eqr/test_surface.py -v

## Defense

1. Find a real Kalshi rung whose quote is non-invertible. What does that
   say about what the market believes?
2. You defaulted to the low root. Give a case where that is the wrong
   choice and you would be lying to yourself.
3. Your smile slope is an OLS on four points. What is its standard error?
   Would you trade on it?
