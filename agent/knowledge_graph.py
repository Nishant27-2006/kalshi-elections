"""
Knowledge graph over the Obsidian political vault.

The vault is already a graph: ~130 notes connected by [[wikilinks]], with
canonical titles carried as YAML `aliases` (because Windows filenames can't
contain ':'). This module parses that into an in-memory graph and does
seed-match -> BFS expansion retrieval, so a headline about "Max Miller"
pulls not just his district note but the connected pattern notes that
explain how to price it.

No LLM, no embeddings, no network. Pure local parse — this is the "free"
tier of the funnel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import VAULT_PATH
from .timeline import assess, latest_event, parse_timeline

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
ALIAS_BLOCK_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
ALIAS_LINE_RE = re.compile(r'^\s*-\s*"?([^"\n]+)"?\s*$', re.MULTILINE)
TAG_RE = re.compile(r"^tags:\s*\n((?:\s*-\s*.+\n)+)", re.MULTILINE)


@dataclass
class Note:
    path: Path
    title: str                       # canonical title (alias if present, else filename)
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)   # outbound wikilink targets
    body: str = ""

    def summary(self, max_chars: int = 1200) -> str:
        """Body with frontmatter stripped, truncated for LLM context."""
        text = re.sub(r"^---.*?---\s*", "", self.body, flags=re.DOTALL)
        text = text.strip()
        return text[:max_chars] + ("..." if len(text) > max_chars else "")


_ELLIPSIS = "..."

# Rendered by nodes.format_expert_context. Kept here so expert_context can
# charge the budget for the text the prompt will actually carry.
SLOT_LABELS = {"latest_event": "Data as of",
               "resolution_source": "Resolution rule",
               "timing_risk": "Timing risk",
               "related_markets": "Related market",
               "historical_analog": "Historical analog"}
CONTEXT_HEADER = "=== EXPERT CONTEXT (from vault) ===" + chr(10)


class VaultGraph:
    def __init__(self, vault_path: Path | None = None):
        self.vault_path = Path(vault_path or VAULT_PATH)
        self.notes: dict[str, Note] = {}       # keyed by canonical title
        self.alias_index: dict[str, str] = {}  # lowercased alias/title -> canonical
        self.backlinks: dict[str, set[str]] = {}
        self._load()

    def _load(self) -> None:
        if not self.vault_path.exists():
            return
        for md in self.vault_path.glob("*.md"):
            try:
                raw = md.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            aliases: list[str] = []
            tags: list[str] = []
            fm = ALIAS_BLOCK_RE.match(raw)
            if fm:
                block = fm.group(1)
                if "aliases:" in block:
                    alias_section = block.split("aliases:", 1)[1]
                    alias_section = alias_section.split("tags:")[0]
                    aliases = [a.strip().strip('"') for a in ALIAS_LINE_RE.findall(alias_section)]
                tm = TAG_RE.search(block)
                if tm:
                    tags = [t.strip("- ").strip() for t in tm.group(1).strip().splitlines()]

            title = aliases[0] if aliases else md.stem
            links = [m.strip() for m in WIKILINK_RE.findall(raw)]

            note = Note(path=md, title=title, aliases=aliases, tags=tags,
                        links=links, body=raw)
            self.notes[title] = note

            for key in {title, md.stem, *aliases}:
                self.alias_index[key.lower()] = title

        # backlinks
        for title, note in self.notes.items():
            for link in note.links:
                target = self.alias_index.get(link.lower())
                if target:
                    self.backlinks.setdefault(target, set()).add(title)

    # ---- retrieval ----

    def resolve(self, name: str) -> str | None:
        return self.alias_index.get(name.lower())

    # Structural/political boilerplate that must never drive a match on its own.
    STOPWORDS = {
        # Bare function words. These were NOT stopworded and scored as RARE
        # distinctive tokens: "from" carried idf 4.9, so one alias containing
        # it outranked a genuine tennis note on "will the player withdraw
        # FROM the tournament". A preposition must never be evidence.
        "from", "into", "onto", "over", "under", "than", "that", "this",
        "these", "those", "their", "there", "been", "being", "have", "has",
        "was", "were", "are", "its",
        "the", "and", "for", "with", "new", "senate", "house", "state", "states",
        "race", "races", "county", "district", "political", "politics", "markets",
        "market", "predictive", "pattern", "trading", "polling", "accuracy",
        "pivotal", "controversy", "risk", "vote", "votes", "election", "elections",
        "congress", "primary", "general", "winner", "party", "gov", "governor",
        "rep", "sen", "2024", "2026", "2028", "map", "index", "doctrine", "checklist",
    
        # Interrogatives and generic verbs matched notes on their own:
        # "which round will the bout end" hit a SPACE note via "which" and an
        # EQUITY note via "end" before combat vocabulary was registered.
        "which", "will", "end", "ends", "ended", "does", "did", "how", "what",
        "when", "where", "who", "whom", "why", "than", "then", "into", "onto",
}

    # Google News titles arrive as "Headline text - Publication Name".
    # The publication is not part of the story and actively poisons matching
    # ("- The New York Times" was matching State: New York and PA-10 York).
    _PUBLICATION_SUFFIX = re.compile(r"\s+[-–|]\s+[^-–|]{2,40}$")

    @classmethod
    def clean_headline(cls, title: str) -> str:
        return cls._PUBLICATION_SUFFIX.sub("", title).strip()

    def _tokens(self, s: str) -> list[str]:
        return [
            t for t in re.split(r"[^a-z0-9]+", s.lower())
            if len(t) >= 3 and t not in self.STOPWORDS
        ]

    def _build_idf(self) -> None:
        """Inverse document frequency over note titles/aliases.

        Structural boilerplate ('state', 'district', 'pattern', 'markets')
        appears in most titles -> near-zero weight. Rare proper nouns
        ('miller', 'sayed', 'maricopa') -> high weight. This is what makes
        seed matching precise instead of matching everything.
        """
        import math
        self._doc_tokens: dict[str, set[str]] = {}
        df: dict[str, int] = {}
        for title, note in self.notes.items():
            toks: set[str] = set()
            for key in {title, note.path.stem, *note.aliases}:
                toks.update(self._tokens(key))
            self._doc_tokens[title] = toks
            for t in toks:
                df[t] = df.get(t, 0) + 1
        n = max(len(self.notes), 1)
        self._idf = {t: math.log(n / (1 + c)) for t, c in df.items()}

    # A match must contain at least one token this distinctive (appears in
    # roughly <=3 of ~130 notes). Prevents a headline matching a note purely
    # via common words shared across many notes.
    # ~<=9 of 130 notes. Low enough that a state name ("georgia") still
    # selects its notes; the STOPWORDS list separately blocks boilerplate.
    MIN_RARE_TOKEN_IDF = 2.5

    def seed_search(self, text: str, limit: int = 6, min_score: float = 2.5) -> list[str]:
        """Find notes whose distinctive title tokens appear in the text.

        IDF-weighted, and gated on at least one genuinely rare token, so
        'Taylor Swift' can't match four states via the word 'New'.
        """
        if not hasattr(self, "_idf"):
            self._build_idf()
        text = self.clean_headline(text)
        text_tokens = set(self._tokens(text))
        if not text_tokens:
            return []
        headline_domains = self._headline_domains(self._domain_tokens(text))
        scored: list[tuple[float, str]] = []
        for title, toks in self._doc_tokens.items():
            overlap = toks & text_tokens
            if not overlap:
                continue
            idfs = [self._idf.get(t, 0.0) for t in overlap]
            if max(idfs) < self.MIN_RARE_TOKEN_IDF:
                continue                      # no distinctive token -> not a real match
            score = (sum(idfs) * self._subject_weight(title)
                     * self._domain_weight(title, headline_domains))
            if score >= min_score:
                scored.append((score, title))
        scored.sort(reverse=True)
        return [t for _, t in scored[:limit]]

    # A note about a SUBJECT (a race, a contract, a state) outranks a note
    # about a METHOD (a trading pattern, a doctrine) on equal token evidence.
    # A pattern note is a lens for reading a subject, not the thing the
    # headline is about. Without this, "NYC heat wave" matched
    # "Pattern: Midterm Moderate Wave Against Populist Incumbent" ahead of the
    # NYC temperature market on the single shared token "wave" -- and the
    # judge prompt then carried midterm-backlash analysis for a weather
    # contract. Cross-domain collisions like that only get more likely as
    # non-political markets are added.
    # ---- domain disambiguation -------------------------------------------
    # Place names collide across verticals: "Washington" is an MLB club AND a
    # state note, "Colorado" likewise. Token-IDF alone sent
    # "Washington at Texas tonight" to State: Washington - Predictive Markets,
    # putting political context in a baseball prompt.
    #
    # Fix: if a headline carries vocabulary that only one domain uses, prefer
    # notes tagged with that domain and demote notes tagged with a DIFFERENT
    # detected domain. When no marker fires, ranking is unchanged.
    #
    # Each new vertical registers its markers here. Keep them unambiguous --
    # a token that appears in two domains belongs in neither list.
    DOMAIN_MARKERS: dict[str, frozenset] = {
        # League sub-markers. MLB, NBA, NFL and soccer all map to the `sports`
        # family, so the family alone cannot separate them -- and once several
        # leagues are modelled, generic vocabulary ("season", "wins", "games")
        # is shared by all of them. These are the words only ONE league uses.
        "mlb": frozenset({
            "inning", "innings", "pitcher", "pitchers", "bullpen", "strikeout",
            "strikeouts", "homer", "homers", "rbi", "doubleheader", "batter",
            "batting", "pitching", "shutout", "baseball", "mlb",
        }),
        "nba": frozenset({
            "rebound", "rebounds", "assists", "dunk", "three-pointer",
            "freethrow", "basketball", "nba", "courtside", "tipoff",
        }),
        "combat": frozenset({
            "knockout", "submission", "octagon", "bout", "undercard",
            "welterweight", "lightweight", "heavyweight", "middleweight",
            "featherweight", "bantamweight", "ufc", "mma", "boxing", "tko",
        }),
        "hockey": frozenset({
            "puck", "goalie", "powerplay", "faceoff", "shootout", "nhl",
            "hockey", "icing", "crease", "zamboni",
        }),
        "equities": frozenset({
            "nasdaq", "equities", "equity", "ticker", "premarket",
            "aftermarket", "earnings", "dividend", "shareholder",
        }),
        "props": frozenset({
            # DELIBERATELY NARROW. An earlier version included "leads",
            # "leader", "starter" and "passer"; those are generic sports words
            # and they stole "NBA rebounds and assists LEADER this season" for
            # the props cluster and "will the PLAYER withdraw" from tennis.
            # Only vocabulary unique to a player-participation contract:
            "prop", "props", "lineup", "lineups", "scratched", "benched",
            "statline", "pinch",
        }),
        "transport": frozenset({
            # NOTE: bare "flight"/"flights" are deliberately ABSENT -- they are
            # ambiguous between aviation and SPACEflight, and including them
            # routed "When will Starship flight test 14 launch" to the airport
            # throughput ladder. "airport"/"airline"/"jfk" carry the aviation
            # sense without the collision.
            "airport", "airline", "airlines", "cancelled",
            "cancellation", "cancellations", "freight", "trucking", "truckload",
            "rail", "transit", "cargo", "port", "tsa", "faa", "jfk", "lax",
            "shipping", "logistics", "throughput", "waymo",
        }),
        "health": frozenset({
            # NOTE: "who" is deliberately ABSENT. It is an interrogative that
            # appears in a large share of all market headlines ("who will
            # win..."), and domain tokens intentionally keep stopwords, so
            # including it would route the whole board to public health.
            "cdc", "fda", "ecdc", "flu", "influenza", "outbreak", "epidemic",
            "pandemic", "vaccine", "vaccination", "hospitalization", "measles",
            "disease", "surveillance", "epidemiological", "fluview", "iqvia",
        }),
        "sovereign": frozenset({
            "conclave", "pope", "papal", "papacy", "parliament", "treaty",
            "sanctions", "referendum", "sovereign", "cptpp", "brexit",
            "confidence", "accession", "junta", "coup",
        }),
        "company": frozenset({
            "layoff", "layoffs", "workforce", "antitrust", "lawsuit",
            "bankruptcy", "pacer", "subsidiary", "rebrand", "recall",
            "ceo", "executive", "executives", "boardroom", "headquarters",
            "carbonarc", "storefront", "foldable",
        }),
        "screen": frozenset({
            "oscar", "oscars", "emmy", "emmys", "grammy", "grammys", "academy",
            "tomatometer", "tomatoes", "metacritic", "nomination", "nominee",
            "nominated", "ceremony", "film", "films", "movie", "movies",
            "cast", "casting", "actor", "actress", "director", "screenplay",
            "netflix", "boxoffice", "sequel", "franchise", "documentary",
        }),
        "music": frozenset({
            "song", "songs", "album", "albums", "billboard", "spotify",
            "streams", "streaming", "artist", "artists", "chart", "charts",
            "single", "singles", "tracklist", "luminate", "riaa", "vinyl",
            "hot100", "discography", "setlist", "coachella",
        }),
        "golf": frozenset({
            "golf", "golfer", "pga", "lpga", "birdie", "birdies", "bogey",
            "eagle", "fairway", "putt", "putting", "caddie", "tee",
            "masters", "ryder", "tournament's", "links", "clubhouse",
        }),
        "tennis": frozenset({
            "tennis", "atp", "wta", "serve", "ace", "aces", "deuce",
            "forehand", "backhand", "baseline", "tiebreak", "wimbledon",
            "roland", "garros", "slam", "singles", "doubles", "racquet",
            "alcaraz", "djokovic", "sinner", "swiatek", "sabalenka",
        }),
        "college": frozenset({
            "ncaa", "ncaaf", "ncaab", "collegiate", "conference",
            "heisman", "bowl", "sec", "acc", "bigten", "pac", "campus",
        }),
        "motorsport": frozenset({
            "nascar", "formula", "grid", "pitstop", "podium", "lap", "laps",
            "qualifying", "pole", "chequered", "checkered", "driver",
            "drivers", "circuit", "motorsport", "paddock",
        }),
        "nfl": frozenset({
            "touchdown", "touchdowns", "quarterback", "interception",
            "fumble", "punt", "football", "nfl", "yardage", "kickoff",
        }),
        "sports": frozenset({
            "inning", "innings", "pitcher", "pitchers", "bullpen", "lineup",
            "strikeout", "strikeouts", "homer", "homers", "rbi", "doubleheader",
            "playoffs", "postseason", "pennant", "roster", "manager", "dugout",
            "shutout", "walkoff", "series", "underdog", "matchup", "standings",
            "mvp", "rookie", "batter", "batting", "pitching", "scoreless",
        }),
        "weather": frozenset({
            "temperature", "temperatures", "forecast", "degrees", "heat",
            "snowfall", "rainfall", "humidity", "hurricane", "blizzard",
            # geophysical: the weather vertical covers quakes and eruptions,
            # and their place names collide with the 50 political state notes
            # ("magnitude 8 earthquake in California" pulled the state note).
            "earthquake", "magnitude", "epicenter", "seismic", "eruption",
            "volcano", "tsunami", "tornado", "precipitation", "meteorological",
        }),
        "economics": frozenset({
            "cpi", "inflation", "bls", "gdp", "payrolls", "unemployment",
            "disinflation", "deflation", "fomc",
        }),
        "politics": frozenset({
            "primary", "election", "electoral", "governor", "senate", "nominee",
            "ballot", "incumbent", "caucus", "midterm", "congressional",
            "candidacy", "recount", "certification",
            # governance, not elections -- the live category is majority
            # tariffs/bills/SCOTUS/pardons and none of it was reachable
            "pardon", "pardons", "commutation", "impeachment", "impeach",
            "tariff", "tariffs", "scotus", "legislation", "statute",
            "supreme", "justice", "confirmation", "nominee", "nominated",
            "shutdown", "appropriations", "filibuster", "veto",
        }),
    }
    # A domain tag on a note maps to one marker family.
    DOMAIN_TAG_FAMILY: dict[str, str] = {
        # A league tag maps to its OWN family so league markers can separate
        # them; `sports` stays the fallback for shared vocabulary.
        "sports": "sports", "mlb": "mlb", "nba": "nba", "nfl": "nfl",
        "nhl": "hockey", "hockey": "hockey", "combat": "combat",
        "college": "college", "ncaa": "college",
        "motorsport": "motorsport", "f1": "motorsport", "nascar": "motorsport",
        "equities": "equities",
        "soccer": "sports", "golf": "golf", "pga": "golf",
        "music": "music", "screen": "screen", "film": "screen",
        "company": "company", "corporate": "company",
        "props": "props",
        "transport": "transport", "logistics": "transport",
        "health": "health", "sovereign": "sovereign", "world": "sovereign",
        "tennis": "tennis", "atp": "tennis", "wta": "tennis",
        "weather": "weather", "climate": "weather",
        "economics": "economics", "cpi": "economics",
        # the family names themselves must map, or a note tagged plainly
        # `politics` / `sports` falls through and escapes the mismatch penalty
        "politics": "politics", "election": "politics", "elections": "politics",
        "race": "politics", "state": "politics", "district": "politics",
        "county": "politics", "polling": "politics", "governor": "politics",
        "senate": "politics", "house": "politics", "primary": "politics",
    }
    DOMAIN_MATCH_BOOST = 1.6
    DOMAIN_MISMATCH_PENALTY = 0.35

    def _domain_tokens(self, s: str) -> set[str]:
        """Tokens for DOMAIN DETECTION -- stopwords deliberately kept.

        `_tokens` strips words that are boilerplate in NOTE TITLES, which is
        right for matching a note and wrong for spotting a subject area. The
        politics layer titles every note `Race: ...` / `State: ...`, so
        "senate", "governor", "election" and "primary" were all stopworded --
        and those are exactly the words DOMAIN_MARKERS["politics"] looks for.
        Sharing one tokenizer therefore made all four markers unreachable:
        "Senate race in Georgia" detected NO domain, took no politics boost,
        and lost to an equities note. 111 political notes were affected.

        Distinctiveness and vocabulary are different questions. This asks the
        second one.
        """
        return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if len(t) >= 3}

    def _headline_domains(self, tokens: set[str]) -> set[str]:
        """Which domain families does this headline's vocabulary point at?"""
        return {fam for fam, marks in self.DOMAIN_MARKERS.items()
                if tokens & marks}

    def _note_domains(self, title: str) -> set[str]:
        """EVERY domain family a note belongs to, not just the first tag.

        A note can honestly sit in two families. KXMLBHR is a player prop AND
        an MLB contract, and returning only the first matching tag meant an
        MLB headline ("will the batter hit a home run") saw the props note as
        a MISMATCH and demoted it to 0.35x -- losing it to an AI note that
        merely shared the word "hit".
        """
        note = self.notes.get(title)
        if not note:
            return set()
        fams = {fam for fam in
                (self.DOMAIN_TAG_FAMILY.get(t.lower()) for t in note.tags)
                if fam}
        # Drop the GENERIC parent when a specific one is present. Every league
        # note also carries a literal `sports` tag, so keeping both would let
        # any sports headline match any league note -- which is exactly the
        # leak that sent an NFL MVP headline to a College note. A note is
        # "generic sports" only if it claims no league of its own.
        specific = {f for f in fams if f in self.DOMAIN_PARENTS}
        return specific or fams

    def _note_domain(self, title: str) -> str | None:
        """First family only. Kept for callers that want a single label."""
        for t in (x.lower() for x in self.notes[title].tags) \
                if title in self.notes else ():
            fam = self.DOMAIN_TAG_FAMILY.get(t)
            if fam:
                return fam
        return None

    # `sports` is a PARENT of the league families. A headline carrying only
    # generic sports vocabulary must not penalise a league-tagged note --
    # giving MLB/NBA/NFL their own families made "Rays win the World Series"
    # boost the generic NHL hub (domain `sports`) while demoting the MLB
    # championship note (domain `mlb`) to 0.35x.
    DOMAIN_PARENTS: dict[str, str] = {"mlb": "sports", "nba": "sports",
                                      "nfl": "sports", "hockey": "sports",
                                      "combat": "sports", "college": "sports",
                                      "motorsport": "sports", "tennis": "sports",
                                      "golf": "sports", "props": "sports"}

    def _domain_matches(self, dom: str, headline_domains: set[str]) -> bool:
        if dom in headline_domains:
            return True
        # The parent boost is for headlines that name NO league -- "Rays win
        # the World Series" carries only generic sports words, so every league
        # note must stay eligible. But once the headline DOES name a league,
        # handing the same boost to rival leagues makes them compete on raw
        # token overlap alone: "Josh Allen ... MVP quarterback" says `nfl`
        # outright and still lost to Market: College Season Wins Ladder,
        # because both notes sat under `sports` and college shared more words.
        parent = self.DOMAIN_PARENTS.get(dom)
        if parent is None or parent not in headline_domains:
            return False
        named = headline_domains & set(self.DOMAIN_PARENTS)
        return not named

    def _domain_weight(self, title: str, headline_domains: set[str]) -> float:
        if not headline_domains:
            return 1.0
        doms = self._note_domains(title)
        if not doms:
            return 1.0
        if any(self._domain_matches(d, headline_domains) for d in doms):
            return self.DOMAIN_MATCH_BOOST
        # Only demote when the note belongs to a domain the headline did NOT
        # signal -- an unclassified note keeps its raw score.
        return self.DOMAIN_MISMATCH_PENALTY

    SUBJECT_TAGS = {"market", "race", "state", "district", "county", "polling"}
    METHOD_TAGS = {"trading-pattern", "pattern", "methodology", "causality",
                   "doctrine", "blueprint", "index", "feature-engineering"}
    METHOD_PENALTY = 0.6

    def _subject_weight(self, title: str) -> float:
        note = self.notes.get(title)
        tags = {t.lower() for t in (note.tags if note else [])}
        if tags & self.SUBJECT_TAGS:
            return 1.0
        if tags & self.METHOD_TAGS:
            return self.METHOD_PENALTY
        return 1.0

    def expand(self, seeds: list[str], hops: int = 1, max_notes: int = 10) -> list[str]:
        """BFS out from seed notes along wikilinks (both directions)."""
        seen = list(dict.fromkeys(seeds))
        frontier = list(seen)
        for _ in range(hops):
            nxt: list[str] = []
            for title in frontier:
                note = self.notes.get(title)
                if not note:
                    continue
                neighbors = [self.resolve(l) for l in note.links]
                neighbors += list(self.backlinks.get(title, ()))
                for n in neighbors:
                    if n and n not in seen:
                        seen.append(n)
                        nxt.append(n)
                        if len(seen) >= max_notes:
                            return seen[:max_notes]
            frontier = nxt
        return seen[:max_notes]

    def retrieve_context(self, text: str, max_notes: int = 6,
                          chars_per_note: int = 900) -> tuple[list[str], str]:
        """Main entry point: text -> (note titles used, formatted context block)."""
        seeds = self.seed_search(text)
        if not seeds:
            return [], ""
        titles = self.expand(seeds, hops=1, max_notes=max_notes)
        blocks = []
        for t in titles:
            note = self.notes.get(t)
            if note:
                blocks.append(f"### {t}\n{note.summary(chars_per_note)}")
        return titles, "\n\n".join(blocks)

    # Map each expert_context slot to the '## ' headers that actually exist in
    # this vault (counted across all 131 notes), best source first. A slot with
    # no matching section is omitted entirely rather than sent as "no info" --
    # an empty labelled field invites the model to invent one.
    #
    # `resolution_source` is now live: race notes carry a '## Resolution Rules'
    # section whose content is derived from Kalshi's own settlement_sources
    # field, not authored from memory. It is listed FIRST so the judge sees the
    # settlement rule before any directional context -- "who calls it, and
    # when" decides more of these contracts than the polling does.
    #
    # Each tuple is tried in order against each note, most-specific header
    # first, so a race-level note beats a state-level one on the same slot.
    CONTEXT_SLOTS: dict[str, tuple[str, ...]] = {
        # `latest_event` is not a '## header' slot -- it is synthesised from the
        # note's Timeline section by expert_context. Listed first so the judge
        # sees how old its evidence is before it reads any of the analysis.
        "latest_event": ("__timeline__",),
        "resolution_source": ("Resolution Rules",),
        "timing_risk": ("Timing Risk",
                        "Reporting Timing & Drop Patterns",
                        "Reporting & Momentum Patterns"),
        "related_markets": ("Related Markets",
                            "Where the Trading Value Is", "Trading Angles",
                            "County Trading Playbook"),
        "historical_analog": ("Historical Analog",
                              "Historical Results (verified)",
                              "Historical Voting Behavior",
                              "Split-Ticket History (Governors vs President)"),
    }

    _SECTION_RE_CACHE: dict[str, re.Pattern] = {}

    @staticmethod
    def _section(body: str, header: str) -> str:
        """Text under a '## header' up to the next '## ', flattened."""
        pat = re.compile(
            r"^##\s+" + re.escape(header) + r"\s*\n(.*?)(?=^##\s|\Z)",
            re.MULTILINE | re.DOTALL)
        m = pat.search(body)
        if not m:
            return ""
        text = m.group(1)
        text = WIKILINK_RE.sub(r"\1", text)             # [[X|y]] -> X
        text = re.sub(r"[*_`>#]", "", text)             # markdown noise
        text = re.sub(r"\s*\n\s*", " ", text)           # flatten
        return re.sub(r"\s{2,}", " ", text).strip()

    def _timeline_fact(self, note: "Note", now=None) -> str:
        """One line describing the age and content of the note's newest
        observation, plus a STALE verdict.

        This is the whole point of the time-series work: a judge told
        "DDHQ avg 37/18/17" with no date cannot tell a poll taken this
        morning from one taken before the early-vote window closed.
        """
        events = parse_timeline(note.body)
        if not events:
            return ""
        st = assess(note.body, now=now)
        newest = events[0]
        age = f"{st.age_hours:.0f}h old" if st.age_hours is not None else "undated"
        head = f"{st.label} ({age}) "
        latest = f"{newest.ts:%Y-%m-%d %H:%M} {newest.kind}: {newest.text}"
        if st.stale:
            return f"{head}- {st.reason}. Newest: {latest}"
        return f"{head}- newest: {latest}"

    def timeline_events(self, title: str) -> list:
        note = self.notes.get(title)
        return parse_timeline(note.body) if note else []

    def staleness(self, title: str, **kw):
        note = self.notes.get(title)
        return assess(note.body, **kw) if note else None

    def expert_context(self, titles: list[str], max_chars: int = 800,
                        per_slot: int | None = None, now=None) -> dict[str, str]:
        """Compress ranked notes into a few short expert facts.

        `titles` must already be relevance-ordered (seed_search does this).
        Returns only slots that were actually found; an empty dict means the
        caller should inject nothing at all.

        Budgeting: each slot gets an equal share of `max_chars` and any share a
        slot does not spend rolls forward to later slots. A fixed per-slot
        allowance instead let the first two slots eat the whole budget, so
        `related_markets` and `historical_analog` silently never appeared --
        the prompt looked complete while quietly dropping half the evidence.
        Pass `per_slot` to pin the old fixed-width behaviour.
        """
        out: dict[str, str] = {}
        slots = self.CONTEXT_SLOTS
        # `max_chars` is a promise about the PROMPT, so charge the budget for
        # the wrapper text too: the header plus one label line per slot.
        # Budgeting the bare facts instead let a 4-slot result render at 898
        # chars under a nominal 800 cap.
        overhead = len(CONTEXT_HEADER) + sum(
            len(SLOT_LABELS.get(k, k)) + 3 for k in slots)
        budget = max(120, max_chars - overhead)
        share = per_slot or max(80, budget // max(1, len(slots)))
        for i, (slot, headers) in enumerate(slots.items()):
            remaining_slots = len(slots) - i
            # never spend more than this slot's fair share of what is left.
            # `budget - 2` reserves the separator, without which the final
            # slot was rejected for overshooting by exactly those 2 chars.
            spendable = max(0, budget - 2)
            if remaining_slots == 1:
                allowance = min(share, spendable)
            else:
                allowance = min(share, spendable // remaining_slots + share // 2)
            if allowance <= 0:
                continue
            for title in titles:                        # best-matching note first
                note = self.notes.get(title)
                if not note:
                    continue
                for header in headers:
                    if header == "__timeline__":
                        text = self._timeline_fact(note, now=now)
                    else:
                        text = self._section(note.body, header)
                    if not text:
                        continue
                    # Titles run ~56 chars; repeating one across four slots
                    # spends a quarter of the budget on the same string.
                    short = title if len(title) <= 30 else title[:29].rstrip() + "…"
                    label = f"[{short}] "
                    # reserve the ellipsis a truncated snippet appends, or
                    # every entry overshoots its allowance by len(ELLIPSIS)
                    room = allowance - len(label) - len(_ELLIPSIS)
                    if room < 40:                       # too little to say anything
                        continue
                    snippet = text[:room].rstrip()
                    if len(text) > room:
                        snippet += _ELLIPSIS
                    entry = label + snippet
                    if len(entry) + 2 > budget:
                        continue                        # try a shorter source
                    out[slot] = entry
                    budget -= len(entry) + 2
                    break
                if slot in out:
                    break
        return out

    def stats(self) -> dict:
        edges = sum(len(n.links) for n in self.notes.values())
        return {
            "notes": len(self.notes),
            "aliases": len(self.alias_index),
            "outbound_links": edges,
            "notes_with_backlinks": len(self.backlinks),
        }
