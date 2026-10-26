"""Labeled headlines for measuring retrieval precision.

WHY A FIXED SET: "the retrieval feels better" is not a result. Every claim
about headline routing in this repo is measured against this list, and the
list is written down so a change that improves one vertical at another's
expense is visible instead of invisible.

Each entry is (headline, expected_vertical_substring). The expectation is a
SUBSTRING of the correct note title rather than an exact title, because the
right answer is "it routed to the MLB cluster", not "it picked note #3".

`None` means the headline is DELIBERATELY out of scope -- Kalshi lists no
market for it -- and the correct behaviour is to return NOTHING. A retriever
that always answers is worse than one that abstains, because a confident
wrong context block is what actually loses money.
"""

# (headline, expected substring in a retrieved note title, or None)
HEADLINES: list[tuple[str, str | None]] = [
    # --- baseball: nicknames, cities, and abbreviations all appear in the wild
    ("Yankees rally past Red Sox in the ninth to take the series", "MLB"),
    ("Dodgers clinch NL West with a walk-off homer", "MLB"),
    ("Brewers beat Braves 6-2 behind seven shutout innings", "MLB"),
    ("Aaron Judge hits 50th home run of the season", "MLB"),
    ("Milwaukee wins its eighth straight", "MLB"),

    # --- football
    ("Chiefs quarterback ruled out for Sunday with ankle sprain", "NFL"),
    ("Titans upset the Bears in overtime", "NFL"),
    ("Eagles clinch playoff berth with win over Cowboys", "NFL"),

    # --- tennis
    ("Djokovic withdraws from the US Open citing wrist injury", "Tennis"),
    ("Frances Tiafoe advances to the quarterfinals in straight sets", "Tennis"),

    # --- macro / rates
    ("Fed holds rates steady, signals one cut before year end", "Econom"),
    # "CPI" rather than "Econom": the router resolves this to
    # "Market: KXCPIYOY US CPI Year-over-Year", which is MORE specific than the
    # Economics hub the original label demanded. The label was wrong, not the
    # route -- corrected here rather than left as a fake miss.
    ("CPI comes in hotter than expected at 3.4 percent", "CPI"),
    ("Jobs report shows unemployment ticking up to 4.3 percent", "Econom"),

    # --- crypto
    ("Bitcoin tops $95,000 after ETF inflows hit record", "Crypto"),
    ("Ethereum slides below $3,000 as traders take profit", "Crypto"),

    # --- politics / governance
    ("Trump signs executive order on semiconductor tariffs", "Politic"),
    ("Supreme Court agrees to hear the tariff challenge", "Politic"),

    # --- entertainment
    ("Taylor Swift announces surprise album, tops Spotify chart", "Music"),
    ("Oppenheimer sequel leads Oscar nominations", "Award"),

    # --- space, AI, weather
    ("SpaceX Starship completes first orbital refuelling test", "Space"),
    ("OpenAI releases GPT-6, tops LM Arena leaderboard", "AI"),
    ("Hurricane Delta strengthens to Category 4 near Florida", "Weather"),

    # --- ABSTENTION CASES: Kalshi lists nothing for these.
    # A retriever that answers here is inventing relevance.
    ("Local bakery wins award for sourdough", None),
    ("Man rescues cat from tree in suburban Ohio", None),
    ("New study links sleep quality to afternoon light exposure", None),
]


def score(retrieve, headlines=None) -> dict:
    """Run a retrieval callable over the set and count outcomes.

    `retrieve(headline) -> list[str]` of note titles, best first.
    """
    rows = headlines if headlines is not None else HEADLINES
    in_scope = [(h, e) for h, e in rows if e is not None]
    out_scope = [(h, e) for h, e in rows if e is None]

    hit1 = hit3 = miss = 0
    wrong: list[tuple[str, str, list[str]]] = []
    for h, exp in in_scope:
        got = retrieve(h) or []
        if not got:
            miss += 1
            wrong.append((h, exp, []))
            continue
        if exp.lower() in got[0].lower():
            hit1 += 1
            hit3 += 1
        elif any(exp.lower() in t.lower() for t in got[:3]):
            hit3 += 1
            wrong.append((h, exp, got[:3]))
        else:
            wrong.append((h, exp, got[:3]))

    false_alarms = [(h, (retrieve(h) or [])[:2])
                    for h, _ in out_scope if retrieve(h)]
    n = len(in_scope)
    return {
        "n_in_scope": n,
        "precision_at_1": hit1 / n if n else 0.0,
        "recall_at_3": hit3 / n if n else 0.0,
        "silent_misses": miss,
        "n_out_of_scope": len(out_scope),
        "false_alarms": len(false_alarms),
        "false_alarm_detail": false_alarms,
        "wrong": wrong,
    }
