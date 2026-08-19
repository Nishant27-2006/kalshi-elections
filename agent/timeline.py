"""
Timestamped events inside vault notes.

Political knowledge is a time series, not a fact sheet. A poll average, an
early-vote total, a decision-desk call and a candidate withdrawal are all
observations with a clock time, and a note that records them without one is
indistinguishable from a note that is six weeks stale. Before this module the
vault carried a day-granularity `updated:` field and nothing else, so the
judge prompt could not tell fresh evidence from old.

Wire format inside a note's `## Timeline` section, newest line anywhere in the
section (order is not trusted -- entries are sorted on parse):

    [2026-08-18 14:32] Poll: DDHQ avg 37/18/17
    [2026-08-18 09:00] News: DDHQ warns "significant egg on face"

Pure parsing and formatting. No network, no LLM, no file writes -- the write
path lives in agent/vault_writer.py so this stays trivially testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

TIMELINE_HEADER = "## Timeline"

# [2026-08-18 14:32] Poll: text     (time optional, seconds optional)
ENTRY_RE = re.compile(
    r"^\s*[-*]?\s*\[(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}(?::\d{2})?))?\]\s*"
    r"(?:([A-Za-z][\w /-]{0,24}):\s*)?(.+?)\s*$",
    re.MULTILINE)

SECTION_RE = re.compile(
    r"^##\s+(?:Timeline|News Events)\s*\n(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL)

# Kinds that justify forcing a re-read even when the note looks recent.
MATERIAL_KINDS = {"poll", "returns", "call", "withdrawal", "filing", "ruling"}


@dataclass(frozen=True)
class TimelineEvent:
    ts: datetime
    kind: str          # "Poll", "News", "Returns", ... ("" when unlabelled)
    text: str
    has_time: bool = True   # False when the line carried a date only

    def age(self, now: datetime | None = None) -> timedelta:
        return (now or datetime.now(timezone.utc)) - self.ts

    def render(self) -> str:
        stamp = self.ts.strftime("%Y-%m-%d %H:%M" if self.has_time else "%Y-%m-%d")
        prefix = f"{self.kind}: " if self.kind else ""
        return f"[{stamp}] {prefix}{self.text}"


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_entry(line: str) -> TimelineEvent | None:
    """One '[ts] Kind: text' line -> TimelineEvent, or None if it isn't one."""
    m = ENTRY_RE.match(line.strip())
    if not m:
        return None
    date_s, time_s, kind, text = m.groups()
    stamp = f"{date_s} {time_s}" if time_s else date_s
    fmt = "%Y-%m-%d %H:%M:%S" if (time_s and len(time_s) == 8) else (
        "%Y-%m-%d %H:%M" if time_s else "%Y-%m-%d")
    try:
        ts = _aware(datetime.strptime(stamp, fmt))
    except ValueError:
        return None
    return TimelineEvent(ts=ts, kind=(kind or "").strip(), text=text.strip(),
                         has_time=bool(time_s))


def parse_timeline(body: str) -> list[TimelineEvent]:
    """All events in a note's Timeline section, NEWEST FIRST.

    Sorted on parse rather than trusting file order: notes are edited by hand
    and an appended-at-the-bottom entry is the common case.
    """
    m = SECTION_RE.search(body or "")
    if not m:
        return []
    events = [e for e in (parse_entry(l) for l in m.group(1).splitlines()) if e]
    return sorted(events, key=lambda e: e.ts, reverse=True)


def latest_event(body: str) -> TimelineEvent | None:
    events = parse_timeline(body)
    return events[0] if events else None


def render_timeline(events: list[TimelineEvent]) -> str:
    """Section body, newest first, one entry per line."""
    return "\n".join(e.render() for e in sorted(events, key=lambda e: e.ts,
                                                reverse=True))


def dedupe(events: list[TimelineEvent]) -> list[TimelineEvent]:
    """Drop exact (timestamp, text) repeats, keeping the first seen.

    The runner re-reads the same RSS feed every five minutes, so without this
    a single headline accumulates one timeline line per cycle.
    """
    seen, out = set(), []
    for e in events:
        key = (e.ts, e.text.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


# ------------------------------------------------------------------ staleness

@dataclass(frozen=True)
class Staleness:
    """Why a note should or should not be trusted for an active trade."""
    stale: bool
    reason: str
    age_hours: float | None
    latest: datetime | None

    @property
    def label(self) -> str:
        return "STALE" if self.stale else "FRESH"


def assess(body: str, *, now: datetime | None = None,
           max_age_hours: float = 72.0,
           resolution_ts: datetime | None = None) -> Staleness:
    """Is this note's newest observation recent enough to trade off?

    Three ways to be stale, checked most-decisive first:
      1. no timestamped observation at all -- cannot be dated, so cannot be trusted
      2. newest observation predates the market's resolution date
      3. newest observation older than `max_age_hours`

    A note with no Timeline is stale by construction. That is deliberate: the
    alternative is treating undated prose as current, which is exactly the
    failure this module exists to prevent.
    """
    now = _aware(now or datetime.now(timezone.utc))
    latest = latest_event(body)
    if latest is None:
        return Staleness(True, "no timestamped observations in note", None, None)

    age_h = latest.age(now).total_seconds() / 3600.0

    if age_h < 0:
        # A timestamp in the future is a data error (clock skew, a mis-entered
        # hour, a timezone mistake). Reporting it as "FRESH (-1h old)" would
        # launder the error into confidence, so it is stale until corrected.
        return Staleness(True, f"newest observation is {-age_h:.1f}h in the "
                               f"FUTURE -- check the timestamp", age_h, latest.ts)

    if resolution_ts is not None and latest.ts < _aware(resolution_ts) <= now:
        return Staleness(
            True,
            f"newest observation {latest.ts:%Y-%m-%d} predates resolution "
            f"{_aware(resolution_ts):%Y-%m-%d}", age_h, latest.ts)

    if age_h > max_age_hours:
        return Staleness(True, f"newest observation is {age_h:.0f}h old "
                               f"(limit {max_age_hours:.0f}h)", age_h, latest.ts)

    return Staleness(False, f"newest observation {age_h:.0f}h old", age_h, latest.ts)


def needs_forced_update(events: list[TimelineEvent], *,
                        poll_shift_pts: float = 5.0) -> tuple[bool, str]:
    """Should we refresh even though the note looks fresh?

    Two triggers from the operating rules: a poll moving more than
    `poll_shift_pts`, or any batch of returns reporting. Both mean the prior
    is no longer the prior regardless of clock age.
    """
    polls = [e for e in events if e.kind.lower() == "poll"]
    for e in events:
        if e.kind.lower() in ("returns", "call"):
            return True, f"{e.kind} reported at {e.ts:%Y-%m-%d %H:%M}"

    nums = []
    for e in polls[:2]:                      # newest two polls
        found = [float(x) for x in re.findall(r"\b(\d{1,3}(?:\.\d)?)\b", e.text)]
        nums.append([n for n in found if 0 <= n <= 100])
    if len(nums) == 2 and nums[0] and nums[1]:
        width = min(len(nums[0]), len(nums[1]))
        shifts = [abs(nums[0][i] - nums[1][i]) for i in range(width)]
        if shifts and max(shifts) >= poll_shift_pts:
            return True, (f"poll moved {max(shifts):.1f}pts "
                          f"(>= {poll_shift_pts:.0f}pt threshold)")
    return False, "no forced-update trigger"


# ------------------------------------------------------------------ news in

def event_from_news(item: dict, *, kind: str = "News") -> TimelineEvent | None:
    """A runner NewsItem ({title, source, pub_date}) -> TimelineEvent.

    `pub_date` is RFC-2822 off Google News RSS ("Mon, 18 Aug 2026 14:32:00 GMT").
    An item with no parseable date is dropped rather than stamped with "now":
    writing an invented timestamp into a time series is worse than writing
    nothing.
    """
    ts = parse_pub_date(item.get("pub_date"))
    if ts is None:
        return None
    title = (item.get("title") or "").strip()
    if not title:
        return None
    src = (item.get("source") or "").strip()
    text = f"{title}" + (f" ({src})" if src else "")
    return TimelineEvent(ts=ts, kind=kind, text=text)


def parse_pub_date(raw: str | None) -> datetime | None:
    """RFC-2822 or ISO -> aware UTC datetime. Unparseable -> None."""
    if not raw:
        return None
    from email.utils import parsedate_to_datetime
    try:
        return _aware(parsedate_to_datetime(raw)).astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return _aware(datetime.fromisoformat(str(raw).replace("Z", "+00:00")))
    except ValueError:
        return None
