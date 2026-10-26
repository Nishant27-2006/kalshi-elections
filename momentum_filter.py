"""
Pure filtering/ranking helpers for the momentum scanner.

Split out of find_momentum.py so the parts that decide WHAT gets scanned and
HOW movers are ranked can be tested without a network round trip. The scanner
itself stays a thin shell around these.

Two problems these solve:

1. No date filter. The scan ranked absolute price delta across every open
   market in 575 series, so a Florida election-day question competed with
   Likud leadership and Alaska/Wyoming contracts resolving years out. A mover
   is only interesting if it resolves inside the window you are trading.

2. Absolute delta as the ranking key. On a thin book an 18c move is inventory
   clearing, not conviction -- see the Askar case (0.10 -> 0.28 on 7,250
   contracts while the field's ask-sum decayed 117 -> 104). Ranking by raw
   delta puts exactly that at the top.
"""

from __future__ import annotations

import math
from collections import Counter
import re
from datetime import datetime, timedelta, timezone


def parse_ts(ts: str | None) -> datetime | None:
    """Kalshi ISO timestamp -> aware datetime. Unparseable -> None."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_day(s: str | None) -> datetime | None:
    """A --close-before/--election-day argument -> aware midnight UTC."""
    if not s:
        return None
    dt = parse_ts(s)
    if dt is None:
        raise ValueError(f"could not parse date {s!r}; use YYYY-MM-DD")
    return dt


def window_for_election_day(day: str, days_either_side: int = 1
                            ) -> tuple[datetime, datetime]:
    """Inclusive close-time window around an election day.

    Election-night contracts do not all close at the same instant, so a bare
    equality test on the date drops half of them.
    """
    d = parse_day(day)
    start = d - timedelta(days=days_either_side)
    end = d + timedelta(days=days_either_side + 1)   # through end of that day
    return start, end


def closes_within(market: dict, after: datetime | None,
                  before: datetime | None) -> bool:
    """Does this market's close_time fall inside [after, before)?

    A market with no parseable close_time is EXCLUDED whenever a window is
    requested. Including it would quietly reintroduce the noise the filter
    exists to remove.
    """
    if after is None and before is None:
        return True
    close = parse_ts(market.get("close_time"))
    if close is None:
        return False
    if after is not None and close < after:
        return False
    if before is not None and close >= before:
        return False
    return True


def series_matches(series_ticker: str, patterns: list[str] | None) -> bool:
    """Case-insensitive substring OR regex match against a series ticker."""
    if not patterns:
        return True
    t = (series_ticker or "").upper()
    for p in patterns:
        pu = p.upper()
        if pu in t:
            return True
        try:
            if re.search(pu, t):
                return True
        except re.error:
            pass
    return False


def _ask_cents(record: dict) -> float | None:
    """Ask price in CENTS from either shape of record.

    `find_momentum.scan_series` reshapes to integer-cent `yes_ask`, but the raw
    /markets payload only ships `yes_ask_dollars` as a string. Reading just
    `yes_ask` made ask_sums_by_event return {} on raw API records -- silently,
    with no error, so a caller saw "no events" rather than "wrong field".
    """
    v = record.get("yes_ask")
    if v is not None:
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    d = record.get("yes_ask_dollars")
    if d is None:
        return None
    try:
        return float(d) * 100.0
    except (TypeError, ValueError):
        return None


def event_ticker(market: "str | dict") -> str:
    """Market -> event ticker.

    Pass the market DICT wherever possible: Kalshi ships an `event_ticker`
    field and it is authoritative. The string heuristic below is a fallback
    and cannot be made correct in general, because the number of hyphens is
    not fixed at either end:

        KXFLPRIMARY-21D26-BTAY            -> KXFLPRIMARY-21D26   (2-segment series)
        KXFLRGOVEXACT-26AUG18-DON-COL-REN -> KXFLRGOVEXACT-26AUG18 (hyphenated OUTCOME)
        KXMLBWINS-BOS-26-T95              -> KXMLBWINS-BOS-26    (hyphenated SERIES)

    The first two cases are handled by taking two segments; the third breaks it,
    because the series ticker itself contains a hyphen (WINS-BOS). Grouping
    KXMLBWINS-BOS-26-T95 under "KXMLBWINS-BOS" would merge every season's
    Boston wins event into one bogus field.

    Fallback rule: take segments up to and including the first one that looks
    like a PERIOD code (starts with two digits, e.g. "26", "26AUG18",
    "26AUG181910SDNYM"). That is what actually delimits series from outcome.
    """
    if isinstance(market, dict):
        ev = market.get("event_ticker")
        if ev:
            return str(ev)
        market = market.get("ticker") or ""
    parts = (market or "").split("-")
    if len(parts) < 2:
        return market or ""
    for i, seg in enumerate(parts[1:], start=1):
        if len(seg) >= 2 and seg[:2].isdigit():
            # A date-looking segment is the PERIOD when something follows it,
            # and the OUTCOME when it is last. Corporate-event markets ladder
            # by date, so KXIPOANTHROPIC-DATE-26SEP01 has a date as its
            # outcome: taking parts[:i+1] made every leg its own event and
            # turned an 8-leg ladder into 8 standalone binaries.
            #   KXBTCD-26AUG1815-T72299.99   -> KXBTCD-26AUG1815      (period)
            #   KXIPOANTHROPIC-DATE-26SEP01  -> KXIPOANTHROPIC-DATE   (outcome)
            #   KXAAPLCEOCHANGE-26           -> KXAAPLCEOCHANGE       (outcome)
            last = (i == len(parts) - 1)
            keep = i if last else i + 1
            return "-".join(parts[:keep]) if keep else parts[0]
    return "-".join(parts[:2])


def ask_sum_cents(records: list[dict]) -> float | None:
    """Sum of YES asks across ONE event's legs.

    A mutually-exclusive field should sum to ~100 plus the vig. A sum well
    above 100 that is decaying toward it means the longshots are being marked
    down -- the field is collapsing into coherence. Movement produced by that
    decay is repricing, not news.

    Callers must group by event first. Summing a whole SERIES is meaningless:
    KXFLPRIMARY spans nine separate district races, and summing all 21 of its
    legs produced 922c, which reads as a colossal longshot premium and is
    actually nine coherent fields added together.
    """
    asks = [a for a in (_ask_cents(r) for r in records) if a is not None]
    return round(sum(asks), 2) if asks else None


_MONTHS = {m: i for i, m in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), start=1)}


def _strike_value(body: str) -> float | None:
    """Strike suffix -> an orderable number, or None if it is not a strike.

    Two spellings carry an ordering:
      numeric   "3.4", "95", "6750000"      -> the number
      date      "26SEP01", "27JAN01"        -> YYMMDD as an integer
    Corporate-event markets ladder by DATE ("will X happen before D"), which is
    just as cumulative as a price ladder -- later dates are weakly more likely.
    Without this the shape heuristic returned False on every date ladder and
    the classification depended entirely on the exchange flag being present.
    """
    if not body:
        return None
    try:
        return float(body)
    except ValueError:
        pass
    if len(body) == 7 and body[:2].isdigit() and body[5:].isdigit():
        mon = _MONTHS.get(body[2:5].upper())
        if mon:
            return float(f"{body[:2]}{mon:02d}{body[5:]}")
    return None


def _bid_cents(record: dict) -> float | None:
    """Bid price in CENTS from either record shape (see _ask_cents)."""
    v = record.get("yes_bid")
    if v is not None:
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    d = record.get("yes_bid_dollars")
    if d is None:
        return None
    try:
        return float(d) * 100.0
    except (TypeError, ValueError):
        return None


def premium_is_readable(records: list[dict], ask_sum: float) -> tuple[bool, str]:
    """Can this event's ask-sum be read as 100 + vig?

    Only for a LIVE, TWO-SIDED book. Two ways it cannot be, both of which
    previously produced confident three-digit "premiums":

      settled  Kalshi quotes a finalized leg at ask 1.0000 regardless of
               result, so the ask-sum degenerates to the leg count.
      quoteless every leg bids ~0 while asks stay wide -- the sum measures how
               dormant the book is, not what it costs to cross.

    Returns (readable, note). The structure label is unaffected; only the
    derived premium is withheld.
    """
    if any(str(r.get("status", "")).lower() in _SETTLED_STATUSES
           for r in records):
        return False, SETTLED_BOOK_NOTE

    bids = [b for b in (_bid_cents(r) for r in records) if b is not None]
    # `<=`, not `<`. A placeholder golf book -- KXLPGAR3LEAD-CPKWO26, 158 legs
    # asking 71-74c with only four legs bid and all four at EXACTLY 5.0c --
    # sat one tick outside a strict comparison and was published as a
    # +11,276c "premium". The threshold is meant to be inclusive: a book whose
    # best bid IS 5c is no more two-sided than one bidding 4.99c.
    #
    # Breadth would be the wrong test here. KXNCAAFAPRANK-26W12R1 is a GENUINE
    # partition with only one of thirteen legs bid -- but that leg bids 96c.
    # It is the LEVEL of the best bid that separates a real field from a
    # placeholder, not how many legs carry one.
    if bids and max(bids) <= _MIN_LIVE_BID_CENTS and ask_sum > _VIG_BAND[1]:
        return False, QUOTELESS_BOOK_NOTE
    return True, ""


_RANK_PHRASE = re.compile(r"\btop\s+(\d{1,3})\b", re.I)


def is_two_sided_handicap(records: list[dict]) -> bool:
    """Two OPPOSED cumulative ladders sharing one event, not one ladder.

    A handicap book lists both teams at the same margins: "Houston wins by
    more than 3.5" and "Las Vegas wins by more than 3.5" are separate legs of
    one event. Kalshi stores the magnitude UNSIGNED in `floor_strike` and puts
    the direction in `custom_strike`/the ticker, so the two sides collide at
    every rung.

    That breaks both existing labels:
      threshold_ladder   says the legs are one cumulative distribution -- but
                         HOU-over-3.5 and LV-over-3.5 cannot both win
      independent_basket says "read each leg on its own" -- but rungs on the
                         SAME team are strictly nested and very much not
                         independent

    DETECTION IS EXACT, not a heuristic: a one-sided ladder cannot repeat a
    strike, so a duplicated `floor_strike` within one event means two sides.
    Measured live 2026-08-19 -- KXNFL1QSPREAD 5 duplicated strikes of 10,
    KXNFLSPREAD 9 of 27, while KXNFL1QTOTAL, KXCPIYOY, KXNCAAFWINS and
    KXMLBTOTAL all have ZERO.
    """
    strikes = [_numeric(r.get("floor_strike")) for r in records]
    strikes = [v for v in strikes if v is not None]
    if len(strikes) < 2:
        return False        # must be a strike-based book at all
    # NOTE the floor is 2, not 3. First-half soccer spreads list ONE margin per
    # team (KXLALIGA1HSPREAD, KXUCL1HSPREAD, KXMLS1HSPREAD and 9 more) and are
    # two-sided with only two legs. A 2-leg MONEYLINE is not caught because it
    # carries no floor_strike at all, and a 2-rung one-sided ladder is not
    # caught because it has only one side.

    # SIGNAL 1 -- COUNT THE SIDES. Each leg's ticker suffix is a subject token
    # plus a rung index (SKC2/SKC3/ATL2/ATL3), so stripping the digits and
    # counting distinct prefixes counts the teams. A handicap has EXACTLY two.
    # This is the primary test because it also catches ASYMMETRIC books, where
    # the two sides are quoted at different margins and no strike repeats at
    # all -- KXATPGSPREAD lists Tiafoe at -1.5 against Auger-Aliassime at -2.5
    # and -5.5.
    sides = {re.sub(r"[\d.]+$", "", (r.get("ticker") or "").rsplit("-", 1)[-1]).upper()
             for r in records}
    if len(sides) == 2:
        return True

    # SIGNAL 2 -- SYMMETRIC MARGINS. Kept as a fallback in case a ticker
    # grammar does not carry a subject token: a one-sided ladder can never
    # repeat a strike, so several margins each appearing EXACTLY twice means
    # two sides. Multiplicity must be exactly 2 -- KXRAIN lists 20 cities all
    # at floor_strike 0.0, which is ONE strike twenty times over.
    counts = Counter(strikes)
    if len(counts) < 3 or max(counts.values()) != 2:
        return False
    return sum(1 for n in counts.values() if n == 2) >= 2


def stated_cardinality(records: list[dict]) -> int | None:
    """The K a rank-constrained basket NAMES in its own rules, or None.

    The numeric bracket alone is NOT evidence of a constraint. On a genuine
    independent basket the ask-sum IS the expected number of legs that will
    resolve yes, so it always brackets SOME integer -- KXMLBHR (35 players,
    "records 1+ home runs") bracketed 2, and KXNFLSEASONPASSYDS (30 QBs,
    "records 4000+ passing yards") bracketed 6-10. Neither is constrained;
    any number of players can homer and any number of quarterbacks can pass
    for 4000 yards.

    What separates them is the RULE, not the arithmetic:
      rank constraint       "is rated TOP 10", "finishes in the TOP 10"
                            -> exactly ten of the listed entrants can occupy
                               ten places, so the legs are not independent
      independent threshold "records 2+ home runs", "4000+ passing yards"
                            -> each entrant clears the bar on their own
    """
    for r in records:
        for key in ("rules_primary", "yes_sub_title", "title"):
            text = r.get(key)
            if not text:
                continue
            m = _RANK_PHRASE.search(str(text))
            if m:
                k = int(m.group(1))
                return k if k >= 2 else None
    return None


def fixed_cardinality_range(ask_sum: float,
                            bid_sum: float) -> tuple[int, int] | None:
    """If exactly K legs must resolve YES, which K values does the book allow?

    A third kind of ME=False event, distinct from both a cumulative ladder and
    a free-running basket: "Top 10 Rated in October 2026" lists 20 players and
    EXACTLY ten of them will be top ten. The legs are not independent -- they
    are constrained to sum to K -- so the ask-sum is readable after all, as
    K x 100 + vig. Calling it an independent basket and saying "read each leg
    on its own" is the wrong instruction.

    K is NOT inferred by rounding: with 22 legs and 109c of vig,
    KXF1TOP10-DUTGP26 asks 1109c and rounds to 11 when the truth is 10.
    Instead the two sides of the book BRACKET K -- you cannot buy the whole
    basket for less than K x 100 nor sell it for more -- so this returns the
    admissible RANGE and lets the reader see when it is ambiguous.

    Returns (lo, hi) with lo <= hi and lo >= 2, or None when the book does not
    bracket any plausible K.
    """
    if ask_sum <= 0 or bid_sum <= 0 or bid_sum > ask_sum:
        return None
    lo = math.ceil(bid_sum / 100.0)
    hi = math.floor(ask_sum / 100.0)
    if hi < lo or lo < 2:
        return None
    return lo, hi


def _flag_only_ladder(records: list[dict]) -> bool:
    """Did only the exchange flag make this a ladder, against the shape?

    `mutually_exclusive=False` means "not a partition", which is weaker than
    "cumulative". Three real structures carry that flag:
      cumulative ladder   ordered strikes, monotone       (KXBTCD, KXCPIYOY)
      independent basket  unordered parallel binaries     (KXRAIN, 20 cities)
      mislabelled field   a genuine partition             (KXMOONMAN, 109.9c)
    Returns True for the latter two -- the caller separates them by ask-sum.
    Requires >=3 legs so monotonicity means something.
    """
    if len(records) < 3:
        return False
    if not any(r.get("mutually_exclusive") is False for r in records):
        return False                       # the flag was not what decided it
    stripped = [{k: v for k, v in r.items() if k != "mutually_exclusive"}
                for r in records]
    return not is_threshold_ladder(stripped)


def _shape_is_undecidable(records: list[dict]) -> bool:
    """True when there is not enough evidence to name the structure.

    Two legs and no `mutually_exclusive` flag is genuinely ambiguous: it could
    be a two-outcome field or two rungs of a longer ladder we only partly
    sampled. Saying so beats guessing, because the guess carries a premium
    figure that reads as a measurement.
    """
    if len(records) != 2:
        return False
    return all(r.get("mutually_exclusive") is None for r in records)


def is_standalone_binary(records: list[dict]) -> bool:
    """A one-leg market: a single yes/no question with no sibling legs.

    Kalshi flags these `mutually_exclusive=False`, the same as a cumulative
    ladder, because neither is a partition. They are not the same thing and
    must not be read the same way. KXUCLBTTS ("both teams to score") is one
    leg at 53c: there is no field summing toward 100, and no leg differences
    to read a density from. The only correct statement about its ask is that
    it is the price of that outcome.

    Calling it a ladder implied "the LEG DIFFERENCES are the density", which
    is meaningless for a single leg.
    """
    return len(records) == 1


# Penny noise in a ladder's dead tail is not evidence against monotonicity.
# 15% of steps admits CPI's 3-in-25 while still rejecting an unordered basket.
_LADDER_NOISE_FRACTION = 0.15


_SUBTITLE_DATE = re.compile(
    r"(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*"
    r"(?:(?P<day>\d{1,2})\s*,?\s*)?(?P<year>\d{4})", re.I)


def _subtitle_date_ordinal(record: dict) -> float | None:
    """A sortable date from the leg's HUMAN LABEL, when the ticker cannot give one.

    Date ladders whose tails do not parse were being demoted to
    `independent_basket` -- and that label tells the reader the ask-sum has no
    meaning and each leg stands alone, which is precisely wrong for a
    cumulative distribution.

    KXIMPEACH is the clean case: four nested legs at 1.0 / 3.8 / 21.0 / 59.0
    cents, rising exactly as a "before date D" ladder must. Its tails are
    SEP01 / JAN01 / MAR01 / JAN01 -- month-day fragments with no year, and
    TWO OF THEM ARE IDENTICAL (Jan 1 2027 and Jan 1 2028). No ticker-based
    rule can order that. The dates exist only in `yes_sub_title`
    ("Before Sep 1, 2026"), so read them there.

    Returns an ordinal (year*10000 + month*100 + day) or None. A leg whose
    label names a PERSON rather than a date yields None, which is what keeps
    KXFEDGOVNOM (12 Fed nominees) a genuine basket.
    """
    for key in ("yes_sub_title", "subtitle", "title"):
        text = record.get(key)
        if not text:
            continue
        m = _SUBTITLE_DATE.search(str(text))
        if m:
            # reuse the module's existing month map (UPPERCASE keys) --
            # redefining it here shadowed the original and silently broke
            # _strike_value for every YYMMMDD date strike in the repo.
            mon = _MONTHS.get(m.group("mon")[:3].upper())
            if mon is None:
                continue
            day = int(m.group("day") or 1)
            return int(m.group("year")) * 10000 + mon * 100 + day
    return None


def _numeric(v) -> float | None:
    """A strike field as a float, tolerating null/blank/non-numeric."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def is_threshold_ladder(records: list[dict]) -> bool:
    """Does this event price cumulative thresholds rather than exclusive outcomes?

    A candidate field ("who wins?") is mutually exclusive and its asks sum to
    ~100 + vig. A threshold ladder ("will CPI be above X%?") is a cumulative
    distribution: every leg below the outcome resolves YES, so the asks sum to
    whatever the ladder is long -- KXCPIYOY-26AUG has 26 legs summing to 939c.
    Reading that as a 839c longshot premium is nonsense.

    Detected structurally: a ladder's ticker suffixes are all "T<number>"
    (threshold) and its prices are monotone non-increasing in that number.
    Kalshi's own `mutually_exclusive` flag is authoritative when present; this
    is the fallback for records that did not carry it.
    """
    if is_standalone_binary(records):
        return False          # one leg is a binary, not a distribution
    if any(r.get("mutually_exclusive") is True for r in records):
        return False
    if any(r.get("mutually_exclusive") is False for r in records):
        return True

    # Strike suffixes come in two spellings and both are ladders:
    #   T-prefixed  KXCPIYOY-26AUG-T3.4,  KXMLBWINS-BOS-26-T95
    #   bare number KXMLBTOTAL-26AUG181910SDNYM-9  (MLB game totals)
    # Requiring the "T" silently classified every MLB totals ladder as an
    # exclusive field, which would have read its 578c ask-sum as a 478c
    # longshot premium.
    strikes = []
    for r in records:
        # Prefer the exchange's own strike. Parsing it out of the ticker tail
        # works only while the tail happens to be numeric: COSTCOHOTDOG's legs
        # end in 27/28/29/30 (years) and classify correctly by luck, with
        # `floor_strike` null on every leg. Anywhere the exchange DOES supply
        # the number -- KXRIVNA 68000, KXNCAAFWINS 9, KXCPIYOY 2.5 -- it is
        # authoritative and a renamed ticker cannot break it.
        value = _numeric(r.get("floor_strike"))
        if value is None:
            value = _numeric(r.get("cap_strike"))
        if value is None:
            tail = (r.get("ticker") or "").rsplit("-", 1)[-1]
            body = tail[1:] if tail[:1].upper() == "T" else tail
            value = _strike_value(body)
        if value is None:
            value = _subtitle_date_ordinal(r)
        if value is None:
            return False
        # MUST go through _ask_cents: raw /markets records ship only
        # `yes_ask_dollars`, so reading `yes_ask` left `asks` empty, tripped
        # the len<3 guard, and dropped genuine ladders into the exclusive /
        # basket branches with a fabricated premium. _ask_sum_cents was fixed
        # for this and this call site was missed.
        strikes.append((value, _ask_cents(r), _bid_cents(r)))
    if len(strikes) < 3:
        return False
    strikes.sort(key=lambda x: x[0])
    asks = [a for _, a, _ in strikes if a is not None]
    bids = [b for _, _, b in strikes if b is not None]
    if len(asks) < 3 and len(bids) < 3:
        return False
    # A cumulative ladder is monotone, but the DIRECTION depends on what the
    # strike axis measures:
    #   price  "above $X"      -> decreasing in X (higher price, less likely)
    #   date   "before date D" -> INCREASING in D (later date, more likely)
    # Corporate-event markets ladder by date, so accepting only the decreasing
    # case classified every IPO/CEO/acquisition timing ladder as an exclusive
    # field and reported its cumulative ask-sum as a huge longshot premium.
    #
    # Test BOTH sides and accept if EITHER is monotone. On a dead rung the ask
    # is market-maker padding carrying no information, and it destroys the
    # shape: KXNCAAFWINS-26SCAR ("at least N wins") asks
    #   85 70 49 36 36 18 63 96
    # because the 11+ and 12+ rungs are quoted wide against a ZERO bid, while
    # its bids run cleanly 72 65 47 29 19 7 1 0. Ask-only monotonicity
    # therefore demoted a textbook cumulative ladder to `independent_basket`
    # and told the reader to price each leg on its own -- exactly backwards.
    # Tolerance must SCALE with the ladder. A fixed "one bad tick" allowance
    # is fine for a 5-rung ladder and impossible for a 26-rung one: KXCPIYOY
    # -26AUG, the canonical ladder this docstring cites, has a flat tail
    # quoted 2 3 2 3 3 3 1 2 2 2 1 1 1 1 where penny noise alone produces
    # three up-ticks in 25 steps. It was being demoted to `independent_basket`
    # -- the exact misreading the whole function exists to prevent.
    def _monotone(xs: list[float]) -> bool:
        if len(xs) < 3:
            return False
        steps = len(xs) - 1
        allowed = max(1, round(_LADDER_NOISE_FRACTION * steps))
        ups = sum(1 for i in range(1, len(xs)) if xs[i] > xs[i - 1])
        downs = sum(1 for i in range(1, len(xs)) if xs[i] < xs[i - 1])
        return ups <= allowed or downs <= allowed

    return _monotone(asks) or _monotone(bids)


def ask_sums_by_event(records: list[dict]) -> dict[str, dict]:
    """Per-event ask-sums, which is the only grouping that means anything.

    Threshold ladders are reported but explicitly NOT given a premium: the
    ask-sum of a cumulative distribution carries no vig interpretation.
    """
    groups: dict[str, list[dict]] = {}
    for r in records:
        groups.setdefault(event_ticker(r), []).append(r)
    out = {}
    for ev, recs in groups.items():
        s = ask_sum_cents(recs)
        if s is None:
            continue
        note = None
        if is_standalone_binary(recs):
            structure, premium = "standalone_binary", None
        elif is_two_sided_handicap(recs):
            # MUST precede the ladder test. A handicap book satisfies
            # is_threshold_ladder (ME=False + numeric strikes) and was being
            # labelled `threshold_ladder` on period spreads and
            # `independent_basket` on full-game spreads -- one archetype,
            # two wrong labels, decided by which event you happened to read.
            structure, premium = "two_sided_handicap", None
            note = TWO_SIDED_HANDICAP_NOTE
        elif is_threshold_ladder(recs):
            structure, premium = "threshold_ladder", None
            if _flag_only_ladder(recs):
                # ME=False + non-monotone legs means the flag alone decided
                # this, and "not a partition" does NOT imply "cumulative".
                # Which of the two remaining readings applies is settled by
                # whether the asks sum to about 100.
                if _VIG_BAND[0] <= s <= _VIG_BAND[1]:
                    structure = "disputed"          # a mislabelled partition
                    premium = round(s - 100.0, 2)
                    note = DISPUTED_FIELD_NOTE
                else:
                    structure = "independent_basket"
                    note = BASKET_NOTE
                    # ...unless the two sides bracket an integer K, in which
                    # case the legs are constrained rather than independent
                    # and "read each leg on its own" is the wrong advice.
                    # BOTH signals required, and they must agree. The rules
                    # must NAME a rank constraint, and the book must actually
                    # bracket that K. Either alone gives false positives.
                    stated = stated_cardinality(recs)
                    bs = [b for b in (_bid_cents(r) for r in recs)
                          if b is not None]
                    rng = (fixed_cardinality_range(s, sum(bs)) if bs else None)
                    if stated and rng and rng[0] <= stated <= rng[1]:
                        note = FIXED_CARDINALITY_NOTE.format(k=stated)
                    elif stated and bs:
                        # The rules NAME a K but the book does not bracket it.
                        # Falling back to "the ask-sum has no meaning" would
                        # hide the more interesting fact: on a K-place
                        # partition the ask-sum has a floor of K x 100, and
                        # KXCHESSFIDERATINGTOP-26OCTWOMENT10 asked 998c for
                        # ten places against 920c of bids.
                        note = CARDINALITY_MISMATCH_NOTE.format(
                            k=stated, par=stated * 100,
                            ask=round(s, 1), bid=round(sum(bs), 1))
        elif _shape_is_undecidable(recs):
            # Monotonicity needs >=3 points, so a 2-leg sample with no
            # exchange flag cannot be classified at all. Defaulting to
            # exclusive_field printed a confident premium (-17c on a 2-leg
            # KXIPOOPENAI sample) derived from a field we never saw whole.
            structure, premium = "indeterminate", None
        else:
            structure, premium = "exclusive_field", round(s - 100.0, 2)
            if s < _VIG_BAND[0]:
                note = SUB_100_FIELD_NOTE

        if premium is not None:
            # Most specific diagnosis first: a settled or quoteless book
            # explains itself better than "this number looks too big".
            readable, why = premium_is_readable(recs, s)
            if not readable:
                premium, note = None, why
            elif structure == "exclusive_field":
                bids = [b for b in (_bid_cents(r) for r in recs)
                        if b is not None]
                if bids and sum(bids) > _MAX_FIELD_BID_SUM:
                    premium, note = None, IMPLAUSIBLE_FIELD_NOTE
        entry = {"ask_sum_cents": s, "legs": len(recs),
                 "structure": structure, "premium_cents": premium}
        if note:
            entry["note"] = note
        out[ev] = entry
    return out


# A sum BELOW 100 on an exclusive field has TWO readings and this module can
# not tell them apart from prices alone:
#   (a) the scan sampled only part of the field  -> the number means nothing
#   (b) the field is CONDITIONAL: every listed outcome requires some precondition
#       that may simply not occur, and there is no leg for "nothing happens"
#       -> the sum IS the market's probability that the field resolves at all
# KXMODELHIGH-27-1550 is case (b): a complete 8-leg ME=True field, including an
# explicit "Other" leg, asking 37c because "no model reaches 1550 before 2027"
# is not purchasable. Calling that "legs missing from the scan" was wrong.
SUB_100_FIELD_NOTE = ("ask_sum < 100 on an exclusive field is ambiguous: either "
                      "the sample is partial, or the field is conditional and "
                      "the sum is P(field resolves at all). Not a vig reading.")
INCOMPLETE_FIELD_NOTE = SUB_100_FIELD_NOTE      # backwards-compatible alias

# A partition pays out exactly 100c in total: one leg wins, the rest expire
# worthless. So SELLING every leg can never be worth much more than 100c --
# the bid-sum is bounded by the payout no matter how many legs there are.
# The ASK-sum is not: it widens with illiquidity, and on a thin book it says
# nothing about whether the event is a partition at all.
#
# This replaced a per-leg ask allowance that got it backwards. That version
# flagged KXNCAAFAPRANK-26W12R1 (13 legs, ask-sum 219c) as "probably not a
# field" when its bid-sum was 41c -- a textbook partition with one 96c
# favourite and twelve zero-bid longshots quoted wide. Meanwhile the actual
# non-partition, KXF1TOP10-DUTGP26, bids 805c across 22 legs: you could sell
# the entire "field" for 805c and owe at most 100c. That is the tell.
_MAX_FIELD_BID_SUM = 105.0


IMPLAUSIBLE_FIELD_NOTE = ("bid-sum exceeds the 100c a partition can pay out, "
                          "so these legs are NOT mutually exclusive however "
                          "they are labelled -- most often the event flag was "
                          "never attached and this is really a basket. "
                          "Premium withheld.")

# A flag/shape disagreement worth surfacing rather than silently resolving.
# Prices alone cannot separate these two, so do not pretend otherwise. Both
# read "flag says not-a-partition, legs are not ordered, asks sum near 100":
#   a partition Kalshi mislabelled  (KXMOONMAN-31, 5 countries, 109.9c), or
#   an independent basket that happens to sum near 100 by coincidence.
# The premium is only a vig reading under the first, so it is reported as
# CONDITIONAL rather than asserted.
DISPUTED_FIELD_NOTE = ("AMBIGUOUS: exchange flag says not-a-partition but the "
                       "legs are unordered and the asks sum near 100. Either a "
                       "mislabelled partition (KXMOONMAN-31 is 5 countries at "
                       "109.9c flagged False) or a basket summing near 100 by "
                       "chance. premium_cents is a vig reading ONLY under the "
                       "first -- confirm the legs are alternatives of one "
                       "question before using it.")

SETTLED_BOOK_NOTE = ("legs are FINALIZED: Kalshi quotes a settled leg at ask "
                     "1.0000 whether it won or lost, so the ask-sum is just the "
                     "leg count. A settled 7-leg KXUFCMOV event reported +600c, "
                     "presented identically to a real vig.")

QUOTELESS_BOOK_NOTE = ("no live bid side: every leg bids at or near zero while "
                       "asks are wide, so the ask-sum measures DORMANCY, not "
                       "vig. KXWBCHEAVYWEIGHTTITLE-27 reported +516c on a book "
                       "whose highest bid was 3c.")

# A premium is a claim about a live two-sided market. Below this the bid side
# is effectively absent and the ask-sum stops meaning anything.
_MIN_LIVE_BID_CENTS = 5.0
_SETTLED_STATUSES = frozenset({"finalized", "settled", "closed", "determined"})

BASKET_NOTE = ("independent parallel binaries sharing one event -- neither a "
               "partition nor a cumulative ladder. The ask-sum has NO meaning: "
               "KXRAIN-26AUG19 is 20 different cities asking 279c. Read each "
               "leg on its own.")
FIXED_CARDINALITY_NOTE = (
    "legs are CONSTRAINED, not independent: the book brackets exactly {k} of "
    "them resolving yes, so this is a fixed-cardinality basket and the "
    "ask-sum IS readable as K x 100 + vig. "
    "KXCHESSFIDERATINGTOP-26OCTWOMENT10 lists 20 players for 'Top 10 Rated' "
    "and asks 1003c. Do NOT read the legs as independent, and do not treat "
    "the ask-sum as a longshot premium.")

CARDINALITY_MISMATCH_NOTE = (
    "the rules name a {k}-place constraint, so buying every leg should cost "
    "about {par}c -- but this book asks {ask}c against {bid}c of bids. The "
    "two sides do not bracket {k}, so either the constraint is not what the "
    "wording implies or the book is mispriced against it. Read the rungs "
    "before trusting either number; no premium is claimed here.")

TWO_SIDED_HANDICAP_NOTE = (
    "TWO OPPOSED LADDERS in one event: both teams are listed at the same "
    "margins and `floor_strike` stores the magnitude UNSIGNED, so the sides "
    "collide at every rung. Same-team rungs are strictly nested; cross-team "
    "rungs at one margin are mutually exclusive. The ask-sum is therefore "
    "NEITHER vig NOR a single cumulative distribution -- split the legs by "
    "team before reading anything. Strikes are all x.5 with a strict "
    "'greater', so no push is possible.")

_VIG_BAND = (95.0, 130.0)


def ticker_matches(market_ticker: str, patterns: list[str] | None) -> bool:
    """Match against the market ticker itself.

    Needed because close_time is NOT a reliable election-day proxy. The
    KXFLRGOVEXACT-26AUG18-* contracts embed their event date in the ticker but
    carry close_time=2027-08-18, and the KXGOVFLNOMR nomination markets close
    2026-11-03 (the general) rather than on the primary date. Filtering an
    election day by close_time alone silently returns the wrong set.
    """
    return series_matches(market_ticker, patterns)


def conviction_score(rec: dict, *, thin_book_contracts: float = 20000.0) -> float:
    """Rank movers by move size discounted linearly for book depth.

    weight = min(1, volume / thin_book_contracts). A book at or above the
    reference depth keeps its move intact; a book at a tenth of it keeps a
    tenth of its move. Linear rather than sqrt because sqrt barely moves the
    ranking: on the Askar case it left an 18c move on 7,250 contracts ahead of
    a 6c move on 280,000, which is the ordering the score exists to fix.

    `thin_book_contracts` should be set to the depth NORMAL FOR THE RACE being
    scanned, not left at the default. FL-22R turns ~280k contracts in 24h, so
    scanning it with the 20k default still flatters a 7k-contract move.
    """
    delta = abs(float(rec.get("delta") or 0.0))
    vol = max(0.0, float(rec.get("volume") or 0.0))
    weight = min(1.0, vol / thin_book_contracts) if thin_book_contracts > 0 else 1.0
    return round(delta * weight, 6)


def is_thin_book(rec: dict, thin_book_contracts: float = 20000.0) -> bool:
    return float(rec.get("volume") or 0.0) < thin_book_contracts


def annotate(records: list[dict], *, thin_book_contracts: float = 20000.0
             ) -> list[dict]:
    """Attach conviction + thin-book flags without reordering."""
    for r in records:
        r["conviction"] = conviction_score(r, thin_book_contracts=thin_book_contracts)
        r["thin_book"] = is_thin_book(r, thin_book_contracts)
    return records


def rank(records: list[dict], *, by: str = "conviction") -> list[dict]:
    """Sort movers. `by="delta"` reproduces the old absolute-delta ordering."""
    if by == "delta":
        return sorted(records, key=lambda r: abs(r.get("delta") or 0.0), reverse=True)
    return sorted(records, key=lambda r: r.get("conviction") or 0.0, reverse=True)
