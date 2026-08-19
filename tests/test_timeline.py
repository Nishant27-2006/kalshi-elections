"""Time-series vault: parsing, staleness, and the news write path.

The gap this closes: all 134 vault notes carried a day-granularity `updated:`
field and nothing else, so a judge prompt could not distinguish a poll taken
this morning from one taken before the early-vote window closed.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.timeline import (assess, dedupe, event_from_news, latest_event,
                            needs_forced_update, parse_entry, parse_pub_date,
                            parse_timeline, render_timeline, TimelineEvent)
from agent.vault_writer import (STALE_MARKER, append_events, ingest_news,
                                set_stale_marker)

NOW = datetime(2026, 8, 18, 20, 0, tzinfo=timezone.utc)

BODY = """---
aliases:
  - "Race: Test"
updated: 2026-08-18
---

# Race: Test

Intro prose.

## Timeline

[2026-08-18 09:00] News: DDHQ warns "significant egg on face"
[2026-08-18 14:32] Poll: DDHQ avg 37/18/17
[2026-08-16] Returns: early vote closed

## Timing Risk

Counting window dominates.

## Update Log
- seeded
"""


# ---------------------------------------------------------------- parsing
def test_parses_a_timestamped_entry():
    e = parse_entry("[2026-08-18 14:32] Poll: DDHQ avg 37/18/17")
    assert e.ts == datetime(2026, 8, 18, 14, 32, tzinfo=timezone.utc)
    assert e.kind == "Poll"
    assert e.text == "DDHQ avg 37/18/17"


def test_date_only_entry_is_kept_and_flagged():
    """A date without a clock time is real data; inventing an hour is not."""
    e = parse_entry("[2026-08-16] Returns: early vote closed")
    assert e.has_time is False
    assert e.render() == "[2026-08-16] Returns: early vote closed"


def test_entry_without_a_kind_still_parses():
    e = parse_entry("[2026-08-18 09:00] something happened")
    assert e.kind == ""
    assert e.text == "something happened"


def test_bullet_prefixed_entries_parse():
    assert parse_entry("- [2026-08-18 09:00] News: x") is not None


@pytest.mark.parametrize("line", [
    "not an entry",
    "[not-a-date] Poll: x",
    "[2026-13-45 99:99] Poll: x",
    "",
])
def test_non_entries_are_rejected(line):
    assert parse_entry(line) is None


def test_timeline_is_returned_newest_first_regardless_of_file_order():
    events = parse_timeline(BODY)
    assert [e.kind for e in events] == ["Poll", "News", "Returns"]
    assert events == sorted(events, key=lambda e: e.ts, reverse=True)


def test_only_the_timeline_section_is_read():
    """Prose elsewhere in the note must not leak into the event list."""
    assert len(parse_timeline(BODY)) == 3
    assert all("Counting window" not in e.text for e in parse_timeline(BODY))


def test_note_without_a_timeline_yields_nothing():
    assert parse_timeline("# Title\n\n## Timing Risk\nprose") == []
    assert latest_event("no timeline here") is None


def test_render_round_trips():
    events = parse_timeline(BODY)
    assert parse_timeline(f"## Timeline\n{render_timeline(events)}") == events


def test_dedupe_drops_repeats_of_the_same_observation():
    """The runner re-reads the same RSS feed every five minutes."""
    e = TimelineEvent(ts=NOW, kind="News", text="Donalds leads")
    assert len(dedupe([e, e, e])) == 1


def test_dedupe_is_case_insensitive_on_text():
    a = TimelineEvent(ts=NOW, kind="News", text="Donalds leads")
    b = TimelineEvent(ts=NOW, kind="News", text="DONALDS LEADS")
    assert len(dedupe([a, b])) == 1


# ---------------------------------------------------------------- staleness
def test_a_recent_note_is_fresh():
    st = assess(BODY, now=NOW)
    assert st.stale is False and st.label == "FRESH"
    assert st.age_hours == pytest.approx(5.47, abs=0.1)


def test_an_old_note_goes_stale():
    st = assess(BODY, now=NOW + timedelta(days=5))
    assert st.stale is True
    assert "old" in st.reason


def test_a_note_with_no_timestamps_is_stale_by_construction():
    """Undated prose must not be treated as current."""
    st = assess("# Title\n\n## Timing Risk\nprose", now=NOW)
    assert st.stale is True
    assert "no timestamped observations" in st.reason


def test_observations_predating_a_passed_resolution_are_stale():
    st = assess(BODY, now=NOW + timedelta(days=30),
                resolution_ts=datetime(2026, 8, 25, tzinfo=timezone.utc))
    assert st.stale is True
    assert "predates resolution" in st.reason


def test_a_future_resolution_does_not_make_a_fresh_note_stale():
    st = assess(BODY, now=NOW,
                resolution_ts=datetime(2026, 11, 3, tzinfo=timezone.utc))
    assert st.stale is False


# ---------------------------------------------------------------- forced update
def test_returns_reporting_forces_an_update():
    forced, why = needs_forced_update(parse_timeline(BODY))
    assert forced is True and "Returns" in why


def test_a_poll_shift_over_five_points_forces_an_update():
    body = ("## Timeline\n"
            "[2026-08-18 14:00] Poll: 31 28 31\n"
            "[2026-08-17 14:00] Poll: 37 18 17\n")
    forced, why = needs_forced_update(parse_timeline(body))
    assert forced is True and "poll moved" in why


def test_a_small_poll_shift_does_not_force_an_update():
    body = ("## Timeline\n"
            "[2026-08-18 14:00] Poll: 37 18 17\n"
            "[2026-08-17 14:00] Poll: 38 19 18\n")
    forced, _ = needs_forced_update(parse_timeline(body))
    assert forced is False


# ---------------------------------------------------------------- news in
def test_rfc2822_pub_dates_parse():
    ts = parse_pub_date("Mon, 18 Aug 2026 14:32:00 GMT")
    assert ts == datetime(2026, 8, 18, 14, 32, tzinfo=timezone.utc)


def test_iso_pub_dates_parse():
    assert parse_pub_date("2026-08-18T14:32:00Z").hour == 14


def test_news_without_a_parseable_date_is_dropped_not_stamped_with_now():
    """Writing an invented timestamp into a time series is worse than
    writing nothing."""
    assert event_from_news({"title": "x", "pub_date": "yesterday"}) is None
    assert event_from_news({"title": "x", "pub_date": None}) is None
    assert event_from_news({"title": "x"}) is None


def test_news_item_becomes_an_event_carrying_its_source():
    e = event_from_news({"title": "Donalds leads", "source": "AP",
                         "pub_date": "Mon, 18 Aug 2026 14:32:00 GMT"})
    assert e.kind == "News"
    assert "Donalds leads" in e.text and "AP" in e.text


# ---------------------------------------------------------------- write path
@pytest.fixture
def note(tmp_path):
    p = tmp_path / "Race - Test.md"
    p.write_text(BODY, encoding="utf-8")
    return p


def test_appending_a_new_event_persists_it(note):
    e = TimelineEvent(ts=datetime(2026, 8, 18, 18, 0, tzinfo=timezone.utc),
                      kind="News", text="fresh headline")
    res = append_events(note, [e])
    assert res["added"] == 1 and res["total"] == 4
    assert "fresh headline" in note.read_text(encoding="utf-8")


def test_appending_the_same_event_twice_adds_nothing(note):
    e = TimelineEvent(ts=datetime(2026, 8, 18, 18, 0, tzinfo=timezone.utc),
                      kind="News", text="fresh headline")
    append_events(note, [e])
    res = append_events(note, [e])
    assert res["added"] == 0


def test_the_rest_of_the_note_is_preserved_byte_for_byte(note):
    """These are hand-authored analytical notes; only Timeline may change."""
    e = TimelineEvent(ts=NOW, kind="News", text="fresh")
    append_events(note, [e])
    after = note.read_text(encoding="utf-8")
    assert "## Timing Risk" in after
    assert "Counting window dominates." in after
    assert "## Update Log" in after and "- seeded" in after
    assert 'aliases:' in after


def test_frontmatter_updated_tracks_the_newest_entry(note):
    e = TimelineEvent(ts=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
                      kind="News", text="later")
    append_events(note, [e])
    assert "updated: 2026-09-01" in note.read_text(encoding="utf-8")


def test_a_note_with_no_timeline_section_gets_one(tmp_path):
    p = tmp_path / "n.md"
    p.write_text("# Title\n\n## Timing Risk\nprose\n", encoding="utf-8")
    append_events(p, [TimelineEvent(ts=NOW, kind="News", text="first")])
    body = p.read_text(encoding="utf-8")
    assert "## Timeline" in body and "first" in body
    assert body.index("## Timeline") < body.index("## Timing Risk")
    assert len(parse_timeline(body)) == 1


def test_dry_run_reports_without_writing(note):
    before = note.read_text(encoding="utf-8")
    res = append_events(note, [TimelineEvent(ts=NOW, kind="News", text="x")],
                        dry_run=True)
    assert res["added"] == 1
    assert note.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------- stale marker
def test_stale_marker_is_written_into_the_note_body(note):
    st = assess(note.read_text(encoding="utf-8"), now=NOW + timedelta(days=10))
    res = set_stale_marker(note, st)
    body = note.read_text(encoding="utf-8")
    assert res["stale"] is True and res["changed"] is True
    assert STALE_MARKER in body
    assert body.index(STALE_MARKER) > body.index("# Race: Test")


def test_stale_marker_is_cleared_once_the_note_is_fresh_again(note):
    set_stale_marker(note, assess(note.read_text(encoding="utf-8"),
                                  now=NOW + timedelta(days=10)))
    assert STALE_MARKER in note.read_text(encoding="utf-8")
    set_stale_marker(note, assess(note.read_text(encoding="utf-8"), now=NOW))
    assert STALE_MARKER not in note.read_text(encoding="utf-8")


def test_marking_stale_twice_does_not_duplicate_the_block(note):
    st = assess(note.read_text(encoding="utf-8"), now=NOW + timedelta(days=10))
    set_stale_marker(note, st)
    set_stale_marker(note, st)
    assert note.read_text(encoding="utf-8").count(STALE_MARKER) == 1


# ---------------------------------------------------------------- scoping
class _FakeNote:
    def __init__(self, tags): self.tags = tags


def test_race_and_state_notes_accept_a_timeline():
    from agent.vault_writer import accepts_timeline
    assert accepts_timeline(_FakeNote(["race", "florida", "2026"]))
    assert accepts_timeline(_FakeNote(["state", "florida"]))
    assert accepts_timeline(_FakeNote(["polling", "florida"]))


def test_method_notes_refuse_a_timeline():
    """A headline about one candidate is not an observation about a pattern."""
    from agent.vault_writer import accepts_timeline
    assert not accepts_timeline(_FakeNote(["trading-pattern", "primaries"]))
    assert not accepts_timeline(_FakeNote(["methodology", "causality"]))


def test_untagged_notes_refuse_a_timeline():
    from agent.vault_writer import accepts_timeline
    assert not accepts_timeline(_FakeNote([]))
    assert not accepts_timeline(_FakeNote(None))


def test_ingest_routes_only_to_accepting_notes():
    from agent.vault_writer import ingest_news

    class G:
        def __init__(self): self.notes = {}
        def seed_search(self, t): return list(self.notes)

    g = G()
    g.notes["Pattern"] = _FakeNote(["trading-pattern"])
    res = ingest_news(g, [{"title": "Donalds leads", "source": "AP",
                           "pub_date": "Mon, 18 Aug 2026 14:32:00 GMT"}],
                      dry_run=True)
    assert all(r.get("note") is None for r in res), "method note must not be written"


def test_a_future_timestamp_is_stale_not_fresh():
    """Clock skew or a mis-entered hour must not launder into confidence."""
    body = "## Timeline\n[2026-08-18 16:10] Market: stamped an hour ahead\n"
    st = assess(body, now=NOW - timedelta(hours=5))   # now = 15:00
    assert st.stale is True
    assert "FUTURE" in st.reason
