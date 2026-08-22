"""A recorded event, reassembled into a strike ladder with a density.

WHAT A LADDER IS. Kalshi's threshold markets list one binary per strike, all
`strike_type: greater`, so leg i quotes P(X >= K_i). Read together they are
not a basket of independent bets -- they are a CUMULATIVE DISTRIBUTION, and
the exchange is publishing it for free.

THE MISTAKE THIS MODULE EXISTS TO PREVENT. A first pass at scanning for
arbitrage applied the PARTITION invariant (sum of legs = 1) to these
cumulative ladders and reported 16 violations across the board. Every one was
false: nested legs like P(X>=68.5k) + P(X>=69.1k) + ... sum far above 1 by
construction, not by mispricing. The applicable invariant depends on the
contract STRUCTURE, which is why nothing downstream of this module is allowed
to see a raw event -- only a ladder that already knows what it is.

STRIKES COME FROM THE TICKER. The book recorder saves quotes, not strikes, so
they are parsed back out of the ticker suffix: `KXBTCD-26AUG2017-T73749.99`
carries strike 73749.99 and expiry 26AUG2017. This keeps recordings small and
means a historical ladder can be rebuilt without a second API call.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

# KXBTCD-26AUG2017-T73749.99  ->  ('26AUG2017', '73749.99')
_TICKER_RE = re.compile(r"^[A-Z0-9]+-([0-9]{2}[A-Z]{3}[0-9]{2}(?:[0-9]{2})?)-T([0-9.]+)$")

_MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
           "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}


def parse_strike(ticker: str) -> float | None:
    """Strike encoded in the ticker suffix, or None if it carries none."""
    m = _TICKER_RE.match(ticker or "")
    if not m:
        return None
    try:
        return float(m.group(2))
    except ValueError:
        return None


def parse_expiry_ts(ticker: str) -> float | None:
    """Expiry as a UTC epoch, parsed from the event segment.

    `26AUG2017` is 2026-08-20 at 17:00 UTC: two digits of year, three of
    month, two of day, then an optional two-digit hour. A date with no hour
    is treated as end of day, which is how Kalshi's daily events settle.
    """
    m = _TICKER_RE.match(ticker or "")
    if not m:
        return None
    s = m.group(1)
    try:
        year = 2000 + int(s[0:2])
        month = _MONTHS[s[2:5]]
        day = int(s[5:7])
        hour = int(s[7:9]) if len(s) >= 9 else 23
    except (KeyError, ValueError):
        return None
    try:
        return datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


@dataclass(frozen=True)
class Rung:
    strike: float
    bid_c: float
    ask_c: float

    @property
    def mid(self) -> float:
        """Mid price in DOLLARS -- i.e. the implied P(X >= strike)."""
        return (self.bid_c + self.ask_c) / 200.0

    @property
    def spread_c(self) -> float:
        return self.ask_c - self.bid_c


@dataclass
class Ladder:
    """One event at one instant, sorted by strike ascending."""
    event: str
    ts: float
    expiry_ts: float | None
    rungs: list[Rung] = field(default_factory=list)

    @property
    def strikes(self) -> list[float]:
        return [r.strike for r in self.rungs]

    @property
    def mids(self) -> list[float]:
        return [r.mid for r in self.rungs]

    @property
    def t_years(self) -> float | None:
        if self.expiry_ts is None:
            return None
        return max(0.0, (self.expiry_ts - self.ts) / (365.0 * 24 * 3600))

    def monotonicity_violations(self) -> list[tuple[int, float, float]]:
        """Indices where P(X>=K) RISES with strike, which is impossible.

        Uses MIDS, so this reports a modelling inconsistency. Whether it is
        also tradeable is a separate question answered on bid/ask by the
        arbitrage scanner, because crossing the book costs the spread.
        """
        out = []
        for i, (a, b) in enumerate(zip(self.mids, self.mids[1:])):
            if b > a:
                out.append((i, a, b))
        return out

    def density(self) -> list[tuple[float, float]]:
        """(strike_midpoint, probability mass) between adjacent strikes.

        For a cumulative ladder this is one difference, not the two that
        Breeden-Litzenberger needs for vanilla calls -- the exchange has
        already done the first derivative by listing digitals.

            p_i = P(X >= K_i) - P(X >= K_i+1)

        Masses may come out slightly negative where quotes are inconsistent.
        They are NOT clipped here: a negative mass is evidence about the
        book, and hiding it would remove the very signal the scanner looks
        for.
        """
        out = []
        for lo, hi in zip(self.rungs, self.rungs[1:]):
            out.append(((lo.strike + hi.strike) / 2.0, lo.mid - hi.mid))
        return out

    def forward(self) -> float | None:
        """Risk-neutral mean E[X], recovered from the ladder's own density.

        This is the F every Black-Scholes call downstream uses, because
        Kalshi publishes no spot. Two honest caveats:

        - It is CIRCULAR in a limited sense: the forward comes from the same
          quotes whose implied vol it is then used to compute. That makes
          implied vol here a statement about the ladder's INTERNAL shape, not
          about a gap between Kalshi and a spot exchange.
        - It is TRUNCATED. Probability below the lowest strike and above the
          highest is unobserved, so a ladder whose interior does not span the
          distribution understates the tails. `mass_captured` reports how much
          of the distribution the ladder actually covers so a caller can
          refuse the ones that do not.
        """
        d = self.density()
        if not d:
            return None
        total = sum(p for _, p in d)
        if total <= 0:
            return None
        return sum(k * p for k, p in d) / total

    def mass_captured(self) -> float:
        """Probability mass between the lowest and highest strike.

        1.0 means the ladder spans the whole distribution. A ladder capturing
        0.2 is a narrow window on a wide distribution and its moments are
        meaningless -- the forward would be pinned inside the window whatever
        the market believes.
        """
        if len(self.rungs) < 2:
            return 0.0
        return max(0.0, min(1.0, self.rungs[0].mid - self.rungs[-1].mid))

    def variance(self) -> float | None:
        f = self.forward()
        d = self.density()
        if f is None or not d:
            return None
        total = sum(p for _, p in d)
        if total <= 0:
            return None
        return sum(p * (k - f) ** 2 for k, p in d) / total

    def stdev(self) -> float | None:
        v = self.variance()
        return None if v is None or v < 0 else math.sqrt(v)

    def skew(self) -> float | None:
        f, sd, d = self.forward(), self.stdev(), self.density()
        if f is None or not sd or not d:
            return None
        total = sum(p for _, p in d)
        if total <= 0:
            return None
        return sum(p * ((k - f) / sd) ** 3 for k, p in d) / total

    def kurtosis(self) -> float | None:
        """EXCESS kurtosis: 0 for a normal, positive for fat tails."""
        f, sd, d = self.forward(), self.stdev(), self.density()
        if f is None or not sd or not d:
            return None
        total = sum(p for _, p in d)
        if total <= 0:
            return None
        return sum(p * ((k - f) / sd) ** 4 for k, p in d) / total - 3.0


def ladders_from_rows(rows: list[dict], min_rungs: int = 5
                      ) -> dict[tuple[str, float], Ladder]:
    """Recorded snapshot rows -> {(event, ts): Ladder}, strikes ascending.

    Rows with no strike in the ticker are skipped: they are not ladder legs.
    """
    grouped: dict[tuple[str, float], list[Rung]] = {}
    expiries: dict[str, float | None] = {}
    for r in rows:
        ticker = r.get("ticker") or ""
        strike = parse_strike(ticker)
        if strike is None:
            continue
        bid, ask = r.get("yes_bid_c"), r.get("yes_ask_c")
        if bid is None or ask is None:
            continue
        event = r.get("event_ticker") or ticker.rsplit("-", 1)[0]
        key = (event, r["ts"])
        grouped.setdefault(key, []).append(Rung(strike, float(bid), float(ask)))
        if event not in expiries:
            expiries[event] = parse_expiry_ts(ticker)

    out: dict[tuple[str, float], Ladder] = {}
    for (event, ts), rungs in grouped.items():
        if len(rungs) < min_rungs:
            continue
        rungs.sort(key=lambda r: r.strike)
        out[(event, ts)] = Ladder(event=event, ts=ts,
                                  expiry_ts=expiries.get(event), rungs=rungs)
    return out
