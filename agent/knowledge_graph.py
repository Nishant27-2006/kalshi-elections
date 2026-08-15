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
        "the", "and", "for", "with", "new", "senate", "house", "state", "states",
        "race", "races", "county", "district", "political", "politics", "markets",
        "market", "predictive", "pattern", "trading", "polling", "accuracy",
        "pivotal", "controversy", "risk", "vote", "votes", "election", "elections",
        "congress", "primary", "general", "winner", "party", "gov", "governor",
        "rep", "sen", "2024", "2026", "2028", "map", "index", "doctrine", "checklist",
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
        scored: list[tuple[float, str]] = []
        for title, toks in self._doc_tokens.items():
            overlap = toks & text_tokens
            if not overlap:
                continue
            idfs = [self._idf.get(t, 0.0) for t in overlap]
            if max(idfs) < self.MIN_RARE_TOKEN_IDF:
                continue                      # no distinctive token -> not a real match
            score = sum(idfs)
            if score >= min_score:
                scored.append((score, title))
        scored.sort(reverse=True)
        return [t for _, t in scored[:limit]]

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

    def stats(self) -> dict:
        edges = sum(len(n.links) for n in self.notes.values())
        return {
            "notes": len(self.notes),
            "aliases": len(self.alias_index),
            "outbound_links": edges,
            "notes_with_backlinks": len(self.backlinks),
        }
