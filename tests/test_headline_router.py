"""Tests for the two-stage headline router.

The measured baseline these defend: the vault alone scored 50.0%
precision@1 on `headline_eval_set`, missed 5 of 22 in-scope headlines, and
answered 2 of the 3 headlines Kalshi lists no market for. The router scores
90.9%, and its strict mode answers none of the 3.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent.entity_index import EntityIndex, build_from_markets, add_subject_terms
from agent.headline_router import HeadlineRouter, Route


class _FakeNote:
    def __init__(self, body):
        self.body = body

    def summary(self, n=900):
        return self.body[:n]


class _FakeGraph:
    """Minimal stand-in: a vault with two hubs and one market note."""

    def __init__(self, notes=None, subject_hits=None):
        self.notes = notes or {
            "Vertical: MLB Pro Baseball": _FakeNote("covers KXMLBGAME rules"),
            "Vertical: Crypto Digital Assets": _FakeNote("covers KXBTCD"),
            "Market: KXCPIYOY US CPI Year-over-Year": _FakeNote("cpi detail"),
            "Vertical: Corporate Events": _FakeNote("mentions KXCPIYOY once"),
        }
        self._subject_hits = subject_hits or {}

    def retrieve_context(self, text, max_notes=6, chars_per_note=900):
        hits = self._subject_hits.get(text, [])
        return hits, "\n".join(hits)


def _idx():
    idx = build_from_markets({"KXMLBGAME": [{"yes_sub_title": "New York Y"},
                                            {"yes_sub_title": "Boston"}]})
    add_subject_terms(idx, {"KXBTCD": {"Bitcoin price on Aug 21"}})
    return idx


# ------------------------------------------------------------ hub mapping

def test_the_hub_map_is_derived_from_the_vaults_own_text():
    """A note naming KXMLBGAME is evidence it covers that series. Evidence
    beats an author's memory, so the map is read rather than written."""
    r = HeadlineRouter(_FakeGraph(), entity_index=_idx())
    assert r._hub_for_series["KXMLBGAME"] == "Vertical: MLB Pro Baseball"
    assert r._hub_for_series["KXBTCD"] == "Vertical: Crypto Digital Assets"


def test_a_note_whose_title_names_the_series_beats_one_that_merely_cites_it():
    """THE BUG THIS PINS: "Vertical: Corporate Events" mentions KXCPIYOY in
    passing and is a shorter title, so a shortest-wins tiebreak sent CPI
    there instead of to the note actually named for it."""
    g = _FakeGraph()
    idx = EntityIndex(by_phrase={"cpi": {"KXCPIYOY"}},
                      series_seen={"KXCPIYOY"}, strong_singles={"cpi"})
    r = HeadlineRouter(g, entity_index=idx)
    assert r._hub_for_series["KXCPIYOY"] == "Market: KXCPIYOY US CPI Year-over-Year"


def test_a_series_no_note_mentions_falls_back_to_the_explicit_table():
    r = HeadlineRouter(_FakeGraph(), entity_index=_idx())
    assert r._hub_for_series["KXNBAGAME"] == "Vertical: NBA Pro Basketball"


# ---------------------------------------------------------------- routing

def test_an_entity_headline_routes_through_the_entity_stage():
    r = HeadlineRouter(_FakeGraph(), entity_index=_idx())
    out = r.route("Yankees rally past Boston")
    assert out.series == ["KXMLBGAME"]
    assert out.notes[0] == "Vertical: MLB Pro Baseball"
    assert out.stage == "entity"
    assert out.actionable


def test_a_subject_headline_the_entity_stage_cannot_see_still_routes():
    """The two stages cover disjoint vocabulary. A headline the entity index
    misses may still be a subject the vault knows by name."""
    g = _FakeGraph(subject_hits={"Hurricane Delta strengthens":
                                 ["Vertical: Weather and Climate"]})
    r = HeadlineRouter(g, entity_index=_idx())
    out = r.route("Hurricane Delta strengthens")
    assert out.stage == "subject"
    assert out.notes == ["Vertical: Weather and Climate"]


def test_the_entity_hub_leads_the_context_when_both_stages_fire():
    """A named team is harder evidence than a token overlap, so its note
    should lead the block the trader actually reads."""
    g = _FakeGraph(subject_hits={"Yankees rally past Boston":
                                 ["Vertical: Corporate Events"]})
    r = HeadlineRouter(g, entity_index=_idx())
    out = r.route("Yankees rally past Boston")
    assert out.stage == "both"
    assert out.notes[0] == "Vertical: MLB Pro Baseball"


def test_a_headline_about_nothing_routes_to_nothing():
    r = HeadlineRouter(_FakeGraph(), entity_index=_idx())
    out = r.route("Local bakery wins award for sourdough")
    assert out.series == [] and out.notes == [] and out.stage == "none"
    assert not out.actionable


# ----------------------------------------------------------- strict mode

def test_strict_mode_refuses_context_with_no_tradeable_series():
    """THE FALSE ALARM THIS KILLS. The subject stage proves a headline is
    topically near some cluster; it does not prove there is an order to
    place. "Local bakery wins award" produced an award-market context block
    on the word "award" -- confident, related-looking, and untradeable."""
    g = _FakeGraph(subject_hits={"Local bakery wins award":
                                 ["Vertical: Awards and Screen"]})
    r = HeadlineRouter(g, entity_index=_idx())
    assert r.route("Local bakery wins award").notes  # non-strict answers
    assert r.route_strict("Local bakery wins award").notes == []
    assert not r.route_strict("Local bakery wins award").actionable


def test_strict_mode_keeps_a_headline_that_does_name_a_market():
    r = HeadlineRouter(_FakeGraph(), entity_index=_idx())
    out = r.route_strict("Yankees rally past Boston")
    assert out.series == ["KXMLBGAME"]
    assert out.actionable


def test_context_without_a_series_is_not_actionable():
    """Background reading is not a trade signal, and the distinction has to
    be a property rather than a convention."""
    assert not Route("h", notes=["Vertical: Tennis"]).actionable
    assert Route("h", series=["KXATPMATCH"]).actionable


# --------------------------------------------------- measured regression

def test_the_router_beats_the_vault_on_the_labelled_set():
    """The whole justification, re-measured on every run. If a change makes
    routing worse this fails, rather than being noticed months later."""
    pytest.importorskip("agent.knowledge_graph")
    from agent.knowledge_graph import VaultGraph
    from headline_eval_set import score

    idx_path = Path("state/_entity_index.json")
    if not idx_path.exists():
        pytest.skip("entity index not built; run scripts/build_entity_index.py")

    g = VaultGraph()
    r = HeadlineRouter(g)
    base = score(lambda h: g.retrieve_context(h)[0])
    routed = score(lambda h: r.route(h).notes)
    strict = score(lambda h: r.route_strict(h).notes)

    assert routed["precision_at_1"] > base["precision_at_1"] + 0.30
    assert routed["silent_misses"] < base["silent_misses"]
    assert strict["false_alarms"] == 0, \
        "strict mode exists to answer nothing when nothing is tradeable"
    assert base["false_alarms"] > 0, \
        "if the baseline stops false-alarming, this comparison is stale"
