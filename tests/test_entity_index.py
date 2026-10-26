"""Tests for headline -> series routing.

Most of these pin a SPECIFIC failure that was observed and fixed. The
retrieval was never slow -- it ran in 0.1ms and was wrong 55% of the time --
so every test here is about precision or about abstaining, never about speed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent.entity_index import (EntityIndex, EVENT_WORDS, NICKNAMES,
                                add_subject_terms, build_from_markets,
                                _phrase_tokens)


def _mkt(sub, title=""):
    return {"yes_sub_title": sub, "title": title}


def _sports_index():
    return build_from_markets({
        "KXMLBGAME": [_mkt("New York Y"), _mkt("Boston"), _mkt("Milwaukee"),
                      _mkt("Chicago C"), _mkt("A's")],
        "KXNFLGAME": [_mkt("KC Chiefs"), _mkt("TEN Titans"), _mkt("CHI Bears"),
                      _mkt("PHI Eagles"), _mkt("DAL Cowboys")],
        "KXATPMATCH": [_mkt("Frances Tiafoe"), _mkt("Taylor Fritz")],
        "KXNCAAFGAME": [_mkt("Ohio"), _mkt("Alabama")],
    })


# ----------------------------------------------------- the original defect

def test_a_team_nickname_routes_where_the_vault_could_not():
    """THE DEFECT THIS MODULE EXISTS FOR. "Yankees" appears in zero note
    titles, zero aliases and zero note bodies, so the vault's token search
    fell through to whatever shared the word "series" -- which was NHL."""
    idx = _sports_index()
    assert idx.series_for("Yankees rally past Red Sox") == ["KXMLBGAME"]


def test_the_nickname_table_only_covers_leagues_the_api_leaves_short():
    """MLB and WNBA subtitles are cities; NFL already publishes nicknames.
    A table entry for NFL would be dead weight and a second place to drift."""
    assert "KXMLBGAME" in NICKNAMES
    assert "KXNFLGAME" not in NICKNAMES


def test_a_nickname_only_attaches_when_its_series_was_actually_harvested():
    """Nicknames for a league with no live markets must not create phantom
    routes to a series the index never saw."""
    idx = build_from_markets({"KXATPMATCH": [_mkt("Frances Tiafoe")]})
    assert idx.series_for("Yankees rally past Red Sox") == []


# ------------------------------------------------- sub-token / abbreviation

def test_the_last_word_of_a_multiword_entity_is_indexed_alone():
    """Kalshi says "KC Chiefs"; a headline says "Chiefs". The discriminative
    half is the nickname, and it is always last."""
    idx = _sports_index()
    assert idx.series_for("Chiefs quarterback ruled out") == ["KXNFLGAME"]


def test_a_short_disambiguator_suffix_is_never_indexed_alone():
    """Kalshi distinguishes same-city teams with a trailing letter: "Chicago
    C" vs "Chicago WS", "New York Y" vs "New York M". Those suffixes are the
    LAST token of their phrase, so without a length floor they get indexed
    alone and a stray "c" in a headline routes to the Cubs.

    A leading league abbreviation ("TEN Titans") was never at risk -- only
    the last token is indexed -- so the length rule is about suffixes."""
    idx = build_from_markets({"KXMLBGAME": [_mkt("Chicago C"),
                                            _mkt("Chicago WS"),
                                            _mkt("New York Y")]})
    for junk in ("c", "ws", "y"):
        assert junk not in idx.by_phrase, f"{junk!r} must not be an entity"
    # the full phrases still work
    assert idx.series_for("Chicago WS beat New York Y") == ["KXMLBGAME"]


def test_a_leading_abbreviation_is_not_indexed_either():
    idx = _sports_index()
    assert "ten" not in idx.by_phrase
    assert idx.series_for("ten people attended the meeting") == []


def test_a_possessive_does_not_hide_a_name():
    """Kalshi writes "the Fed's Apr 2027 meeting". Apostrophes survive
    normalisation because the Athletics are published as "A's", so without
    explicit handling the token is "fed's" and "Fed" never matches."""
    assert _phrase_tokens("the Fed's meeting") == ["fed", "meeting"]
    # ...and the Athletics still survive it
    assert "athletics" in NICKNAMES["KXMLBGAME"]


# ---------------------------------------------------------- abstention

def test_a_lone_ambiguous_token_does_not_fire_without_corroboration():
    """"Ohio" is a real NCAAF school, so "man rescues cat from tree in
    suburban Ohio" matches on entity evidence alone. Answering there is
    exactly the false alarm this gate exists to stop."""
    idx = _sports_index()
    assert idx.series_for("Man rescues cat from tree in suburban Ohio") == []
    # ...but with an event word it is a real sports headline again
    assert idx.series_for("Ohio wins in overtime") == ["KXNCAAFGAME"]


def test_two_entities_from_one_series_need_no_event_word():
    """"Titans upset the Bears" is unambiguous without a verb list."""
    idx = _sports_index()
    assert idx.series_for("Titans and the Bears") == ["KXNFLGAME"]


def test_corroboration_can_be_switched_off_for_inspection():
    idx = _sports_index()
    assert idx.series_for("suburban Ohio", corroborate=False) == ["KXNCAAFGAME"]
    assert idx.series_for("suburban Ohio", corroborate=True) == []


def test_a_headline_about_nothing_returns_nothing():
    idx = _sports_index()
    assert idx.series_for("Local bakery wins award for sourdough") == []


# ------------------------------------------------------- strike filtering

def test_price_strikes_are_not_treated_as_entities():
    """Crypto publishes "$50,000 or above" in the same field team sports use
    for the team name. Indexing those maps every dollar figure in a headline
    onto Bitcoin."""
    idx = build_from_markets({
        "KXBTCD": [_mkt("$50,000 or above"), _mkt("$95,000 or above")]})
    assert idx.by_phrase == {}
    assert idx.series_for("Bitcoin tops $95,000") == []


def test_a_player_prop_suffix_is_stripped():
    idx = build_from_markets({"KXMLBHR": [_mkt("Alex Bregman: 2+")]})
    assert "alex bregman" in idx.by_phrase


# -------------------------------------------------------- subject terms

def test_subject_terms_come_from_titles_for_series_with_no_entities():
    """Crypto and macro have no entity subtitles, but their TITLE carries the
    subject: "Bitcoin price on Aug 21", "the rate of CPI inflation"."""
    idx = build_from_markets({"KXBTCD": [_mkt("$50,000 or above")]})
    add_subject_terms(idx, {
        "KXBTCD": {"Bitcoin price on Aug 21, 2026?"},
        "KXCPIYOY": {"Will the rate of CPI inflation be above 2.5%?"},
    })
    assert idx.series_for("Bitcoin tops $95,000") == ["KXBTCD"]
    assert idx.series_for("CPI comes in hotter than expected") == ["KXCPIYOY"]


def test_a_subject_term_is_strong_enough_to_fire_alone():
    """A term harvested at low cross-series document frequency is distinctive
    by construction, unlike a bare team name. It must bypass the
    corroboration gate or "Bitcoin tops $95,000" -- which contains no event
    word -- gets thrown away."""
    idx = EntityIndex()
    add_subject_terms(idx, {"KXBTCD": {"Bitcoin price today"}})
    assert "bitcoin" in idx.strong_singles
    assert idx.series_for("Bitcoin tops $95,000") == ["KXBTCD"]


def test_a_rare_function_word_is_not_a_subject_term():
    """THE FALSE ALARM THIS PREVENTS: "for" is carried by exactly one series
    ("...for the year ending in August 2026"), so document frequency alone
    calls it distinctive -- and "local bakery wins award FOR sourdough"
    routed straight to CPI. Rarity is evidence a token identifies a series;
    it is not evidence the token means anything."""
    idx = EntityIndex()
    add_subject_terms(idx, {
        "KXCPIYOY": {"Will CPI inflation be above 2.5% for the year ending"}})
    assert "for" not in idx.by_phrase
    assert "cpi" in idx.by_phrase
    assert idx.series_for("Local bakery wins award for sourdough") == []


def test_subject_harvest_skips_series_that_already_have_entities():
    """Harvesting titles for an entity series re-adds its team names as
    "strong" singles, silently defeating the corroboration gate -- "ohio"
    came back as a distinctive subject term and the cat-in-a-tree headline
    routed to college football again."""
    idx = build_from_markets({"KXNCAAFGAME": [_mkt("Ohio")]})
    add_subject_terms(idx, {"KXNCAAFGAME": {"Will Ohio win on Saturday?"}})
    assert "ohio" not in idx.strong_singles
    assert idx.series_for("Man rescues cat in suburban Ohio") == []


# ------------------------------------------------------------ round trip

def test_the_index_survives_a_save_and_load(tmp_path):
    idx = _sports_index()
    add_subject_terms(idx, {"KXBTCD": {"Bitcoin price today"}})
    p = tmp_path / "idx.json"
    idx.save(p)
    back = EntityIndex.load(p)
    assert back.by_phrase == idx.by_phrase
    assert back.series_seen == idx.series_seen
    assert back.strong_singles == idx.strong_singles, \
        "strong_singles must persist, or reloading re-breaks Bitcoin"
    assert back.series_for("Bitcoin tops $95,000") == ["KXBTCD"]


def test_event_words_contain_the_vocabulary_of_things_happening():
    for w in ("wins", "ruled", "injury", "traded", "overtime"):
        assert w in EVENT_WORDS
