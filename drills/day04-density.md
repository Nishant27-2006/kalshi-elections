# Day 4 — Breeden-Litzenberger, one derivative cheaper

1. Breeden-Litzenberger: for VANILLA calls, the risk-neutral density is
   d2C/dK2. Write why. Start from C(K) = E[(S-K)+] and differentiate twice
   under the integral.

2. Kalshi lists DIGITALS, not vanillas, with strike_type "greater". So a
   rung quotes P(X >= K). Write the relationship between the rung price and
   the CDF. How many derivatives do you now need to get the density?

3. Therefore: given rungs at K_0 < K_1 < ... < K_n with prices
   p_i = P(X >= K_i), write the probability mass in the bucket
   [K_i, K_{i+1}]. Which strike do you assign that mass to, and what error
   does your choice introduce?

4. Sum of all bucket masses. What should it be? What IS it, for a real
   ladder that does not span the whole real line? agent/ladder.py calls
   this `mass_captured`. Why can you not simply renormalise it to 1 and
   move on?

5. NEGATIVE MASS. Under what quoted condition does your bucket formula
   return a negative number? Is that an arbitrage? State the trade that
   captures it, then apply the fee 0.07*P*(1-P) to BOTH legs and say
   whether it survives. Read AGENT.md:166 before you answer.

6. MEASURED FOR YOU, 2026-08-30, and you must account for it before you
   trust any density you compute. On the live KXETHD-26AUG3101 ladder --
   300 rungs, every strike parsing cleanly and ascending -- the mid-price
   survival curve has ELEVEN upward steps. A survival function cannot
   rise.

   The cause is not missing data. It is WIDE ONE-SIDED BOOKS: rungs
   quoting bid 0 / ask 81, an 81-cent spread whose mid of 0.405 is the
   midpoint of a hole rather than a probability. 49 of the 300 rungs quote
   10c or wider. Restrict to rungs at 2c or tighter and the 11 violations
   collapse to 1.

   Your questions: (a) at what spread does a quote stop being a price, and
   what principle sets that number rather than taste? (b) if you drop the
   wide rungs, what happens to `mass_captured`, and is a density with a
   hole in it better or worse than one built on fictional mids? (c) is the
   single surviving violation real, and does it clear the fee?

   Nothing in the plumbing filters those rungs for you. That decision is
   research, not plumbing. The Density panel reports "Wide books" and both
   violation counts so you can see what your choice costs.

## Build

Write `eqr/density.py`. Make these pass:

    python -m pytest tests/eqr/test_density.py -v

Then open the Density panel. The chart draws itself the moment the module
returns real numbers.

## Defense

1. Run it on a live KXBTCD ladder. What is your `mass`? Now tell me
   whether your `mean` means anything.
2. You found negative mass. Price the trade. Apply the fee to both legs.
   Do you still want it?
3. You used mids. The spread is 2c. Redo it on bids, then on asks. Which
   of your three densities is real?
4. How many of your rungs had an empty book, and what did you do with
   them?
