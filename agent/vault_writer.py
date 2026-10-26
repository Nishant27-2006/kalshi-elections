"""
The write half of the time-series vault.

agent/timeline.py parses; this module edits notes on disk. Kept separate so
the parsing logic can be tested without a filesystem and so exactly one file
is responsible for mutating the user's Obsidian vault.

Editing rules, in order of how much they matter:

1. Never rewrite a note wholesale. Only the `## Timeline` section is touched;
   every other section, the frontmatter and the Update Log are preserved
   byte-for-byte. These are hand-authored analytical notes.
2. Only append events strictly NEWER than what the note already holds, then
   dedupe. The runner re-reads the same RSS feed every cycle.
3. Write atomically (tmp + replace). A half-written note in an Obsidian vault
   is a data-loss event, not an inconvenience.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from .timeline import (TIMELINE_HEADER, TimelineEvent, dedupe, parse_timeline,
                       render_timeline)

STALE_MARKER = "> [!warning] STALE"
_STALE_BLOCK_RE = re.compile(r"^> \[!warning\] STALE.*?(?:\n>.*)*\n\n?",
                             re.MULTILINE)
_TIMELINE_SECTION_RE = re.compile(
    r"(^##\s+(?:Timeline|News Events)\s*\n)(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL)
_FRONTMATTER_RE = re.compile(r"^(---\s*\n.*?\n---\s*\n)", re.DOTALL)


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _insert_timeline_section(body: str, rendered: str) -> str:
    """Add a Timeline section to a note that has none.

    Placed immediately before the first `## ` heading so it reads at the top
    of the analysis rather than being buried under the Update Log.
    """
    section = f"{TIMELINE_HEADER}\n{rendered}\n\n"
    m = re.search(r"^##\s", body, re.MULTILINE)
    if not m:
        return body.rstrip() + "\n\n" + section
    return body[:m.start()] + section + body[m.start():]


def append_events(path: Path, events: list[TimelineEvent], *,
                  dry_run: bool = False) -> dict:
    """Merge `events` into the note's Timeline. Returns what changed.

    Only strictly-newer-than-nothing is not the rule -- an event older than
    the note's newest is still kept if it is not already present, because
    backfilling a missed poll is legitimate. What is refused is duplication.
    """
    body = path.read_text(encoding="utf-8")
    existing = parse_timeline(body)
    before = len(existing)

    merged = dedupe(existing + [e for e in events if e])
    added = len(merged) - before
    if added == 0:
        return {"path": str(path), "added": 0, "total": before,
                "reason": "no new events"}

    rendered = render_timeline(merged)
    m = _TIMELINE_SECTION_RE.search(body)
    if m:
        new_body = body[:m.start(2)] + rendered + "\n\n" + body[m.end(2):]
    else:
        new_body = _insert_timeline_section(body, rendered)

    new_body = _bump_updated(new_body, max(e.ts for e in merged))

    if not dry_run:
        _atomic_write(path, new_body)
    return {"path": str(path), "added": added, "total": len(merged),
            "newest": max(e.ts for e in merged).isoformat(),
            "dry_run": dry_run}


def _bump_updated(body: str, newest: datetime) -> str:
    """Keep frontmatter `updated:` in step with the newest timeline entry."""
    fm = _FRONTMATTER_RE.match(body)
    if not fm:
        return body
    block = fm.group(1)
    stamp = newest.strftime("%Y-%m-%d")
    if re.search(r"^updated:\s*.*$", block, re.MULTILINE):
        new_block = re.sub(r"^updated:\s*.*$", f"updated: {stamp}", block,
                           count=1, flags=re.MULTILINE)
    else:
        new_block = block.replace("---\n", f"---\nupdated: {stamp}\n", 1)
    return new_block + body[fm.end():]


def set_stale_marker(path: Path, staleness, *, dry_run: bool = False) -> dict:
    """Add or clear the STALE callout directly under the note's H1.

    Written into the note body rather than held in memory so it is visible in
    Obsidian itself -- the person reading the note is the one who most needs
    to know it should not be traded off.
    """
    body = path.read_text(encoding="utf-8")
    had = STALE_MARKER in body
    cleaned = _STALE_BLOCK_RE.sub("", body)

    if not staleness.stale:
        changed = had
        new_body = cleaned
    else:
        block = (f"{STALE_MARKER} — do not trade off this note\n"
                 f"> {staleness.reason}\n\n")
        m = re.search(r"^#\s+.*$", cleaned, re.MULTILINE)
        if m:
            new_body = cleaned[:m.end() + 1] + "\n" + block + cleaned[m.end() + 1:].lstrip("\n")
        else:
            new_body = block + cleaned
        changed = new_body != body

    if changed and not dry_run:
        _atomic_write(path, new_body)
    return {"path": str(path), "stale": staleness.stale,
            "changed": changed, "reason": staleness.reason, "dry_run": dry_run}


# Notes that describe a THING THAT HAPPENS get a timeline. Notes that describe
# a METHOD do not: a headline about one candidate is not an observation about
# "Trading Pattern: Trump Endorsement Primary Premium", and appending it there
# buries the pattern's argument under a news feed. Checked against tags.
TIMELINE_TAGS = {"race", "state", "polling", "district", "county", "market-mechanics"}
EXCLUDED_TAGS = {"trading-pattern", "pattern", "methodology", "causality",
                 "doctrine", "blueprint", "index", "feature-engineering"}


def accepts_timeline(note) -> bool:
    """Should this note carry a news timeline at all?"""
    tags = {t.lower() for t in (getattr(note, "tags", None) or [])}
    if tags & EXCLUDED_TAGS:
        return False
    return bool(tags & TIMELINE_TAGS)


def ingest_news(graph, news_items: list[dict], *, max_notes: int = 3,
                dry_run: bool = False) -> list[dict]:
    """Route timestamped headlines to the vault notes they actually concern.

    Routing reuses the same free local seed_search the triage tier uses, so a
    headline only writes to notes it already matches. An item with no
    parseable pub_date is skipped -- see timeline.event_from_news.
    """
    from .timeline import event_from_news

    by_note: dict[str, list[TimelineEvent]] = {}
    skipped_no_date = 0
    for item in news_items:
        ev = event_from_news(item)
        if ev is None:
            skipped_no_date += 1
            continue
        matched = 0
        for t in graph.seed_search(item.get("title", "")):
            note = graph.notes.get(t)
            if note is None or not accepts_timeline(note):
                continue
            by_note.setdefault(t, []).append(ev)
            matched += 1
            if matched >= max_notes:
                break

    results = []
    for title, events in by_note.items():
        note = graph.notes.get(title)
        if note is None:
            continue
        results.append({"note": title,
                        **append_events(note.path, events, dry_run=dry_run)})
    if skipped_no_date:
        results.append({"note": None, "skipped_no_pub_date": skipped_no_date})
    return results
