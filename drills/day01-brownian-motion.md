# Day 1 — Brownian motion, by hand, before you write code

Answer these on paper. Do not open an editor until all five are done.

1. W(t) is standard Brownian motion. Write Var[W(t) - W(s)] for t > s.
   Now write Var[W(t)] itself. Why is it linear in t and not in sqrt(t),
   when the standard deviation goes as sqrt(t)?

2. Quadratic variation. Partition [0, T] into n intervals and form
   S_n = sum (W(t_{i+1}) - W(t_i))^2. What does S_n converge to as
   n goes to infinity? State the answer, then say in one sentence why this
   is the single fact that makes Ito calculus different from ordinary
   calculus.

3. Under geometric Brownian motion with zero drift under the risk-neutral
   measure, S(T) = F * exp(-0.5*sigma^2*T + sigma*W(T)). Take the
   expectation E[S(T)] and show it equals F. Explain what the
   -0.5*sigma^2*T term is doing there and what breaks if you drop it.

4. A digital call pays $1 if S(T) >= K. Show that its risk-neutral price
   with r = 0 is P(S(T) >= K), and reduce that probability to N(d2) with
   d2 = [ln(F/K) - 0.5*sigma^2*T] / (sigma*sqrt(T)).
   NOTE the sign. Compare it to the d2 in agent/digital.py:60 and account
   for any difference before you continue.

5. Monte-Carlo error. If you price this digital by simulating n paths and
   averaging an indicator, the estimator is a sample mean of a Bernoulli
   with parameter p. Write its standard error. How many paths do you need
   for a standard error below 0.001 when p is near 0.5?

Bring your answer to question 5 to the build step. You will check your
simulation against it, and a run whose error does not match your formula is
a bug in the code or a bug in the formula. Find out which.

## Build

Write `eqr/gbm.py`. Make these pass:

    python -m pytest tests/eqr/test_gbm.py -v

The gate is `test_mc_converges_to_closed_form`. Your Monte Carlo must agree
with agent/digital.py's closed-form N(d2) at three strikes, within four
standard errors. Two independent implementations agreeing is the only
evidence that either one is right.

## Defense — be ready for these

1. Your d2 versus agent/digital.py:60. Same number? Prove it.
2. You passed with 500,000 paths. What is your standard error? Is your
   agreement evidence, or is your tolerance just wide?
3. gbm_terminal does not call brownian_paths. Justify that, or admit a bug.
4. Fix the seed and halve n_paths. Does the error rise by sqrt(2)? If not,
   why not?
