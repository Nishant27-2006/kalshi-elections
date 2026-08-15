"""
Curated ticker map: vault-tracked 2026 races -> real Kalshi series tickers.

Discovered live on 2026-08-06 via `fetch_political_markets.py` against the
production API (confirmed real, category="Elections" — NOT "Politics",
which is why a naive category filter misses them). Two ticker families
coexist per district:

    HOUSEPARTY-<ST><NN>   general-election, party-winner market
                          (confirmed live: HOUSEPARTY-MI07 = the exact
                          "MI-07 House winner?" market from the Kalshi
                          screenshot — William Lawrence vs Tom Barrett)
    HOUSE<ST><NN>         alt/legacy general-election series seen for
                          some districts (no hyphen, no "PARTY")
    KX<ST><NN>D / R       primary-nominee markets (who wins the D/R primary)

KNOWN GAP: `HOUSEPARTY-MI07` returns 0 events via `/events?series_ticker=`
and `/markets?series_ticker=` as of this writing, despite the series
existing and a market for it clearly trading in the Kalshi app (per the
user's screenshot: $35,252 volume, Yes 68c/No 39c on Lawrence). This may
mean the specific 2026 event hasn't been linked to the series in the
public API yet, or needs a param this client doesn't send. Re-run
`fetch_political_markets.py --series HOUSEPARTY-MI07` periodically, or
try `--event <ticker>` once you find the event ticker in the Kalshi app
(visible in the market URL).

Cross-referenced against the vault's battleground-district picks
(Cook Political Report toss-up list, June 2026 + Apr 2026 PA-08 update)
in C:\\Users\\nisha\\Desktop\\obsidian-personal-space\\vault\\.
"""

# district -> (general-election series ticker, vault note file, notes)
WATCHLIST = {
    "MI-07": {
        "series": "HOUSEPARTY-MI07",
        "incumbent": "Tom Barrett (R)",
        "challenger": "William Lawrence (D)",
        "vault_note": "Race - 2026 MI-07 House – Lawrence vs Barrett.md",
        "status": "series confirmed live; events endpoint currently empty — see module docstring",
    },
    "NY-17": {"series": "HOUSENY17", "incumbent": "Mike Lawler (R)"},
    "NJ-07": {"series": "KXNJ07D", "note": "primary-nominee ticker found; general-election series not yet located"},
    "PA-08": {"series": None, "note": "not yet located — search fetch_political_markets.py --search 'PA-08' / 'Bresnahan'"},
    "PA-07": {"series": "KXPA07D", "note": "primary-nominee ticker found; general-election series not yet located"},
    "PA-10": {"series": "HOUSEPA10", "incumbent": "Scott Perry (R)"},
    "CO-08": {"series": None, "note": "not yet located — search fetch_political_markets.py --search 'CO-08' / 'Evans'"},
    "AZ-01": {"series": "KXAZ01D / KXAZ01R", "note": "primary-nominee tickers found (both parties); general series not yet located"},
    "AZ-06": {"series": None, "note": "not yet located"},
    "NE-02": {"series": None, "note": "not yet located"},
    "IA-01": {"series": None, "note": "not yet located"},
    "CA-13": {"series": "HOUSECA13", "incumbent": "Adam Gray (D)"},
    "CA-45": {"series": "HOUSECA45", "incumbent": "Derek Tran (D)"},
    "ME-02": {"series": "KXME02D", "incumbent": "Jared Golden (D)", "note": "primary-nominee ticker found; general-election series not yet located"},
    "NM-02": {"series": None, "note": "not yet located"},
    "NC-01": {"series": "KXNC01R", "incumbent": "Don Davis (D)", "note": "primary-nominee ticker found (R side); general-election series not yet located"},
    "OH-09": {"series": None, "note": "not yet located"},
    "OH-13": {"series": "HOUSEOH13", "incumbent": "Emilia Sykes (D)"},
    "TX-34": {"series": "HOUSETX34", "incumbent": "Vicente Gonzalez (D)"},
    "WA-03": {"series": None, "note": "not yet located"},
    # Chamber-control and state presidential-line markets (confirmed real):
    "US House control": {"series": "HOUSE", "note": "aggregate chamber-control market, category=Elections"},
}


def print_watchlist() -> None:
    for district, info in WATCHLIST.items():
        series = info.get("series") or "??? not yet located"
        print(f"{district:16s} {series}")
        if info.get("incumbent"):
            print(f"{'':16s}   incumbent: {info['incumbent']}")
        if info.get("note"):
            print(f"{'':16s}   note: {info['note']}")


if __name__ == "__main__":
    print_watchlist()
