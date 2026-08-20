"""Measured abandonment rates: how often a contract settles at a price
rather than YES/NO.

The settled feed's `result` has THREE values -- `yes`, `no`, and `scalar`.
`scalar` marks a settlement at an exchange-set price, so a fraction of every
position's capital has an administratively-determined return regardless of
whether the thesis was right. Standard position sizing has no term for this.

Every number below was measured from Kalshi's own settled feed (see
LOOP_LOG.md findings 266-270, 305, 349-352, 354-357). Refresh with:

    python -c "import sys;sys.path.insert(0,'.');\\
from kalshi_client import KalshiClient;\\
from agent.history import fetch_settled,group_settled,void_rate;\\
r=void_rate(group_settled(fetch_settled(KalshiClient.from_env(),'KXATPMATCH')));\\
print(r.hits,'/',r.total)"
"""
from __future__ import annotations

# vertical -> measured event-level void rate
VOID_RATES: dict[str, float] = {
    "scheduled_data": 0.000,   # charts, daily crypto ladders, index sessions
    "mlb_game": 0.005,         # 4 of 876
    "mlb_player_leg": 0.009,   # 21 of 2,400 LEGS -- see note below
    "ufc_method": 0.017,       # 2 of 115
    "atp_match": 0.037,        # 35 of 944
    "wta_match": 0.040,        # 38 of 956
    "tennis_games_ladder": 0.053,   # 43 of 804
    "ufc_bout": 0.071,         # 9 of 127
    "esports_series": 0.099,   # 119 of 1,200 -- a FLOOR, cursor outstanding
}

# A caller that proceeds without a measurement must not be handed an
# optimistic number, so the fallback is the WORST observed rate.
DEFAULT_VOID_RATE: float = max(VOID_RATES.values())

# Series prefix -> vertical. The table is checked IN ORDER, first match
# wins -- so a future entry whose prefix is itself a prefix of an EARLIER
# entry's prefix (e.g. adding a bare "KXMLB" rule) would need to come AFTER
# the more specific entries it must not shadow, such as KXMLBGAME. As it
# stands today no entry's prefix is a prefix of another's, so order does
# not currently affect any match -- this is a constraint on future entries,
# not a description of the current table.
_PREFIX_RULES: list[tuple[str, str]] = [
    ("KXMLBHR", "mlb_player_leg"),
    ("KXMLBRBI", "mlb_player_leg"),
    ("KXMLBGAME", "mlb_game"),
    ("KXATPGTOTAL", "tennis_games_ladder"),
    ("KXWTAGTOTAL", "tennis_games_ladder"),
    ("KXATPMATCH", "atp_match"),
    ("KXWTAMATCH", "wta_match"),
    ("KXUFCMOV", "ufc_method"),
    ("KXUFCVICROUND", "ufc_method"),
    ("KXUFCFIGHT", "ufc_bout"),
    ("KXCS2GAME", "esports_series"),
    ("KXCS2MAP", "esports_series"),
    ("KXLOLGAME", "esports_series"),
    ("KXBTCD", "scheduled_data"),
    ("KXBTC15M", "scheduled_data"),
    ("KXINXU", "scheduled_data"),
    ("KXTOPSONG", "scheduled_data"),
    ("KXTOPALBUM", "scheduled_data"),
    ("KXRAIN", "scheduled_data"),
]


def vertical_for_series(series_ticker: str) -> str | None:
    """The vertical whose measured void rate applies, or None if unmeasured."""
    t = (series_ticker or "").upper()
    for prefix, vertical in _PREFIX_RULES:
        if t.startswith(prefix):
            return vertical
    return None


def void_rate_for_series(series_ticker: str) -> float | None:
    """Measured rate for this series, or None. NEVER guesses."""
    vertical = vertical_for_series(series_ticker)
    return VOID_RATES[vertical] if vertical else None
