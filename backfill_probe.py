"""Which empty ## Historical Analog slots can actually be backfilled?

The vault's weakest slot is `historical_analog`, and most of it reads "None
recorded". Much of that is CORRECT -- a championship or an IPO resolves once and
has not resolved yet, so its settled feed is empty by construction. Guessing
which notes are backfillable wastes a lot of API calls.

This maps every empty note to the KX tickers named in its own aliases, asks the
settled feed how much history exists, and ranks what is worth writing. Measured
2026-08-19: 35 of 82 empty notes had ANY settled history, and only about eight
had a sample big enough to state a rate.

    python backfill_probe.py                # rank everything
    python backfill_probe.py --min-events 20

Read-only. No auth required.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from agent.config import VAULT_PATH
from agent.history import fetch_settled, group_settled
from kalshi_client import KalshiClient

# A note names its own contracts in its aliases; that is the only reliable
# note -> ticker mapping in the vault, because filenames are archetype names
# ("Market - Tennis Match Games Ladder") and carry no ticker at all.
_TICKER = re.compile(r'"(KX[A-Z0-9]{3,})"')


def empty_analog_notes(vault: pathlib.Path) -> dict[str, list[str]]:
    """Notes whose ## Historical Analog section is still 'None recorded'.

    Counting the SECTION matters: a naive grep for the phrase across the whole
    file also catches hubs and briefs that merely quote it, which is how a
    cached count of 77 survived when the real figure was 102.
    """
    out: dict[str, list[str]] = {}
    for p in sorted(vault.glob("Market*.md")):
        text = p.read_text(encoding="utf-8")
        if "## Historical Analog" not in text:
            continue
        start = text.index("## Historical Analog")
        end = (text.index("## Update Log")
               if "## Update Log" in text else len(text))
        if "None recorded" not in text[start:end]:
            continue
        head = text[:text.index("tags:")] if "tags:" in text else text[:600]
        tickers = _TICKER.findall(head)
        if tickers:
            out[p.stem] = tickers
    return out


def probe(client, tickers: list[str], limit: int = 2):
    """Best (event count, ticker, legs, decided, abandoned) across a note's tickers."""
    best = None
    for tk in tickers[:limit]:
        try:
            markets = fetch_settled(client, tk)
        except Exception:                      # a dead series is not an error
            continue
        if not markets:
            continue
        events = group_settled(markets)
        cand = (len(events), tk, len(markets),
                sum(1 for e in events if e.decided),
                sum(1 for e in events if e.abandoned))
        if best is None or cand[0] > best[0]:
            best = cand
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-events", type=int, default=1,
                    help="only report notes with at least this many settled events")
    ap.add_argument("--vault", default=str(VAULT_PATH))
    args = ap.parse_args()

    vault = pathlib.Path(args.vault)
    empty = empty_analog_notes(vault)
    print(f"{len(empty)} empty notes name a KX ticker in their aliases")

    client = KalshiClient.from_env()
    rows = []
    for note, tickers in empty.items():
        best = probe(client, tickers)
        if best and best[0] >= args.min_events:
            rows.append((best[0], note, best[1], best[2], best[3], best[4]))

    rows.sort(reverse=True)
    print(f"{len(rows)} have >= {args.min_events} settled event(s)\n")
    for n_ev, note, tk, legs, decided, abandoned in rows:
        print(f"  {n_ev:5} events | {tk:22} | decided {decided:5} | "
              f"abandoned {abandoned:4} | {note}")
    if not rows:
        print("  nothing to backfill at this threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
