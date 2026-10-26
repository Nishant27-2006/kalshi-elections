"""Put options on an exchange that lists no puts.

>>> THE AUTHOR WRITES THE BODIES. <<<

THE PREMISE. Kalshi lists no puts and no calls. Every contract is a binary
with strike_type "greater", so a rung quotes P(X >= K). That is not a dead
end, it is a shortcut, and there are three separate things called a "put"
here. Keep them distinct or you will price the wrong one.

1. THE DIGITAL PUT is already listed. A contract paying $1 if X >= K has a
   NO side paying $1 if X < K. So

       digital put price = 1 - P(X >= K)

   You do not construct this. You buy it. It is the NO leg, and its price
   is the complement of the YES.

2. THE VANILLA PUT is not listed, and you build it from the density.
   A ladder is the risk-neutral CDF, one first difference gives the
   density (Day 4), and any European payoff is then just an expectation:

       P(K) = E[(K - S)+] = sum_i max(K - S_i, 0) * mass_i

   with r = 0, which at Kalshi tenors is right to a rounding error.

3. THE SAME VANILLA PUT, built a second and independent way. A vanilla put
   is the integral of digital puts across strike:

       P(K) = integral_0^K P(S < u) du = integral_0^K (1 - P(X >= u)) du

   This is the gate, and it is the same discipline as Day 1's Monte Carlo
   against the closed form: two constructions that must agree. If they
   disagree, one of your two readings of the ladder is wrong and you find
   out which before you trade either.

PUT-CALL PARITY IS THE INSTRUMENT, NOT THE EXERCISE. With r = 0,

       C(K) - P(K) = F - K

Feed it the density's OWN mean and the error is zero by construction --
that is arithmetic, not evidence. Feed it the PERP forward from
eqr/perps.py and the error becomes a measurement: it is the gap between
what the ladder believes and what the perpetual future believes, in
dollars. That number is a signal. Chasing it is a strategy. Read the
caveat in eqr/perps.py about basis before you believe it.

DO NOT RENORMALISE. Same rule as density.py. A truncated ladder does not
observe the tails, and a put struck below the ladder's lowest rung is
genuinely unobservable. Return what you can compute and let the caller see
`mass`.
"""
from __future__ import annotations


def digital_put(p_ge: float) -> float:
    """Price of the NO leg: P(X < K) = 1 - P(X >= K).

    Raises ValueError if p_ge is outside [0, 1] -- a probability outside
    the unit interval is a data bug upstream and must not be smoothed over
    here.
    """
    raise NotImplementedError("Day 4b: yours to write")


def vanilla_put(pdf: list[tuple[float, float]],
                strike: float) -> float | None:
    """E[(K - S)+] over the observed density. None for an empty pdf.

    pdf is what eqr.density.pdf_from_cdf returns: (midpoint, mass) pairs.
    Undiscounted, r = 0. Negative masses are NOT clipped -- if the ladder
    is arbitrageable your put price should say so rather than hide it.
    """
    raise NotImplementedError("Day 4b: yours to write")


def vanilla_call(pdf: list[tuple[float, float]],
                 strike: float) -> float | None:
    """E[(S - K)+] over the observed density. None for an empty pdf."""
    raise NotImplementedError("Day 4b: yours to write")


def put_from_digitals(strikes: list[float], p_ge: list[float],
                      strike: float) -> float | None:
    """The SAME vanilla put, built by integrating the digital-put strip.

        integral_0^K (1 - P(X >= u)) du

    Trapezoid over consecutive rungs, with the final interval clipped at
    `strike`. Rungs at or above `strike` contribute nothing. None when
    fewer than two rungs sit below `strike`.

    This must agree with `vanilla_put` on the same ladder. Two independent
    constructions agreeing is the only evidence either is right.
    """
    raise NotImplementedError("Day 4b: yours to write")


def parity_error(pdf: list[tuple[float, float]], strike: float,
                 forward: float) -> float | None:
    """(C - P) - (F - K). Zero means the ladder and the forward agree.

    Pass the density's own mean as `forward` and this is zero by
    construction -- useful only as a unit test of your own arithmetic.
    Pass the perp spot from eqr.perps.series_forward and it becomes a real
    measurement of ladder-versus-perp disagreement, in dollars.

    None for an empty pdf.
    """
    raise NotImplementedError("Day 4b: yours to write")
