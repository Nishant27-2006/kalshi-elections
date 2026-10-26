"""Market -> knowledge chunks, with a hard as-of cutoff.

Chunks are single dated claims (see knowledge/politics/_FORMAT.md), dated
Timeline lines, and one header chunk per file (title + aliases + tags + the
one-line scope, dated at the file's `created`). A query at decision time T can
only return chunks with as_of < T, so a backtest never reads anything written
about the future.

Scoring is BM25 (no embeddings, no network). Options switch on one change at a
time so recall@5 can be measured before and after each.
"""
from __future__ import annotations

import glob
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE = os.path.join(ROOT, "knowledge")

TAG_RE = re.compile(r"\(as_of:\s*(\d{4}-\d{2}-\d{2})\s*;\s*source:\s*([^)]*)\)\s*$")
TL_RE = re.compile(r"^(?:-\s*)?\[(\d{4}-\d{2}-\d{2})[^\]]*\]\s*(.*)$")
TOKEN_RE = re.compile(r"[a-z0-9]+")

STATES = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas", "CA": "california",
    "CO": "colorado", "CT": "connecticut", "DE": "delaware", "FL": "florida", "GA": "georgia",
    "HI": "hawaii", "ID": "idaho", "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas",
    "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland", "MA": "massachusetts",
    "MI": "michigan", "MN": "minnesota", "MS": "mississippi", "MO": "missouri", "MT": "montana",
    "NE": "nebraska", "NV": "nevada", "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico",
    "NY": "new york", "NC": "north carolina", "ND": "north dakota", "OH": "ohio", "OK": "oklahoma",
    "OR": "oregon", "PA": "pennsylvania", "RI": "rhode island", "SC": "south carolina",
    "SD": "south dakota", "TN": "tennessee", "TX": "texas", "UT": "utah", "VT": "vermont",
    "VA": "virginia", "WA": "washington", "WV": "west virginia", "WI": "wisconsin", "WY": "wyoming",
}
OFFICE_WORDS = {"SENATE": "senate", "GOV": "governor", "HOUSE": "house", "MAYOR": "mayor",
                "PRES": "president presidential", "NOM": "nominee nomination", "CONTROL": "control"}
STOP = set("the a an of to in on for will be is and or by at with which who what when how this that "
           "market resolves yes no if as are from than any before after".split())


def tokens(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOP and len(t) > 1]


def _date(s) -> float:
    if s is None:
        return 0.0
    if hasattr(s, "isoformat"):
        s = s.isoformat()
    return datetime.fromisoformat(str(s)[:10]).replace(tzinfo=timezone.utc).timestamp()


@dataclass
class Chunk:
    file: str
    text: str
    as_of: float
    kind: str              # claim | timeline | header
    source: str = ""
    title: str = ""
    markets: list = field(default_factory=list)


def _split_frontmatter(raw: str):
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end > 0:
            try:
                fm = yaml.safe_load(raw[3:end]) or {}
            except yaml.YAMLError:
                fm = {}
            return fm, raw[end + 4:]
    return {}, raw


def load_chunks(root: str = KNOWLEDGE) -> list[Chunk]:
    out: list[Chunk] = []
    for path in sorted(glob.glob(os.path.join(root, "**", "*.md"), recursive=True)):
        name = os.path.relpath(path, root).replace("\\", "/")
        if os.path.basename(path).startswith("_") or "/data/" in name:
            continue
        with open(path, encoding="utf-8") as fh:
            fm, body = _split_frontmatter(fh.read())
        title = ""
        m = re.search(r"^#\s+(.+)$", body, re.M)
        if m:
            title = m.group(1).strip()
        aliases = " ".join(fm.get("aliases") or [])
        tags = " ".join(str(t) for t in (fm.get("tags") or []))
        markets = [str(x) for x in (fm.get("markets") or [])]
        created = _date(fm.get("created") or fm.get("as_of") or "2026-10-09")
        scope = ""
        for line in body.splitlines():
            s = line.strip()
            if s and not s.startswith(("#", "Back to", "-", "[")):
                scope = s
                break
        out.append(Chunk(name, f"{title} {aliases} {tags} {scope}", created, "header", "", title, markets))
        for line in body.splitlines():
            s = line.strip()
            tm = TAG_RE.search(s)
            if s.startswith("-") and tm:
                text = TAG_RE.sub("", s).lstrip("- ").strip()
                out.append(Chunk(name, text, _date(tm.group(1)), "claim", tm.group(2).strip(), title, markets))
                continue
            tl = TL_RE.match(s)
            if tl:
                out.append(Chunk(name, tl.group(2), _date(tl.group(1)), "timeline", "", title, markets))
    return out


STATE_MECHANICS = {"AK": "ranked choice voting rcv", "ME": "ranked choice voting rcv",
                   "GA": "runoff 50 percent", "LA": "runoff jungle primary",
                   "CA": "top two primary", "WA": "top two primary"}


def concept_terms(title: str, ticker: str, states: list[str]) -> str:
    """Election-mechanics vocabulary implied by the contract, so the matching
    mechanics / base-rate notes compete with the race note."""
    t = title.lower()
    candidate_race = any(w in t for w in ("winner", "senate", "governor", "mayor", "house", "elect"))
    extra = [STATE_MECHANICS[s] for s in states if s in STATE_MECHANICS] if candidate_race else []
    if "primary" in t or "runoff" in t or "nominee" in t:
        extra.append("primary incumbent loss endorsement base rate runoff reversal")
    if "margin" in t or "vote percent" in t:
        extra.append("polling error margin")
    return " ".join(extra)


def _states(title: str, ticker: str) -> list[str]:
    head = ticker.upper().split("-")[0]
    head = head[2:] if head.startswith("KX") else head
    out = []
    for code, name in STATES.items():
        if (head.endswith(code) or re.search(r"\b" + code + r"\b", title)
                or re.search("-" + code + r"\d", ticker.upper()) or name in title.lower()):
            out.append(code)
    return out


def expand_query(title: str, rules: str, ticker: str, concepts: bool = False) -> str:
    """Spell out what tickers abbreviate: SENATETX -> senate texas."""
    extra = []
    head = ticker.upper().split("-")[0]
    head = head[2:] if head.startswith("KX") else head
    for k, v in OFFICE_WORDS.items():
        if k in head:
            extra.append(v)
    for code, name in STATES.items():
        if head.endswith(code) or re.search(rf"\b{code}\b", title) or re.search(rf"-{code}\d", ticker.upper()):
            extra.append(name)
    year = re.search(r"-(\d{2})(?:[A-Z]{3}\d{2})?\b", ticker.upper())
    if year:
        extra.append("20" + year.group(1))
    if concepts:
        extra.append(concept_terms(title, ticker, _states(title, ticker)))
    return " ".join([title, rules, " ".join(extra)])


class Retriever:
    def __init__(self, chunks: list[Chunk] | None = None, *, title_boost: bool = True,
                 expand: bool = True, ticker_match: bool = True, per_file_cap: int | None = 2,
                 concepts: bool = False,
                 k1: float = 1.2, b: float = 0.75):
        self.chunks = chunks if chunks is not None else load_chunks()
        self.title_boost, self.expand, self.ticker_match = title_boost, expand, ticker_match
        self.per_file_cap, self.k1, self.b = per_file_cap, k1, b
        self.concepts = concepts
        self.docs = []
        for c in self.chunks:
            text = c.text
            if title_boost:
                text = f"{c.title} {c.title} {text}"   # each chunk carries its note's title, x2
            self.docs.append(Counter(tokens(text)))
        self.N = len(self.docs)
        self.avgdl = sum(sum(d.values()) for d in self.docs) / max(self.N, 1)
        df = Counter()
        for d in self.docs:
            df.update(d.keys())
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def _bm25(self, q: list[str], i: int) -> float:
        d = self.docs[i]
        dl = sum(d.values())
        s = 0.0
        for t in q:
            f = d.get(t)
            if f:
                s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return s

    def search(self, title: str, rules: str = "", ticker: str = "", as_of: float | None = None,
               k: int = 5) -> list[tuple[float, Chunk]]:
        text = expand_query(title, rules, ticker, self.concepts) if self.expand else f"{title} {rules}"
        q = tokens(text)
        tick = ticker.upper()
        scored = []
        for i, c in enumerate(self.chunks):
            if as_of is not None and c.as_of >= as_of:
                continue
            s = self._bm25(q, i)
            if self.ticker_match and tick and any(tick.startswith(m.upper()) or m.upper().startswith(tick.split("-")[0] + "-")
                                                  or m.upper() == tick.split("-")[0] for m in c.markets):
                s += 25.0
            if s > 0:
                scored.append((s, c))
        scored.sort(key=lambda x: -x[0])
        if not self.per_file_cap:
            return scored[:k]
        out, per = [], defaultdict(int)
        for s, c in scored:
            if per[c.file] >= self.per_file_cap:
                continue
            per[c.file] += 1
            out.append((s, c))
            if len(out) == k:
                break
        return out
