"""Map the words a HEADLINE uses onto the series Kalshi actually lists.

THE PROBLEM THIS SOLVES, measured before it was written:
`VaultGraph.retrieve_context` scored 45.5% precision@1 on a labelled headline
set, missed 5 of 22 in-scope headlines entirely, and answered 2 of the 3
headlines it should have ignored. Not because it was slow -- it runs in
0.1ms -- but because it indexes note TITLES and ALIASES only, and note titles
describe market STRUCTURE ("Vertical: MLB Pro Baseball") while headlines name
ENTITIES ("Yankees"). The word "Yankees" appears in zero note titles, zero
aliases and zero note bodies, so "Yankees rally past Red Sox" fell through to
whatever else shared the word "series" -- which was NHL.

THE FIX: Kalshi's own API is the entity dictionary, free and always current.
Every market carries a `yes_sub_title` naming the team, player or school it
is about. Harvesting those gives an entity -> series map with no model, no
embedding and no hand-authored alias list.

WHAT THE API DOES NOT GIVE, and why the nickname table exists: MLB and WNBA
subtitles are CITIES ("Milwaukee") while headlines use NICKNAMES ("Brewers").
NFL publishes both forms already and needs nothing. The table covers only the
leagues with the gap, and it is knowledge rather than compute -- the right
place to spend on this system.

COST: building sweeps the API once (~16s) and caches 20 KB of JSON. Lookup
after that is dict access over at most 3n phrases -- no network, no model.

ABSTENTION IS A FEATURE. If nothing matches, this returns nothing. A
retriever that always answers is worse than one that stays quiet, because a
confident wrong context block is what loses money on a headline.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# Subtitles that are strike descriptions, not entities. Crypto and threshold
# ladders publish "$50,000 or above" in the same field team sports use for the
# team name; indexing those maps every dollar figure in a headline onto BTC.
_NOT_AN_ENTITY = re.compile(
    r"^\$|\bor above\b|\bor below\b|^\d|^yes$|^no$|^[<>]=?", re.I)

# "Alex Bregman: 1+" -> "Alex Bregman"
_STRIP_SUFFIX = re.compile(r"\s*:\s*\d+\+?\s*$")

# Too generic to identify anything alone. "Chicago" is deliberately NOT here:
# it is ambiguous across four leagues, which is handled by returning every
# match rather than by discarding it.
_WEAK_TOKENS = frozenset({
    "the", "of", "and", "at", "st", "state", "united", "city", "fc", "sc",
    "club", "team", "univ", "university", "a", "b", "i", "ii",
})

# The vocabulary a headline uses when something HAPPENED to an entity. This is
# what separates "Chiefs quarterback ruled out" from "suburban Ohio" -- both
# name a real Kalshi entity, only one is about a market. Deliberately a plain
# word list rather than a classifier: the point of this module is that routing
# costs microseconds and needs no model.
EVENT_WORDS = frozenset({
    "wins", "win", "won", "beat", "beats", "defeat", "defeats", "defeated",
    "upset", "upsets", "loses", "lost", "falls", "rally", "rallies",
    "clinch", "clinches", "clinched", "advance", "advances", "eliminated",
    "injury", "injured", "hurt", "ruled", "withdraws", "withdrew",
    "questionable", "doubtful", "sidelined", "returns", "activated",
    "trade", "traded", "signs", "signed", "released", "waived", "suspended",
    "homer", "homers", "touchdown", "goal", "goals", "scored", "shutout",
    "streak", "sweep", "swept", "walkoff", "overtime", "innings",
    "playoff", "playoffs", "championship", "finals", "quarterfinals",
    "semifinal", "semifinals", "berth", "seed", "leads", "trails", "straight",
})

# Kalshi publishes MLB and WNBA by CITY; headlines say the nickname. Every
# target below was verified against a live API sweep -- all 30 MLB strings
# matched exactly, with no unmapped teams remaining.
NICKNAMES: dict[str, dict[str, str]] = {
    "KXMLBGAME": {
        "yankees": "New York Y", "mets": "New York M",
        "red sox": "Boston", "blue jays": "Toronto", "orioles": "Baltimore",
        "rays": "Tampa Bay", "guardians": "Cleveland", "twins": "Minnesota",
        "tigers": "Detroit", "royals": "Kansas City", "white sox": "Chicago WS",
        "cubs": "Chicago C", "astros": "Houston", "mariners": "Seattle",
        "rangers": "Texas", "angels": "Los Angeles A", "athletics": "A's",
        "braves": "Atlanta", "phillies": "Philadelphia",
        "nationals": "Washington", "marlins": "Miami", "brewers": "Milwaukee",
        "cardinals": "St. Louis", "reds": "Cincinnati",
        "pirates": "Pittsburgh", "dodgers": "Los Angeles D",
        "padres": "San Diego", "giants": "San Francisco",
        "diamondbacks": "Arizona", "rockies": "Colorado",
    },
    "KXWNBAGAME": {
        "liberty": "New York", "sky": "Chicago", "sun": "Connecticut",
        "fever": "Indiana", "dream": "Atlanta", "mystics": "Washington",
        "aces": "Las Vegas", "storm": "Seattle", "sparks": "Los Angeles",
        "mercury": "Phoenix", "wings": "Dallas", "lynx": "Minnesota",
        "valkyries": "Golden State",
        # Portland and Toronto joined for 2026 and the API lists them, but
        # their nicknames are not verified here. Left unmapped rather than
        # guessed -- a wrong nickname routes a headline to the wrong team,
        # which is worse than not routing it at all.
    },
}


# Function words that a pure document-frequency filter cannot catch. "for"
# is carried by exactly one series ("...for the year ending in August 2026"),
# so it looks distinctive by frequency alone and routed "local bakery wins
# award FOR sourdough" straight to CPI. Rarity across series is evidence a
# token identifies a series; it is not evidence the token means anything.
_FUNCTION_WORDS = frozenset({
    "for", "with", "than", "from", "will", "be", "above", "below", "between",
    "following", "year", "ending", "month", "day", "date", "time", "price",
    "rate", "upper", "lower", "bound", "maximum", "minimum", "close", "open",
    "high", "low", "next", "last", "first", "any", "all", "more", "less",
    "before", "after", "during", "per", "into", "over", "under", "out",
    "end", "start", "week", "today", "tomorrow", "meeting", "report",
})


def _norm(s: str) -> str:
    s = _STRIP_SUFFIX.sub("", s or "").strip().lower()
    return re.sub(r"[^a-z0-9' ]+", " ", s).strip()


def _strip_possessive(t: str) -> str:
    """"the Fed's meeting" -> "fed". Apostrophes survive _norm because the
    Athletics are published as "A's", but a possessive is not part of a name
    and left alone it hides "Fed" behind the token "fed's"."""
    return t[:-2] if len(t) > 3 and t.endswith("'s") else t


def _phrase_tokens(s: str) -> list[str]:
    return [w for w in (_strip_possessive(t) for t in _norm(s).split())
            if w and w not in _WEAK_TOKENS]


@dataclass(frozen=True)
class EntityHit:
    entity: str
    series: str
    n_tokens: int


@dataclass
class EntityIndex:
    """entity phrase -> the series that list it."""
    by_phrase: dict[str, set[str]] = field(default_factory=dict)
    series_seen: set[str] = field(default_factory=set)
    # Single tokens that ARE strong evidence on their own. A subject term
    # harvested at low cross-series document frequency ("bitcoin", "cpi") is
    # distinctive by construction, unlike a bare team name ("Ohio") which is
    # a real school and also a place where cats get stuck in trees.
    strong_singles: set[str] = field(default_factory=set)

    def add(self, phrase: str, series: str) -> None:
        p = _norm(phrase)
        if not p or _NOT_AN_ENTITY.search(p):
            return
        toks = _phrase_tokens(p)
        if not toks:
            return
        self.by_phrase.setdefault(" ".join(toks), set()).add(series)
        self.series_seen.add(series)
        # Also index the LAST significant token alone. Kalshi publishes NFL as
        # "KC Chiefs" and tennis as "Frances Tiafoe", but a headline says
        # "Chiefs" or "Tiafoe" -- the discriminative half is the nickname or
        # the surname, and it is always last.
        #
        # Length >= 4 excludes Kalshi's short DISAMBIGUATORS, which are the
        # last token of their phrase and would therefore be indexed alone:
        # "Chicago WS" -> "ws", "New York Y" -> "y", "Los Angeles D" -> "d".
        # Those are one or two characters of bookkeeping, not names, and
        # indexing them routes any headline containing a stray "d" to the
        # Dodgers.
        #
        # (The league abbreviations that LEAD a phrase -- the "TEN" in "TEN
        # Titans" -- are never at risk here, because only the LAST token is
        # indexed on its own.)
        last = toks[-1]
        if len(toks) > 1 and len(last) >= 4:
            self.by_phrase.setdefault(last, set()).add(series)

    def add_nicknames(self) -> None:
        """Attach headline nicknames to series whose subtitles are cities."""
        for series, table in NICKNAMES.items():
            if series not in self.series_seen:
                continue
            for nick in table:
                n = " ".join(_phrase_tokens(nick))
                if n:
                    self.by_phrase.setdefault(n, set()).add(series)

    def lookup(self, headline: str) -> list[EntityHit]:
        """Entity phrases present in `headline`, longest match first.

        Empty is a real answer: Kalshi lists nothing this headline is about.
        """
        toks = _phrase_tokens(headline)
        if not toks:
            return []
        hits: list[EntityHit] = []
        seen: set[tuple[str, str]] = set()
        for width in (3, 2, 1):
            for i in range(len(toks) - width + 1):
                phrase = " ".join(toks[i:i + width])
                for series in self.by_phrase.get(phrase, ()):
                    key = (phrase, series)
                    if key in seen:
                        continue
                    seen.add(key)
                    hits.append(EntityHit(phrase, series, width))
        hits.sort(key=lambda h: -h.n_tokens)
        return hits

    def series_for(self, headline: str, corroborate: bool = True) -> list[str]:
        """Series this headline names, strongest evidence first.

        A single bare token is WEAK EVIDENCE. "Ohio" is a real NCAAF school,
        so "man rescues cat from tree in suburban Ohio" matches on entity
        grounds alone. With `corroborate` on, a lone one-token match must be
        backed by a second entity from the same series or by an event word.

        Two entities from one series need no event word -- "Titans upset the
        Bears" is unambiguous without one.
        """
        hits = self.lookup(headline)
        if not hits:
            return []
        has_event = bool(set(_phrase_tokens(headline)) & EVENT_WORDS)
        per_series: dict[str, list[EntityHit]] = {}
        for h in hits:
            per_series.setdefault(h.series, []).append(h)
        out: list[str] = []
        for h in hits:
            if h.series in out:
                continue
            group = per_series[h.series]
            strong = (any(g.n_tokens > 1 for g in group)
                      or len({g.entity for g in group}) >= 2
                      or has_event
                      or any(g.entity in self.strong_singles for g in group))
            if corroborate and not strong:
                continue
            out.append(h.series)
        return out

    def to_json(self) -> str:
        return json.dumps({"by_phrase": {k: sorted(v)
                                         for k, v in self.by_phrase.items()},
                           "series_seen": sorted(self.series_seen),
                           "strong_singles": sorted(self.strong_singles)})

    @classmethod
    def from_json(cls, text: str) -> "EntityIndex":
        d = json.loads(text)
        return cls(by_phrase={k: set(v) for k, v in d["by_phrase"].items()},
                   series_seen=set(d.get("series_seen", [])),
                   strong_singles=set(d.get("strong_singles", [])))

    def save(self, path: Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "EntityIndex":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


def build_from_markets(markets_by_series: dict[str, list[dict]]) -> EntityIndex:
    """Harvest entity phrases from `yes_sub_title` per series.

    Pure: takes already-fetched records so it is testable without a network.
    """
    idx = EntityIndex()
    for series, markets in markets_by_series.items():
        for m in markets:
            for key in ("yes_sub_title", "subtitle"):
                v = m.get(key)
                if v:
                    idx.add(v, series)
    idx.add_nicknames()
    return idx


def add_subject_terms(idx: EntityIndex,
                      titles_by_series: dict[str, set[str]],
                      max_series_df: int = 2) -> EntityIndex:
    """Harvest SUBJECT terms from market titles, for series with no entities.

    Crypto, macro and weather publish price strikes in `yes_sub_title`
    ("$50,000 or above"), so the entity harvest finds nothing for them. Their
    subject lives in the TITLE instead: "Bitcoin price on Aug 21", "the rate
    of CPI inflation", "the Fed's Apr 2027 meeting".

    Titles are full sentences, so most of their words are worthless -- "will",
    "the", "above", "rate" appear in nearly every series. The filter is
    DOCUMENT FREQUENCY ACROSS SERIES, not a stopword list: a token carried by
    at most `max_series_df` series identifies those series, and one carried by
    twenty identifies nothing. That is the same principle the vault's IDF uses,
    applied to a corpus where it actually discriminates.
    """
    # ONLY series that produced no entities. Harvesting titles for a series
    # that already has entities re-adds its team names as "strong" singles,
    # which silently defeats the corroboration gate: "ohio" came back as a
    # distinctive subject term and "man rescues cat in suburban Ohio" routed
    # to college football again.
    eligible = {s: t for s, t in titles_by_series.items()
                if s not in idx.series_seen}
    df: dict[str, int] = {}
    per_series: dict[str, set[str]] = {}
    for series, titles in eligible.items():
        toks: set[str] = set()
        for t in titles:
            toks.update(w for w in _phrase_tokens(t)
                        if len(w) >= 3 and w not in _FUNCTION_WORDS)
        per_series[series] = toks
        for w in toks:
            df[w] = df.get(w, 0) + 1
    for series, toks in per_series.items():
        for w in toks:
            if df[w] <= max_series_df and not w.isdigit():
                idx.by_phrase.setdefault(w, set()).add(series)
                idx.series_seen.add(series)
                idx.strong_singles.add(w)
    return idx
