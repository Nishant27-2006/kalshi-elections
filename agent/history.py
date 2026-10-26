"""
Verified base rates from SETTLED Kalshi markets.

Every `## Historical Analog` slot in this vault currently reads "None recorded",
because the alternative was writing remembered facts — exactly what invariant K
forbids. This module closes that gap the only legitimate way: by pulling
markets Kalshi has already settled and counting what actually happened.

`GET /markets?status=settled` returns finalized markets carrying `result`
("yes"/"no"). That is an observation, not a memory, so anything computed here
is citable in a note.

No LLM, no writes. Pure fetch + arithmetic, so the numbers can be re-derived by
running the same command printed into each note's Update Log.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from momentum_filter import event_ticker


@dataclass
class SettledEvent:
    """One resolved event and which of its legs paid out."""
    event: str
    legs: int
    winners: list[str] = field(default_factory=list)   # sub-titles resolving yes
    losers: int = 0
    voided: int = 0                                   # legs resolving `scalar`

    @property
    def decided(self) -> bool:
        """Did exactly one leg win? False for ladders and no-winner fields."""
        return len(self.winners) == 1

    @property
    def abandoned(self) -> bool:
        """Did the exchange settle any leg at a price instead of yes/no?

        Tennis is where this surfaces: a walkover or mid-match retirement
        sends the contract to "Fair Market Price, as determined at the sole
        discretion of the Exchange" and the feed reports `scalar`.
        """
        return self.voided > 0


@dataclass
class BaseRate:
    """A countable historical fact, with the sample it came from."""
    label: str
    hits: int
    total: int

    @property
    def rate(self) -> float:
        return self.hits / self.total if self.total else 0.0

    def render(self) -> str:
        return f"{self.label}: {self.hits}/{self.total} = {self.rate:.1%}"


def fetch_settled(client, series_ticker: str, *, max_pages: int = 12,
                  page_size: int = 200) -> list[dict]:
    """Every settled market in a series, following the cursor.

    Same no-silent-truncation rule as the scanner: if the page cap is hit with
    a cursor outstanding, say so rather than returning a short list that reads
    as the whole history.
    """
    out: list[dict] = []
    cursor = None
    for page in range(max_pages):
        params = {"series_ticker": series_ticker, "status": "settled",
                  "limit": page_size}
        if cursor:
            params["cursor"] = cursor
        data = client.get("/markets", params=params)
        out.extend(data.get("markets") or [])
        cursor = data.get("cursor")
        if not cursor:
            return out
    print(f"  {series_ticker}: stopped at {max_pages} pages "
          f"({len(out)} settled); more history remains")
    return out


def group_settled(markets: list[dict]) -> list[SettledEvent]:
    """Settled markets -> one SettledEvent per event, newest first by ticker."""
    events: dict[str, SettledEvent] = {}
    for m in markets:
        ev = m.get("event_ticker") or event_ticker(m.get("ticker", ""))
        se = events.setdefault(ev, SettledEvent(event=ev, legs=0))
        se.legs += 1
        # `result` has THREE values, not two. A leg settled at Fair Market
        # Price reports `scalar`, and counting it as a loss overstates the
        # loser tally and makes an abandoned match look like one nobody won.
        res = str(m.get("result", "")).lower()
        if res == "yes":
            se.winners.append(m.get("yes_sub_title")
                              or m.get("ticker", "").rsplit("-", 1)[-1])
        elif res == "scalar":
            se.voided += 1
        else:
            se.losers += 1
    return sorted(events.values(), key=lambda e: e.event, reverse=True)


def winner_frequency(events: list[SettledEvent], *,
                     min_events: int = 5) -> list[BaseRate]:
    """How often each outcome won, across decided events only.

    Ladders and no-winner fields are excluded: a cumulative ladder resolves
    many legs yes at once, so counting its "winners" would swamp the tally.
    Returns [] below `min_events` rather than publishing a rate from a sample
    too small to mean anything.
    """
    decided = [e for e in events if e.decided]
    if len(decided) < min_events:
        return []
    counts = Counter(e.winners[0] for e in decided)
    n = len(decided)
    return [BaseRate(label=k, hits=v, total=n)
            for k, v in counts.most_common()]


def yes_rate(markets: list[dict], *, min_markets: int = 10) -> BaseRate | None:
    """Share of settled LEGS that resolved yes.

    The right statistic for a standalone binary ("did the thing happen?"), and
    meaningless for an exclusive field, where exactly one leg wins by
    construction. Callers must know which structure they are asking about.
    """
    resolved = [m for m in markets
                if str(m.get("result", "")).lower() in ("yes", "no")]
    if len(resolved) < min_markets:
        return None
    hits = sum(1 for m in resolved if str(m["result"]).lower() == "yes")
    return BaseRate(label="resolved YES", hits=hits, total=len(resolved))


def void_rate(events: list[SettledEvent], *,
              min_events: int = 5) -> BaseRate | None:
    """How often the exchange settled an event at a price instead of yes/no.

    Measured on tennis, where the rule is explicit: a match that never starts,
    or one abandoned mid-match, resolves to "Fair Market Price, as determined
    at the sole discretion of the Exchange". The settled feed marks those legs
    `scalar`. 35 of 944 ATP matches and 38 of 956 WTA matches did this.

    This is the base rate for a settlement branch that pays neither 100c nor
    0c, so it belongs in the record rather than folded into the losers.
    """
    if len(events) < min_events:
        return None
    hit = sum(1 for e in events if e.abandoned)
    return BaseRate(label="events settled at Fair Market Price",
                    hits=hit, total=len(events))


def ladder_hit_rate(events: list[SettledEvent], *,
                    min_events: int = 5) -> BaseRate | None:
    """For ladders: how often ANY leg resolved yes.

    On a cumulative ladder every rung below the outcome pays, so the
    interesting question is not which rung won but whether the field resolved
    at all -- the count-ladder / date-ladder equivalent of "did it happen".
    """
    if len(events) < min_events:
        return None
    hit = sum(1 for e in events if e.winners)
    return BaseRate(label="events with any winning leg", hits=hit,
                    total=len(events))


def summarise(client, series_ticker: str) -> dict:
    """Everything countable about one series' settled history.

    Returns a dict rather than prose so the caller decides what belongs in a
    note. `sample` is reported alongside every rate so a reader can judge it.
    """
    markets = fetch_settled(client, series_ticker)
    events = group_settled(markets)
    decided = [e for e in events if e.decided]
    return {
        "series": series_ticker,
        "settled_markets": len(markets),
        "settled_events": len(events),
        "decided_events": len(decided),
        "yes_rate": yes_rate(markets),
        "winner_frequency": winner_frequency(events),
        "ladder_hit_rate": ladder_hit_rate(events),
        "void_rate": void_rate(events),
        "abandoned_events": sum(1 for e in events if e.abandoned),
        "sample_events": [e.event for e in events[:5]],
    }
