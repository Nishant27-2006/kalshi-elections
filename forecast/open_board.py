"""Rank open Elections/Politics events by open interest (GET only)."""
import json, os, sys
from forecast.kalshi_data import _paginate, CACHE, _dump

def main():
    evs = _paginate("/events", {"status": "open", "with_nested_markets": "true"}, "events", limit=200)
    rows = []
    for e in evs:
        if e.get("category") not in ("Elections", "Politics"):
            continue
        ms = e.get("markets") or []
        oi = sum(float(m.get("open_interest_fp") or 0) for m in ms)
        vol = sum(float(m.get("volume_fp") or 0) for m in ms)
        rows.append({"event_ticker": e["event_ticker"], "series_ticker": e.get("series_ticker"),
                     "title": e.get("title"), "category": e.get("category"), "n_markets": len(ms),
                     "oi": oi, "volume": vol,
                     "close": max((m.get("close_time") or "" for m in ms), default=""),
                     "rules": (ms[0].get("rules_primary") if ms else "")})
    rows.sort(key=lambda r: -r["oi"])
    _dump(os.path.join(CACHE, "open_board.json"), rows)
    print(len(rows), "open political events")
    for r in rows[:120]:
        print(f'{r["oi"]:>12,.0f} {r["event_ticker"]:<34} {r["close"][:10]} {r["title"][:80]}')

if __name__ == "__main__":
    main()
