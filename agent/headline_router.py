"""Headline -> (tradeable series, vault context), in microseconds, or nothing.

TWO STAGES, BECAUSE THERE ARE TWO KINDS OF HEADLINE.

  1. ENTITY headlines name a thing Kalshi lists: "Yankees", "Chiefs",
     "Frances Tiafoe". The vault cannot route these -- its notes are titled
     by market structure ("Vertical: MLB Pro Baseball") and the word
     "Yankees" appears in zero note titles, aliases or bodies. These route
     through `EntityIndex`, harvested from the API.

  2. SUBJECT headlines name the thing the note itself is about: "Bitcoin",
     "CPI", "Fed", "Hurricane". Here the vault's own token search already
     works, because the subject IS the note title. Crypto proves the split
     cleanly: every crypto subtitle is a price strike ("$50,000 or above"),
     so the entity index contains no crypto entities at all -- and it does
     not need to, because "Bitcoin" is in the note title.

Neither stage is a fallback for the other. They cover disjoint vocabulary,
which is why running both and taking whichever fires beats either alone.

ABSTENTION IS THE THIRD OUTCOME AND IT IS NOT A FAILURE. On a labelled set,
the vault alone answered 2 of 3 headlines that Kalshi lists no market for --
"local bakery wins award" routed to the Screen Award Winner Field on the word
"award". A confident wrong context block on a headline is worse than silence,
because the whole point of retrieving context is to size a trade with it.

LATENCY: the entity index loads from a 20 KB JSON cache; the vault loads in
~51ms. Both are process-start costs. Per-headline routing is dict access and
set intersection -- microseconds, thousands of times faster than the seconds
a headline gives you before the book moves. Speed was never the constraint
here; precision was.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from agent.entity_index import EntityIndex

DEFAULT_INDEX_PATH = Path("state/_entity_index.json")

# Series whose hub note cannot be derived from the vault because no note text
# mentions the ticker. Each is an explicit editorial decision, not a guess:
# the series obviously belongs to that cluster, and saying so here is honest
# about it being asserted rather than measured.
_EXPLICIT_HUB: dict[str, str] = {
    "KXMLBSPREAD": "Vertical: MLB Pro Baseball",
    "KXNBAGAME": "Vertical: NBA Pro Basketball",
    "KXEPLGAME": "Vertical: European Club Soccer",
    # WNBA is filed under the NBA hub. The vault's NBA note explicitly
    # EXCLUDES 88 WNBA series as substring false positives, so this is a
    # known imperfect home rather than a clean match -- flagged so a future
    # reader does not mistake it for a derived mapping.
    "KXWNBAGAME": "Vertical: NBA Pro Basketball",
}


@dataclass
class Route:
    """What a headline resolved to. Every field may be empty."""
    headline: str
    series: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    context: str = ""
    stage: str = "none"          # "entity" | "subject" | "both" | "none"

    @property
    def actionable(self) -> bool:
        """True only when a TRADEABLE series was identified.

        Vault context without a series is background reading, not a trade.
        """
        return bool(self.series)


class HeadlineRouter:
    def __init__(self, vault_graph, entity_index: EntityIndex | None = None,
                 index_path: Path | None = None):
        self.graph = vault_graph
        if entity_index is not None:
            self.index = entity_index
        else:
            p = Path(index_path or DEFAULT_INDEX_PATH)
            self.index = EntityIndex.load(p) if p.exists() else EntityIndex()
        self._hub_for_series = self._derive_hub_map()

    def _derive_hub_map(self) -> dict[str, str]:
        """series ticker -> the note that best covers it, read from the vault.

        Derived rather than hand-written: a note naming KXNFLGAME in its text
        is evidence it covers that series, and evidence beats an author's
        memory. `_EXPLICIT_HUB` fills only what no note mentions at all.

        RANKED BY HOW STRONGLY A NOTE CLAIMS THE SERIES, not by title length.
        A note whose TITLE carries the ticker is about that series; a note
        whose body merely mentions it may only be cross-referencing. Searching
        hubs first and falling back afterwards was wrong for the same reason:
        "Vertical: Corporate Events" cites CPI in passing, so KXCPIYOY resolved
        there and never reached "Market: KXCPIYOY US CPI Year-over-Year".
        """
        out: dict[str, str] = {}
        for series in self.index.series_seen:
            WB = chr(92) + "b"   # a literal ; writing it inline has twice
            # been mangled into a backspace byte by tooling escapes
            pat = re.compile(WB + re.escape(series) + WB)
            found = [t for t, n in self.graph.notes.items()
                     if pat.search((n.body or "") + " " + t)]
            if found:
                def rank(t: str) -> tuple[int, int, int]:
                    return (0 if pat.search(t) else 1,      # ticker in title
                            0 if t.startswith("Vertical:") else 1,  # hub
                            len(t))
                out[series] = min(found, key=rank)
        for series, hub in _EXPLICIT_HUB.items():
            out.setdefault(series, hub)
        return out

    def route(self, headline: str, max_notes: int = 4) -> Route:
        r = Route(headline=headline)

        series = self.index.series_for(headline)
        entity_notes: list[str] = []
        for s in series:
            hub = self._hub_for_series.get(s)
            if hub and hub not in entity_notes:
                entity_notes.append(hub)

        subject_notes, subject_ctx = self.graph.retrieve_context(
            headline, max_notes=max_notes)

        if series and subject_notes:
            r.stage = "both"
        elif series:
            r.stage = "entity"
        elif subject_notes:
            r.stage = "subject"
        else:
            return r

        r.series = series
        # Entity hubs first: a named team is harder evidence than a token
        # overlap, so its note should lead the context block.
        seen = set()
        ordered = []
        for t in entity_notes + list(subject_notes):
            if t not in seen:
                seen.add(t)
                ordered.append(t)
        r.notes = ordered[:max_notes]

        blocks = []
        for t in r.notes:
            note = self.graph.notes.get(t)
            if note:
                blocks.append(f"### {t}\n{note.summary(900)}")
        r.context = "\n\n".join(blocks)
        return r

    def route_strict(self, headline: str, max_notes: int = 4) -> Route:
        """Route, but return nothing unless a TRADEABLE series was found.

        This is the mode a live trader should use. The subject stage alone
        proves a headline is topically related to some market cluster; it does
        not prove there is an order to place. Strict mode refuses to hand back
        context that cannot be acted on, which is what stopped "local bakery
        wins award" from producing an award-market context block.
        """
        r = self.route(headline, max_notes=max_notes)
        if not r.actionable:
            return Route(headline=headline)
        return r
