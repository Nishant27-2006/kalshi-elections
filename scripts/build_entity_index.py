"""Rebuild the headline entity index from the live API.

Run this on a schedule -- daily is enough for team sports, and before any
session that will route headlines. The index is a CACHE of what Kalshi lists
right now: a player traded to another club, a school added to the board, or a
new expansion team all change it, and a stale index silently stops routing
the headlines that matter most.

The output is git-ignored. It is derived data, rebuildable in about 30
seconds, and it would otherwise be a 20 KB blob churning in every diff.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.entity_index import add_subject_terms, build_from_markets
from find_momentum import _all_open_markets
from kalshi_client import KalshiClient

# Series whose `yes_sub_title` names a TEAM, PLAYER or SCHOOL.
ENTITY_SERIES = [
    "KXMLBGAME", "KXMLBTOTAL", "KXMLBSPREAD", "KXMLBHR", "KXNFLGAME",
    "KXWNBAGAME", "KXATPMATCH", "KXWTAMATCH", "KXMLSGAME", "KXNCAAFGAME",
    "KXNHLGAME", "KXNBAGAME", "KXEPLGAME", "KXUCL", "KXNCAABGAME",
]

# Series whose subtitle is a PRICE STRIKE, so the subject lives in the title.
SUBJECT_SERIES = [
    "KXBTCD", "KXETHD", "KXCPIYOY", "KXFED", "KXHIGHNY", "KXNASDAQ100",
    "KXINXU", "KXAAAGAS", "KXU3", "KXPAYROLLS", "KXTRUMPPARDONS",
    "KXELECTIONBILL", "KXIMPEACH", "KXALIENS", "KXSPOTIFY", "KXROTTEN",
]

OUT = Path("state/_entity_index.json")


def main() -> int:
    client = KalshiClient.from_env()
    markets, titles = {}, {}
    skipped = []
    for series in ENTITY_SERIES + SUBJECT_SERIES:
        try:
            found = _all_open_markets(client, series, page_size=200)
        except Exception as exc:            # noqa: BLE001 - one bad series
            # Announce, never swallow: a series that silently vanishes from
            # the index is a whole vertical the router stops answering for.
            skipped.append(f"{series} ({type(exc).__name__})")
            continue
        if not found:
            skipped.append(f"{series} (no open markets)")
            continue
        if series in ENTITY_SERIES:
            markets[series] = found
        titles[series] = {(m.get("title") or "") for m in found}

    index = build_from_markets(markets)
    add_subject_terms(index, titles)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    index.save(OUT)

    print(f"{len(index.by_phrase)} phrases  "
          f"{len(index.strong_singles)} subject terms  "
          f"{len(index.series_seen)} series  -> {OUT}")
    if skipped:
        print(f"skipped {len(skipped)}: {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
