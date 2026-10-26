"""The six-slot schema must be general, not quietly shaped around elections.

Two non-political markets are modelled in the vault (KXHIGHNY weather,
KXCPIYOY economics). These tests assert they route and compress through the
SAME CONTEXT_SLOTS the political notes use, and that a headline from one
domain does not pull context from the other.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.config import VAULT_PATH
from agent.knowledge_graph import SLOT_LABELS, VaultGraph
from agent.nodes import format_expert_context

pytestmark = pytest.mark.skipif(not VAULT_PATH.exists(),
                                reason="local Obsidian vault not present")

WEATHER = "NYC heat wave forecast to push temperatures above 90 degrees"
CPI = "CPI inflation expected to come in at 3.4 percent in August"
POLITICS = "Byron Donalds leads Florida governor primary poll"


@pytest.fixture(scope="module")
def g():
    return VaultGraph()


def _ctx(g, headline):
    titles, raw = g.retrieve_context(headline, max_notes=6)
    expert = g.expert_context(titles, max_chars=800)
    return titles, raw, expert, format_expert_context(expert)


@pytest.mark.parametrize("headline,expected", [
    (WEATHER, "Market: KXHIGHNY NYC Daily High Temperature"),
    (CPI, "Market: KXCPIYOY US CPI Year-over-Year"),
])
def test_non_political_headlines_reach_their_market_note(g, headline, expected):
    titles, *_ = _ctx(g, headline)
    assert titles and titles[0] == expected


@pytest.mark.parametrize("headline", [WEATHER, CPI])
def test_non_political_notes_fill_every_slot(g, headline):
    _, _, expert, _ = _ctx(g, headline)
    assert set(expert) == set(SLOT_LABELS), \
        f"schema is politics-specific; missing {set(SLOT_LABELS) - set(expert)}"


@pytest.mark.parametrize("headline", [WEATHER, CPI, POLITICS])
def test_every_domain_respects_the_same_prompt_cap(g, headline):
    _, _, _, block = _ctx(g, headline)
    assert 0 < len(block) <= 800


def test_a_weather_headline_pulls_no_political_race_note(g):
    """Regression: 'heat wave' once top-matched a midterm-wave pattern note,
    so a weather contract's prompt carried midterm-backlash analysis."""
    titles, _, _, block = _ctx(g, WEATHER)
    assert not any(t.startswith("Race:") for t in titles[:2])
    for term in ("donalds", "fishback", "gop primary", "midterm"):
        assert term not in block.lower()


def test_a_political_headline_pulls_no_market_structure_note(g):
    titles, _, _, block = _ctx(g, POLITICS)
    assert titles[0].startswith("Race:")
    for term in ("kxhighny", "kxcpiyoy", "bureau of labor"):
        assert term not in block.lower()


def test_subject_notes_outrank_method_notes(g):
    """A pattern note is a lens, not the subject of a headline."""
    titles = g.seed_search(WEATHER)
    concrete = [t for t in titles if t.startswith("Market:")]
    method = [t for t in titles if t.startswith(("Pattern:", "Trading Pattern:"))]
    if concrete and method:
        assert titles.index(concrete[0]) < titles.index(method[0])


def test_an_unmodelled_domain_injects_nothing_rather_than_guessing(g):
    """No crypto note exists. The right answer is an empty block, not the
    nearest political note."""
    _, _, expert, block = _ctx(g, "Dogecoin surges on exchange listing rumor")
    assert block == "" and expert == {}


# ---------------------------------------------------------------- MLB vertical
# Was "Boston on pace to win 90 games this season" -- genuinely ambiguous
# once NBA was modelled, since "season/wins/games" is shared vocabulary.
MLB_SEASON = "Red Sox on pace to win 90 games this baseball season"
MLB_TOTAL = "Padres visit Mets tonight, total runs around nine"
MLB_CHAMP = "Rays favored to win the World Series postseason"
MLB_HUB = "MLB pennant race standings tighten in the final stretch"


@pytest.mark.parametrize("headline", [MLB_SEASON, MLB_TOTAL, MLB_CHAMP, MLB_HUB])
def test_mlb_headlines_reach_the_mlb_cluster(g, headline):
    titles, *_ = _ctx(g, headline)
    assert titles, "no seed matched"
    assert "MLB" in titles[0], f"routed to {titles[0]}"


@pytest.mark.parametrize("headline", [MLB_SEASON, MLB_TOTAL, MLB_CHAMP, MLB_HUB])
def test_mlb_notes_fill_every_slot(g, headline):
    _, _, expert, _ = _ctx(g, headline)
    assert set(expert) == set(SLOT_LABELS), \
        f"schema failed on sports; missing {set(SLOT_LABELS) - set(expert)}"


@pytest.mark.parametrize("headline", [MLB_SEASON, MLB_TOTAL, MLB_CHAMP, MLB_HUB])
def test_mlb_prompts_carry_no_political_content(g, headline):
    _, _, _, block = _ctx(g, headline)
    assert 0 < len(block) <= 800
    for term in ("donalds", "fishback", "gop primary", "midterm", "electoral",
                 "certification"):
        assert term not in block.lower(), f"political leak: {term}"


def test_the_mlb_hub_is_tagged_as_a_vertical(g):
    """Rotation depends on the hub tag; without it the next run repeats MLB."""
    note = g.notes.get("Vertical: MLB Pro Baseball")
    assert note is not None
    tags = {t.lower() for t in note.tags}
    assert "vertical" in tags and "market" in tags and "mlb" in tags


def test_the_hub_links_to_every_archetype(g):
    note = g.notes["Vertical: MLB Pro Baseball"]
    for arch in ("Market: MLB Season Wins Total",
                 "Market: MLB Single-Game Moneyline",
                 "Market: MLB Game Totals Ladder",
                 "Market: MLB Championship Field"):
        assert arch in note.links, f"hub does not link {arch}"


# ---------------------------------------------------------------- place-name collisions
@pytest.mark.parametrize("headline,expected_prefix", [
    ("Washington state senate race tightens ahead of the primary", "State: Washington"),
    ("Colorado governor primary poll shows incumbent leading", "State: Colorado"),
    ("Texas congressional district ballot certification dispute", "State: Texas"),
])
def test_place_names_still_reach_political_notes(g, headline, expected_prefix):
    """MLB club cities collide with state notes. Adding club aliases to the hub
    once hijacked bare 'Washington'/'Texas'/'Colorado' and broke this."""
    titles, *_ = _ctx(g, headline)
    assert titles[0].startswith(expected_prefix), f"hijacked by {titles[0]}"


@pytest.mark.parametrize("name", ["washington", "texas", "colorado",
                                  "arizona", "minnesota"])
def test_state_colliding_club_names_are_not_claimed_as_mlb_aliases(g, name):
    owner = g.alias_index.get(name)
    assert owner is None or not owner.startswith("Vertical: MLB"), \
        f"{name!r} claimed by the MLB hub; it collides with a state note"


def test_sports_vocabulary_disambiguates_a_shared_place_name(g):
    """'Toronto bullpen' must not land on a political note."""
    titles, *_ = _ctx(g, "Toronto bullpen collapses in the ninth inning")
    assert titles and "MLB" in titles[0]


# ---------------------------------------------------------------- soccer vertical
SOC_MATCH = "Champions League match result, draw at 22 cents"
SOC_1H = "First half winner at halftime in the Champions League"
SOC_BTTS = "Both teams to score in the Premier League fixture"
SOC_HUB = "Premier League season opens with relegation battles"


@pytest.mark.parametrize("headline", [SOC_MATCH, SOC_1H, SOC_BTTS, SOC_HUB])
def test_soccer_headlines_reach_the_soccer_cluster(g, headline):
    titles, *_ = _ctx(g, headline)
    assert titles, "no seed matched"
    assert "Soccer" in titles[0] or "European Club" in titles[0], \
        f"routed to {titles[0]}"


@pytest.mark.parametrize("headline", [SOC_MATCH, SOC_1H, SOC_BTTS, SOC_HUB])
def test_soccer_notes_fill_every_slot(g, headline):
    _, _, expert, block = _ctx(g, headline)
    assert set(expert) == set(SLOT_LABELS)
    assert 0 < len(block) <= 800


# Two sports verticals share the `sports` domain family, so domain markers
# alone cannot separate them -- these guard that they still do not bleed.
@pytest.mark.parametrize("headline", [SOC_MATCH, SOC_1H, SOC_BTTS])
def test_soccer_prompts_carry_no_baseball_content(g, headline):
    _, _, _, block = _ctx(g, headline)
    for term in ("mlb", "baseball", "innings", "world series", "bullpen"):
        assert term not in block.lower(), f"baseball leak: {term}"


@pytest.mark.parametrize("headline", [MLB_SEASON, MLB_TOTAL, MLB_CHAMP])
def test_baseball_prompts_carry_no_soccer_content(g, headline):
    _, _, _, block = _ctx(g, headline)
    for term in ("soccer", "champions league", "halftime", "btts", "relegation"):
        assert term not in block.lower(), f"soccer leak: {term}"


@pytest.mark.parametrize("headline", [SOC_MATCH, SOC_1H, SOC_BTTS, SOC_HUB])
def test_soccer_prompts_carry_no_political_content(g, headline):
    _, _, _, block = _ctx(g, headline)
    for term in ("donalds", "fishback", "gop primary", "midterm", "ballot"):
        assert term not in block.lower(), f"political leak: {term}"


def test_the_soccer_hub_is_tagged_as_a_vertical(g):
    note = g.notes.get("Vertical: European Club Soccer")
    assert note is not None
    tags = {t.lower() for t in note.tags}
    assert {"vertical", "market", "soccer"} <= tags


def test_the_soccer_hub_links_to_every_archetype(g):
    note = g.notes["Vertical: European Club Soccer"]
    for arch in ("Market: Soccer Three-Way Match Result",
                 "Market: Soccer First-Half Period Market",
                 "Market: Soccer Both Teams To Score",
                 "Market: Soccer Outright Winner Field"):
        assert arch in note.links, f"hub does not link {arch}"


def test_both_sports_hubs_coexist(g):
    """Rotation must see two built verticals, not one overwriting the other."""
    hubs = [t for t, n in g.notes.items()
            if "vertical" in {x.lower() for x in n.tags}]
    assert "Vertical: MLB Pro Baseball" in hubs
    assert "Vertical: European Club Soccer" in hubs


# ---------------------------------------------------------------- crypto vertical
CRY_LADDER = "Bitcoin daily price ladder on the CF Benchmarks index"
CRY_MAX = "How high will BTC get in August, monthly maximum barrier"
CRY_15M = "BTC 15 minute binary target price"
CRY_MILE = "Will Bitcoin be above 200k by 2027"
CRY_HUB = "Ethereum and Solana crypto markets trade around the clock"


@pytest.mark.parametrize("headline", [CRY_LADDER, CRY_MAX, CRY_15M, CRY_MILE, CRY_HUB])
def test_crypto_headlines_reach_the_crypto_cluster(g, headline):
    titles, *_ = _ctx(g, headline)
    assert titles, "no seed matched"
    assert "Crypto" in titles[0], f"routed to {titles[0]}"


@pytest.mark.parametrize("headline", [CRY_LADDER, CRY_MAX, CRY_15M, CRY_MILE, CRY_HUB])
def test_crypto_notes_fill_every_slot(g, headline):
    _, _, expert, block = _ctx(g, headline)
    assert set(expert) == set(SLOT_LABELS)
    assert 0 < len(block) <= 800


@pytest.mark.parametrize("headline", [CRY_LADDER, CRY_MAX, CRY_15M, CRY_MILE])
def test_crypto_prompts_carry_no_other_vertical_content(g, headline):
    _, _, _, block = _ctx(g, headline)
    for term in ("mlb", "baseball", "innings", "champions league", "halftime",
                 "donalds", "gop primary", "midterm"):
        assert term not in block.lower(), f"leak: {term}"


@pytest.mark.parametrize("headline", [MLB_SEASON, SOC_MATCH, POLITICS])
def test_other_verticals_carry_no_crypto_content(g, headline):
    _, _, _, block = _ctx(g, headline)
    for term in ("bitcoin", "btc", "cf benchmarks", "ethereum"):
        assert term not in block.lower(), f"crypto leak: {term}"


def test_the_crypto_hub_is_tagged_as_a_vertical(g):
    note = g.notes.get("Vertical: Crypto Digital Assets")
    assert note is not None
    assert {"vertical", "market", "crypto"} <= {t.lower() for t in note.tags}


def test_the_crypto_hub_links_to_every_archetype(g):
    note = g.notes["Vertical: Crypto Digital Assets"]
    for arch in ("Market: Crypto Daily Price Ladder",
                 "Market: Crypto 15-Minute Price Binary",
                 "Market: Crypto Window Maximum",
                 "Market: Crypto Long-Dated Price Milestone"):
        assert arch in note.links, f"hub does not link {arch}"


# The loop adds a vertical per cycle, so this must not be an equality check —
# a hardcoded hub set turns every successful build into a test failure.
KNOWN_HUBS = {"Vertical: MLB Pro Baseball",
              "Vertical: European Club Soccer",
              "Vertical: Crypto Digital Assets",
              "Vertical: Corporate Events"}


def _hubs(g):
    return {t for t, n in g.notes.items()
            if "vertical" in {x.lower() for x in n.tags}}


def test_every_known_vertical_still_has_its_hub(g):
    """Rotation depends on every hub staying discoverable. New hubs are
    welcome; losing one silently is not."""
    missing = KNOWN_HUBS - _hubs(g)
    assert not missing, f"hub(s) disappeared: {missing}"


def test_every_hub_links_at_least_two_archetypes(g):
    """A hub with no archetypes makes rotation believe the vertical is done."""
    for hub in _hubs(g):
        note = g.notes[hub]
        arch = [l for l in set(note.links) if l.startswith("Market: ")]
        assert len(arch) >= 2, f"{hub} links only {len(arch)} archetype(s)"


# ---------------------------------------------------------------- corporate vertical
CORP_IPO = "When will Anthropic officially announce an IPO"
CORP_ACQ = "GameStop acquisition announcement of eBay"
CORP_CEO = "Tim Cook departure as Apple CEO"
CORP_MERGER = "Tesla and SpaceX merger definitive agreement"
CORP_HUB = "corporate events IPO and CEO change markets"


@pytest.mark.parametrize("headline", [CORP_IPO, CORP_ACQ, CORP_CEO,
                                      CORP_MERGER, CORP_HUB])
def test_corporate_headlines_reach_the_corporate_cluster(g, headline):
    titles, *_ = _ctx(g, headline)
    assert titles and "Corporate" in titles[0], \
        f"routed to {titles[0] if titles else '(none)'}"


@pytest.mark.parametrize("headline", [CORP_IPO, CORP_ACQ, CORP_CEO,
                                      CORP_MERGER, CORP_HUB])
def test_corporate_notes_fill_every_slot(g, headline):
    _, _, expert, block = _ctx(g, headline)
    assert set(expert) == set(SLOT_LABELS)
    assert 0 < len(block) <= 800


@pytest.mark.parametrize("headline", [CORP_IPO, CORP_ACQ, CORP_CEO, CORP_MERGER])
def test_corporate_prompts_carry_no_other_vertical_content(g, headline):
    _, _, _, block = _ctx(g, headline)
    for term in ("bitcoin", "mlb", "baseball", "champions league", "halftime",
                 "donalds", "midterm"):
        assert term not in block.lower(), f"leak: {term}"


def test_the_corporate_hub_is_tagged_and_links_its_archetypes(g):
    note = g.notes.get("Vertical: Corporate Events")
    assert note is not None
    assert {"vertical", "market", "corporate"} <= {t.lower() for t in note.tags}
    for arch in ("Market: Corporate IPO Date Ladder",
                 "Market: Corporate Acquisition Announcement",
                 "Market: Corporate CEO Departure",
                 "Market: Corporate Merger Date Ladder"):
        assert arch in note.links, f"hub does not link {arch}"





# ---------------------------------------------------------------- AI vertical
AI_RANK = "Google has the top ranked LLM on the arena leaderboard"
AI_RELEASE = "When will Anthropic release Opus 6"
AI_AGI = "OpenAI announces they have attained AGI"
AI_THRESHOLD = "Which model first hits 1550 on Text Arena"
AI_HUB = "AI and machine learning prediction markets"

# ---------------------------------------------------------------- space vertical
SP_COUNT = "How many SpaceX launches in August"
SP_DATE = "When will Starship flight test 14 launch"
SP_DISCOVERY = "interstellar object confirmed discovery"
SP_HUB = "space and launch prediction markets"


@pytest.mark.parametrize("headline,marker", [
    (AI_RANK, "AI"), (AI_RELEASE, "AI"), (AI_AGI, "AI"),
    (AI_THRESHOLD, "AI"), (AI_HUB, "AI"),
    (SP_COUNT, "Space"), (SP_DATE, "Space"),
    (SP_DISCOVERY, "Space"), (SP_HUB, "Space"),
])
def test_subagent_built_clusters_route_correctly(headline, marker, g):
    """These clusters were written by subagents; verify them like any other."""
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], \
        f"routed to {titles[0] if titles else '(none)'}"


@pytest.mark.parametrize("headline", [AI_RANK, AI_RELEASE, AI_AGI,
                                      AI_THRESHOLD, AI_HUB, SP_COUNT,
                                      SP_DATE, SP_DISCOVERY, SP_HUB])
def test_subagent_built_notes_fill_every_slot(headline, g):
    _, _, expert, block = _ctx(g, headline)
    assert set(expert) == set(SLOT_LABELS), \
        f"missing {set(SLOT_LABELS) - set(expert)}"
    assert 0 < len(block) <= 800


@pytest.mark.parametrize("headline", [AI_RANK, AI_AGI, SP_COUNT, SP_DISCOVERY])
def test_new_clusters_carry_no_other_vertical_content(headline, g):
    _, _, _, block = _ctx(g, headline)
    for term in ("bitcoin", "mlb", "baseball", "champions league", "halftime",
                 "donalds", "midterm", "cpi inflation"):
        assert term not in block.lower(), f"leak: {term}"


@pytest.mark.parametrize("headline", [MLB_SEASON, SOC_MATCH, POLITICS,
                                      CRY_LADDER, CORP_IPO])
def test_established_verticals_carry_no_ai_or_space_content(headline, g):
    _, _, _, block = _ctx(g, headline)
    # NB: not "spacex" -- KXIPOSPACEX is a legitimate IPO target listed in the
    # Corporate hub. Use terms that only the SPACE vertical would carry.
    for term in ("starship", "launch count", "lm arena", "leaderboard"):
        assert term not in block.lower(), f"leak: {term}"


@pytest.mark.parametrize("hub,archetypes", [
    ("Vertical: AI and Machine Learning",
     ["Market: AI Top Model Ranking Field",
      "Market: AI Model Release Date Ladder",
      "Market: AI AGI Declaration Ladder",
      "Market: AI Capability Threshold Race"]),
    ("Vertical: Space and Launch",
     ["Market: Space Launch Count Ladder",
      "Market: Space Launch Date Ladder",
      "Market: Space Mission Exclusive Field",
      "Market: Space Discovery Binary"]),
])
def test_subagent_hubs_link_their_archetypes(hub, archetypes, g):
    note = g.notes.get(hub)
    assert note is not None, f"{hub} missing"
    assert "vertical" in {t.lower() for t in note.tags}
    for arch in archetypes:
        assert arch in note.links, f"{hub} does not link {arch}"
        assert arch in g.notes, f"{arch} note missing"


# ---------------------------------------------------------------- weather vertical
WX_RAIN = "Will it rain in Phoenix today precipitation"
WX_STORM = "first named hurricane of the Atlantic season"
WX_QUAKE = "magnitude 8 earthquake in California epicenter"
WX_HUB = "weather and climate prediction markets"


@pytest.mark.parametrize("headline", [WX_RAIN, WX_STORM, WX_QUAKE, WX_HUB, WEATHER])
def test_weather_headlines_reach_the_weather_cluster(g, headline):
    titles, *_ = _ctx(g, headline)
    assert titles, "no seed matched"
    top = titles[0]
    assert "Weather" in top or "KXHIGHNY" in top, f"routed to {top}"


@pytest.mark.parametrize("headline", [WX_RAIN, WX_STORM, WX_QUAKE, WX_HUB])
def test_weather_notes_fill_every_slot(g, headline):
    _, _, expert, block = _ctx(g, headline)
    assert set(expert) == set(SLOT_LABELS)
    assert 0 < len(block) <= 800


@pytest.mark.parametrize("headline,expected_prefix", [
    ("California governor primary election poll", "State: California"),
    ("Washington state senate race primary", "State: Washington"),
])
def test_geophysical_markers_do_not_hijack_political_place_names(
        g, headline, expected_prefix):
    """Adding earthquake/volcano vocabulary must not pull political state
    notes into weather, nor vice versa. Both directions matter."""
    titles, *_ = _ctx(g, headline)
    assert titles[0].startswith(expected_prefix), f"hijacked by {titles[0]}"


def test_the_retrofitted_hub_links_the_pre_existing_note(g):
    """The weather hub was built AROUND an existing single note; that note
    must be adopted, not orphaned or rewritten."""
    hub = g.notes.get("Vertical: Weather and Climate")
    assert hub is not None
    assert "Market: KXHIGHNY NYC Daily High Temperature" in hub.links
    assert "Market: KXHIGHNY NYC Daily High Temperature" in g.notes


# ---------------------------------------------------------------- NBA vertical
NBA_CHAMP = "Washington wins the Pro Basketball Finals championship"
NBA_NEXTTEAM = "Steph Curry next team free agency destination"
NBA_AWARD = "NBA most valuable player award winner"
NBA_WINS = "Utah wins at least 60 games this basketball season"
NBA_HUB = "NBA pro basketball prediction markets"


@pytest.mark.parametrize("headline", [NBA_CHAMP, NBA_NEXTTEAM, NBA_AWARD,
                                      NBA_WINS, NBA_HUB])
def test_nba_headlines_reach_the_nba_cluster(g, headline):
    titles, *_ = _ctx(g, headline)
    assert titles and "NBA" in titles[0], \
        f"routed to {titles[0] if titles else '(none)'}"


@pytest.mark.parametrize("headline", [NBA_CHAMP, NBA_NEXTTEAM, NBA_AWARD,
                                      NBA_WINS, NBA_HUB])
def test_nba_notes_fill_every_slot(g, headline):
    _, _, expert, block = _ctx(g, headline)
    assert set(expert) == set(SLOT_LABELS)
    assert 0 < len(block) <= 800


# MLB and NBA share the generic sports vocabulary ("season", "wins", "games"),
# so only league-specific words can separate them. Both directions matter.
@pytest.mark.parametrize("headline,league", [
    ("Boston bullpen collapses, pitcher struggles in the ninth inning", "MLB"),
    ("Padres visit Mets tonight, total runs around nine innings", "MLB"),
    ("Utah wins at least 60 games this basketball season", "NBA"),
    ("NBA rebounds and assists leader this season", "NBA"),
])
def test_league_vocabulary_separates_mlb_from_nba(g, headline, league):
    titles, *_ = _ctx(g, headline)
    assert titles and league in titles[0], f"routed to {titles[0]}"


@pytest.mark.parametrize("name", ["washington", "utah", "phoenix",
                                  "portland", "indiana"])
def test_nba_hub_claims_no_bare_place_names(g, name):
    """Bare city/state aliases hijack the 50 political State notes."""
    owner = g.alias_index.get(name)
    assert owner is None or not owner.startswith("Vertical: NBA"), \
        f"{name!r} claimed by the NBA hub"


def test_nba_hub_links_its_archetypes(g):
    note = g.notes.get("Vertical: NBA Pro Basketball")
    assert note is not None
    assert {"vertical", "market", "nba"} <= {t.lower() for t in note.tags}
    for arch in ("Market: NBA Championship Field",
                 "Market: NBA Next Team Destination Field",
                 "Market: NBA Award Winner Field",
                 "Market: NBA Season Wins Ladder"):
        assert arch in note.links and arch in g.notes


# ---------------------------------------------------------- NFL + Economics
NFL_MVP = "Josh Allen wins the AP Regular Season MVP quarterback"
NFL_WINS = "New York Giants win at least 8 games football season"
NFL_DRAFT = "Arch Manning first overall pick in the football draft"
NFL_HUB = "NFL pro football prediction markets"

ECON_FUEL = "gasoline price ladder AAA average"
ECON_RATE = "Federal Reserve FOMC rate decision September"
ECON_RECESSION = "US recession two consecutive quarters GDP"
ECON_HUB = "economics and macro prediction markets"


@pytest.mark.parametrize("headline", [NFL_MVP, NFL_WINS, NFL_DRAFT, NFL_HUB])
def test_nfl_headlines_reach_the_nfl_cluster(g, headline):
    titles, *_ = _ctx(g, headline)
    assert titles and "NFL" in titles[0], f"routed to {titles[0]}"


@pytest.mark.parametrize("headline", [ECON_FUEL, ECON_RATE, ECON_RECESSION,
                                      ECON_HUB,
                                      "CPI inflation expected at 3.4 percent in August"])
def test_economics_headlines_reach_the_economics_cluster(g, headline):
    titles, *_ = _ctx(g, headline)
    top = titles[0]
    assert "Economics" in top or "KXCPIYOY" in top, f"routed to {top}"


@pytest.mark.parametrize("headline", [NFL_MVP, NFL_WINS, NFL_DRAFT, NFL_HUB,
                                      ECON_FUEL, ECON_RATE, ECON_RECESSION,
                                      ECON_HUB])
def test_nfl_and_economics_notes_fill_every_slot(g, headline):
    _, _, expert, block = _ctx(g, headline)
    assert set(expert) == set(SLOT_LABELS)
    assert 0 < len(block) <= 800


def test_the_economics_hub_adopted_the_pre_existing_cpi_note(g):
    """The hub was written around three orphan archetypes left by a subagent
    that died mid-run; it must also adopt the note that predated all of it."""
    hub = g.notes.get("Vertical: Economics and Macro")
    assert hub is not None
    assert {"vertical", "market", "economics"} <= {t.lower() for t in hub.tags}
    for arch in ("Market: KXCPIYOY US CPI Year-over-Year",
                 "Market: Economics Rate Decision Field",
                 "Market: Economics Fuel Price Ladder",
                 "Market: Economics Recession Binary"):
        assert arch in hub.links and arch in g.notes, arch


def test_no_hub_is_left_half_built(g):
    """A hub with fewer than two archetypes, or a dangling archetype link,
    makes the rotation query believe a vertical is finished when it is not.
    A subagent dying mid-run is the realistic way this happens."""
    for hub, note in g.notes.items():
        if "vertical" not in {t.lower() for t in note.tags}:
            continue
        arch = [l for l in set(note.links) if l.startswith("Market: ")]
        assert len(arch) >= 2, f"{hub} links only {len(arch)} archetype(s)"
        missing = [l for l in arch if l not in g.notes]
        assert not missing, f"{hub} links missing notes: {missing}"


def test_every_market_note_is_reachable_from_some_hub(g):
    """An orphan archetype is invisible to anyone browsing the graph."""
    hubs = [n for n in g.notes.values()
            if "vertical" in {t.lower() for t in n.tags}]
    linked = {l for n in hubs for l in n.links if l.startswith("Market: ")}
    market_notes = {t for t, n in g.notes.items() if t.startswith("Market: ")}
    orphans = market_notes - linked
    assert not orphans, f"market notes no hub links: {sorted(orphans)}"


@pytest.mark.parametrize("headline,league", [
    ("Rays favored to win the World Series postseason", "MLB"),
    ("Stanley Cup champion hockey playoff series", "NHL"),
    ("Josh Allen wins the AP Regular Season MVP quarterback", "NFL"),
    ("Utah wins at least 60 games this basketball season", "NBA"),
])
def test_generic_sports_vocabulary_does_not_demote_league_notes(
        g, headline, league):
    """`sports` is a PARENT of the mlb/nba/nfl families. Giving the leagues
    their own families made a generic-sports headline boost the generic NHL
    hub while demoting the MLB championship note to 0.35x, so
    "Rays win the World Series" routed to hockey."""
    titles, *_ = _ctx(g, headline)
    assert titles and league in titles[0], f"routed to {titles[0]}"


# ---------------------------------------------- NHL / combat / equities
@pytest.mark.parametrize("headline,marker", [
    ("Stanley Cup champion hockey playoff series", "NHL"),
    ("Connor McDavid next team hockey", "NHL"),
    ("NHL puck line single game goalie", "NHL"),
    ("UFC bout winner knockout octagon", "Combat"),
    ("method of victory submission or decision", "Combat"),
    ("which round will the bout end", "Combat"),
    ("UFC lightweight title holder", "Combat"),
    ("NASDAQ index level ladder session close", "Equity"),
    ("stock index and equities prediction markets", "Equit"),
])
def test_late_verticals_route_correctly(g, headline, marker):
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0]}"


@pytest.mark.parametrize("headline", [
    "Stanley Cup champion hockey playoff series",
    "UFC bout winner knockout octagon",
    "NASDAQ index level ladder session close",
])
def test_late_verticals_fill_every_slot(g, headline):
    _, _, expert, block = _ctx(g, headline)
    assert set(expert) == set(SLOT_LABELS)
    assert 0 < len(block) <= 800


def test_interrogatives_do_not_match_notes_on_their_own(g):
    """'which round will the bout end' hit a SPACE note via "which" and an
    EQUITY note via "end" before those were stopworded."""
    for junk in ("which", "will", "end", "what", "when", "how"):
        assert junk in VaultGraph.STOPWORDS, f"{junk!r} should be a stopword"


# ---------------------------------------------- domain detection vs stopwords
def test_politics_markers_are_reachable_at_all(g):
    """The bug: domain detection shared the note-MATCHING tokenizer.

    111 political notes are titled `Race: ...` / `State: ...`, so "senate",
    "governor", "election" and "primary" are stopwords -- and those are
    exactly the words DOMAIN_MARKERS["politics"] looks for. Every politics
    marker was therefore unreachable, "Senate race in Georgia" detected NO
    domain, took no politics boost, and routed to an EQUITIES note.
    """
    for headline in ("Senate race in Georgia too close to call",
                     "who leads the governor race polling average",
                     "the presidential primary election result"):
        doms = g._headline_domains(g._domain_tokens(headline))
        assert "politics" in doms, f"{headline!r} -> {doms}"


def test_stopworded_markers_stay_stopwords_for_note_matching(g):
    """The two tokenizers must stay different. Domain detection keeps these

    words; note matching must still drop them, or `Race:` boilerplate starts
    matching every political note again.
    """
    for word in ("senate", "governor", "election", "primary"):
        assert word in VaultGraph.STOPWORDS
        assert word not in set(g._tokens(f"the {word} question"))
        assert word in g._domain_tokens(f"the {word} question")


@pytest.mark.parametrize("headline,marker", [
    ("Senate race in Georgia too close to call", "Georgia"),
    ("NCAA tournament bracket Heisman conference champion", "College"),
    ("Who wins the Dutch Grand Prix pole position", "Motorsport"),
    ("NASCAR race winner at Daytona checkered flag", "Motorsport"),
])
def test_late_clusters_and_politics_route_correctly(g, headline, marker):
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0] if titles else None}"


def test_a_named_league_does_not_lose_to_a_rival_league(g):
    """The `sports` parent boost exists for headlines naming NO league, so

    "Rays win the World Series" can still reach the MLB note. Handing it to
    RIVAL leagues made them compete on raw token overlap: once the College
    cluster landed, "Josh Allen ... MVP quarterback" -- which says `nfl`
    outright -- routed to Market: College Season Wins Ladder.
    """
    titles, *_ = _ctx(g, "Josh Allen wins the AP Regular Season MVP quarterback")
    assert "NFL" in titles[0], f"routed to {titles[0]}"
    # and the generic case must still work
    titles, *_ = _ctx(g, "Rays favored to win the World Series")
    assert "MLB" in titles[0], f"routed to {titles[0]}"


# ---------------------------------------------- Company KPI vs stock indices
@pytest.mark.parametrize("headline,marker", [
    ("Tesla quarterly vehicle deliveries production milestone", "KPI"),
    ("Anthropic funded customers reported metric", "KPI"),
    ("Nvidia gross margin percentage next earnings report", "KPI"),
])
def test_kpi_headlines_reach_the_kpi_cluster(g, headline, marker):
    """KXTESLA / KXAAPLA / KXNVDAA are Fiscal.ai KPI contracts (revenue,

    deliveries, funded customers), NOT single-stock price markets -- Kalshi
    lists none of those. The ticker shape is the biggest trap in Financials,
    and these notes sit next to the index cluster in the same category.
    """
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0] if titles else None}"


@pytest.mark.parametrize("headline", [
    "NASDAQ index level ladder session close",
    "S&P 500 annual range for the year",
])
def test_index_headlines_are_not_captured_by_the_kpi_cluster(g, headline):
    titles, *_ = _ctx(g, headline)
    assert titles and "Equity Index" in titles[0], f"routed to {titles[0]}"


# ---------------------------------------------- Tennis
@pytest.mark.parametrize("headline", [
    "Who wins the ATP Cincinnati tennis match",
    "Alcaraz to win the US Open mens singles",
    "total games in the tennis match over 21.5",
    "will the player withdraw from the tournament",
    "tennis match retirement fair market price",
    "WTA grand slam womens singles winner",
])
def test_tennis_headlines_reach_the_tennis_cluster(g, headline):
    """Tennis needed its own domain family for the same reason college and

    motorsport did: its notes carried the shared `sports` tag, so "Alcaraz to
    win the US Open mens singles" lost on generic token overlap and routed to
    Market: NBA Season Wins Ladder.
    """
    titles, *_ = _ctx(g, headline)
    assert titles and "Tennis" in titles[0], f"routed to {titles[0] if titles else None}"


@pytest.mark.parametrize("headline,marker", [
    ("Stanley Cup champion hockey playoff series", "NHL"),
    ("Rays favored to win the World Series", "MLB"),
    ("Josh Allen wins the AP Regular Season MVP quarterback", "NFL"),
    ("UFC bout winner knockout octagon", "Combat"),
    ("NCAA tournament bracket Heisman conference champion", "College"),
    ("Who wins the Dutch Grand Prix pole position", "Motorsport"),
])
def test_tennis_does_not_capture_the_other_sports(g, headline, marker):
    """Every new sports vertical is a fresh chance to break the league split."""
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0]}"


def test_tennis_fills_every_slot(g):
    for title in ("Vertical: Tennis", "Market: Tennis Match Head-to-Head",
                  "Market: Tennis Player to Compete Binary"):
        expert = g.expert_context([title], max_chars=800)
        assert set(expert) == set(SLOT_LABELS)
        block = "".join(str(v) for v in expert.values())
        assert 0 < len(block) <= 800


# ---------------------------------------------- politics: governance vs elections
@pytest.mark.parametrize("headline,marker", [
    ("Will Trump pardon a family member before the term ends", "Executive Action"),
    ("proof of citizenship voter registration bill becomes law", "Legislative Date"),
    ("comprehensive federal AI legislation passes Congress", "Legislative Date"),
])
def test_governance_headlines_reach_the_governance_notes(g, headline, marker):
    """The Politics category is MAJORITY governance -- tariffs 76, bills 37,

    SCOTUS 28, pardons 18, impeachment 16 -- while all 119 political notes in
    this vault were about elections. These two archetypes are the first
    governance coverage; a pardon headline previously had nowhere to land.
    """
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0] if titles else None}"


@pytest.mark.parametrize("headline,marker", [
    ("Senate race in Georgia too close to call", "Georgia"),
    ("Fishback vs Donalds Florida governor GOP primary", "FL Governor"),
])
def test_governance_notes_do_not_cannibalise_the_election_layer(g, headline, marker):
    """Adding governance notes to a category with 119 election notes is the

    same collision risk that college created for the NFL. The election layer
    is the vault's deepest and must not lose its own headlines.
    """
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0]}"


# ---------------------------------------------- Golf
@pytest.mark.parametrize("headline", [
    "Who wins the BMW Championship golf tournament",
    "first round leader at the Masters",
    "will the golfer make the cut",
    "top 20 finish finishing position golf",
    "career major championships won by a golfer",
])
def test_golf_headlines_reach_the_golf_cluster(g, headline):
    """Golf needed its own domain family, like college/motorsport/tennis

    before it. "will the golfer make the cut" reached NOTHING at all until
    the family and a cut alias existed -- the cut is golf's defining
    mid-event mechanic and had no route into the graph.
    """
    titles, *_ = _ctx(g, headline)
    assert titles and "Golf" in titles[0], f"routed to {titles[0] if titles else None}"


@pytest.mark.parametrize("headline,marker", [
    ("Alcaraz to win the US Open mens singles", "Tennis"),
    ("Who wins the Dutch Grand Prix pole position", "Motorsport"),
    ("Rays favored to win the World Series", "MLB"),
    ("NCAA tournament bracket Heisman conference champion", "College"),
])
def test_golf_does_not_capture_neighbouring_sports(g, headline, marker):
    """Golf shares "tournament", "winner", "open" and "field" with tennis and

    college. 53 substring false positives were excluded when BUILDING the
    vertical; retrieval is where the same collision reappears.
    """
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0]}"


# ---------------------------------------------- Music charts
@pytest.mark.parametrize("headline", [
    "which song will be number one on the Billboard Hot 100",
    "total Spotify streams for the artist this year",
    "will the album be released before December",
    "how many consecutive weeks at number one",
    "top artist in the USA on Spotify",
])
def test_music_headlines_reach_the_music_cluster(g, headline):
    """"will the album be released before December" routed to

    Market: KPI Production Milestone Ladder before music had a domain family
    -- a release-date question is shaped exactly like a production-milestone
    question, so only vocabulary separates them.
    """
    titles, *_ = _ctx(g, headline)
    assert titles and "Music" in titles[0], f"routed to {titles[0] if titles else None}"


@pytest.mark.parametrize("headline,marker", [
    ("Tesla quarterly vehicle deliveries production milestone", "KPI"),
    ("Anthropic funded customers reported metric", "KPI"),
    ("Alcaraz to win the US Open mens singles", "Tennis"),
    ("Senate race in Georgia too close to call", "Georgia"),
])
def test_music_does_not_capture_its_neighbours(g, headline, marker):
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0]}"


# ---------------------------------------------- Awards and screen
@pytest.mark.parametrize("headline", [
    "who wins best picture at the Academy Awards",
    "Emmy nomination for outstanding drama series",
    "Rotten Tomatoes Tomatometer score above 75",
    "who will be cast as the next James Bond",
    "Grammy award winner for album of the year",
])
def test_screen_headlines_reach_the_awards_cluster(g, headline):
    """Two collisions made this vertical need its own family and an alias:

    "Emmy nomination for outstanding drama SERIES" routed to NHL Pro Hockey
    on the shared sports marker `series`, and "GRAMMY award winner for ALBUM
    of the year" is genuinely bi-domain -- the Recording Academy is an awards
    body, so the awards note has to carry the Grammy alias to win it.
    """
    titles, *_ = _ctx(g, headline)
    assert titles and "Screen" in titles[0], f"routed to {titles[0] if titles else None}"


@pytest.mark.parametrize("headline,marker", [
    ("which song will be number one on the Billboard Hot 100", "Music"),
    ("total Spotify streams for the artist this year", "Music"),
    ("will the album be released before December", "Music"),
    ("Stanley Cup champion hockey playoff series", "NHL"),
])
def test_awards_and_music_stay_separated(g, headline, marker):
    """Music and awards are two halves of ONE Kalshi category and share

    "album", "artist", "year" and "winner". They were split into separate
    verticals deliberately; retrieval has to hold that line.
    """
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0]}"


# ---------------------------------------------- Companies vs the corporate clusters
@pytest.mark.parametrize("headline,marker", [
    ("will Tesla announce a layoff this year", "Layoff"),
    ("Carbon Arc consumer spending panel data for Amazon", "Alt-Data"),
    ("Apple antitrust lawsuit court ruling", "Legal Action"),
])
def test_company_headlines_reach_the_companies_cluster(g, headline, marker):
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0] if titles else None}"


@pytest.mark.parametrize("headline,marker", [
    ("chief executive steps down departure", "Corporate CEO"),
    ("when will the merger close date ladder", "Merger"),
    ("when will the company IPO date ladder", "Corporate IPO"),
    ("Tesla quarterly vehicle deliveries production milestone", "KPI"),
    ("Anthropic funded customers reported metric", "KPI"),
])
def test_four_corporate_clusters_stay_separated(g, headline, marker):
    """Companies (515 series) OVERLAPS three existing clusters -- 61.7% of it

    was already covered by Company KPI Markets, Corporate Events and Stock
    Indices. Four clusters now share "company", "announce", "date" and
    "ladder", so retrieval has to hold four lines at once.
    """
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0]}"


def test_corporate_ceo_departure_is_not_captured_by_the_pardon_basket(g):
    """A regression this session created: Market: Politics Executive Action

    Basket (presidential pardons) captured "chief EXECUTIVE steps down" on the
    shared word. Adding governance markers to politics and an executive marker
    to company separated them.
    """
    titles, *_ = _ctx(g, "chief executive steps down departure")
    assert "Corporate CEO" in titles[0]
    titles, *_ = _ctx(g, "Will Trump pardon a family member before the term ends")
    assert "Executive Action" in titles[0]


# ---------------------------------------------- transport / health / sovereign
@pytest.mark.parametrize("headline,marker", [
    ("how many flights will be cancelled at JFK", "Transport"),
    ("freight rate index for trucking", "Transport"),
    ("CDC flu hospitalization rate surveillance", "Health"),
    ("will the WHO declare a public health emergency", "Health"),
    ("FDA drug approval decision", "Health"),
    ("who will be elected pope conclave", "Sovereign"),
    ("will the UK parliament vote of no confidence pass", "Sovereign"),
])
def test_late_small_verticals_route_correctly(g, headline, marker):
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0] if titles else None}"


@pytest.mark.parametrize("headline,marker", [
    ("who will win the World Series", "MLB"),
    ("who wins best picture at the Academy Awards", "Screen"),
    ("who will be the next James Bond", "Screen"),
])
def test_the_interrogative_who_is_not_a_health_marker(g, headline, marker):
    """The WHO (organisation) and "who" (interrogative) are the same token.

    Domain detection deliberately KEEPS stopwords, so putting "who" in the
    health markers would route every "who will win..." headline on the board
    to public health. It is omitted on purpose; these are the guard.
    """
    assert "who" not in VaultGraph.DOMAIN_MARKERS["health"]
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0]}"


def test_spaceflight_is_not_captured_by_aviation(g):
    """"flight" is ambiguous between aviation and SPACEflight. Adding it as a

    transport marker -- and separately as an alias token on the airport
    throughput note -- both routed "When will Starship flight test 14 launch"
    to the airport ladder. Neither carries the bare token now.
    """
    assert "flight" not in VaultGraph.DOMAIN_MARKERS["transport"]
    titles, *_ = _ctx(g, "When will Starship flight test 14 launch")
    assert "Space" in titles[0], f"routed to {titles[0]}"
    titles, *_ = _ctx(g, "how many flights will be cancelled at JFK")
    assert "Transport" in titles[0], f"routed to {titles[0]}"


def test_the_scalar_mechanics_note_is_reachable_but_does_not_hijack(g):
    """A shared MECHANICS note must answer a mechanics question and stay out

    of the way of subject questions. The vault already learned this the hard
    way: a MIDTERM WAVE pattern note once captured "NYC heat wave" and put
    backlash analysis in a weather prompt.
    """
    titles, *_ = _ctx(g, "what happens if the match is abandoned fair market price")
    assert "Scalar Settlement" in titles[0], f"routed to {titles[0]}"
    # ...but a subject headline must still reach its subject note
    for headline, marker in [("Alcaraz to win the US Open mens singles", "Tennis"),
                             ("who wins the BMW Championship golf tournament", "Golf")]:
        titles, *_ = _ctx(g, headline)
        assert marker in titles[0], f"{headline!r} routed to {titles[0]}"


# ---------------------------------------------- player props
@pytest.mark.parametrize("headline,marker", [
    ("will the batter hit a home run tonight", "Player Daily"),
    ("scratched from the starting lineup pinch hit", "Player Daily"),
    ("who leads the league in home runs this season", "Player Season Stat Leader"),
    ("which quarterback passes for 4000 yards", "Player Season Threshold"),
])
def test_player_prop_headlines_reach_the_props_cluster(g, headline, marker):
    """Props are the vault's first PERSON-level contracts and they sit beside

    the team-level notes for the same games. Two collisions had to be fixed:
    motorsport's "starting grid" captured "starting lineup", and a props note
    that was not tagged with its league was demoted 0.35x by an MLB headline.
    """
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0] if titles else None}"


def test_a_note_can_belong_to_two_domain_families(g):
    """KXMLBHR is honestly BOTH a player prop and an MLB contract. Returning

    only the first matching tag meant an MLB headline saw the props note as a
    mismatch and lost it to an AI note that merely shared the word "hit".
    """
    doms = g._note_domains("Market: Player Daily Stat Prop")
    assert {"mlb", "props"} <= doms


def test_the_generic_sports_family_is_dropped_when_a_league_is_present(g):
    """Every league note also carries a literal `sports` tag. Counting both

    would let ANY sports headline match ANY league note -- the exact leak that
    sent an NFL MVP headline to a College note.
    """
    assert g._note_domains("Market: MLB Championship Field") == {"mlb"}
    titles, *_ = _ctx(g, "Josh Allen wins the AP Regular Season MVP quarterback")
    assert "NFL" in titles[0], f"routed to {titles[0]}"


def test_bare_prepositions_are_not_rare_tokens(g):
    """"from" carried idf 4.9 and scored as a DISTINCTIVE token, so one alias

    containing it outranked a real tennis note on "will the player withdraw
    FROM the tournament". A preposition must never be evidence.
    """
    for word in ("from", "into", "than", "that", "this", "with"):
        assert word in VaultGraph.STOPWORDS, f"{word!r} still scores as evidence"
    titles, *_ = _ctx(g, "will the player withdraw from the tournament")
    assert "Tennis" in titles[0], f"routed to {titles[0]}"


# ---------------------------------------------- politics governance archetypes
@pytest.mark.parametrize("headline,marker", [
    ("what tariff rate will be in effect on China", "Tariff Rate"),
    ("will tariff rebate checks be sent to Americans", "Tariff Media Panel"),
    ("will the government shut down in October", "Shutdown"),
    ("will the president be impeached before 2027", "Impeachment"),
    ("will the Senate confirm a new Supreme Court justice", "Judicial Vacancy"),
    ("who will be nominated to the Federal Reserve board", "Nominee Confirmation"),
    ("presidential approval rating below 40 percent", "Approval Rating"),
])
def test_governance_archetypes_route_correctly(g, headline, marker):
    """The governance half of Politics went from 2 archetypes to 9. "Federal

    Reserve BOARD" routed to Vertical: Chess until the nominee note carried
    the vocabulary, and the politics markers had no judicial words at all.
    """
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0] if titles else None}"


@pytest.mark.parametrize("headline,marker", [
    ("Senate race in Georgia too close to call", "Georgia"),
    ("proof of citizenship voter registration bill becomes law", "Legislative Date"),
    ("comprehensive federal AI legislation passes Congress", "Legislative Date"),
    ("chief executive steps down departure", "Corporate CEO"),
])
def test_governance_does_not_swamp_the_election_layer(g, headline, marker):
    """Nine governance notes now sit in a category with 119 election notes."""
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0]}"


# ---------------------------------------------- NFL period + handicap
@pytest.mark.parametrize("headline,marker", [
    ("will the team cover the spread by 7 points", "Handicap"),
    ("who wins the first quarter or is it a tie", "Period Winner"),
    ("total points scored in the first half over 24", "Period Total"),
])
def test_nfl_period_headlines_route_correctly(g, headline, marker):
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0] if titles else None}"


@pytest.mark.parametrize("headline,marker", [
    ("Josh Allen wins the AP Regular Season MVP quarterback", "NFL Season Wins"),
    ("total runs in the game over 9", "MLB Game Totals"),
    ("which quarterback passes for 4000 yards", "Player Season Threshold"),
])
def test_period_notes_do_not_swamp_their_neighbours(g, headline, marker):
    """Three new NFL notes share "total", "points", "quarter" and "spread"

    with the MLB totals ladder and the player season basket.
    """
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0]}"


# ---------------------------------------------- SCOTUS / cabinet
@pytest.mark.parametrize("headline,marker", [
    ("will the Supreme Court grant certiorari", "Certiorari"),
    ("will a cabinet secretary resign or be fired", "Cabinet Departure"),
    ("will the Senate confirm a new Supreme Court justice", "Judicial Vacancy"),
])
def test_court_and_cabinet_headlines_route_correctly(g, headline, marker):
    titles, *_ = _ctx(g, headline)
    assert titles and marker in titles[0], f"routed to {titles[0] if titles else None}"
