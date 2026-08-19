"""
Map a news headline / matched entities to live Kalshi markets.

Kalshi's series taxonomy for elections is inconsistent (HOUSEPARTY-<ST><NN>,
HOUSE<ST><NN>, KX<ST><NN>D/R, plus KXMIDTERMVOTETURN-* turnout contracts),
and `?series_ticker=` filtering has proven unreliable for several election
series while `?event_ticker=` works. So we cache the open-event list and do
keyword matching locally rather than trusting server-side filters.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .config import REPO_ROOT, STATE_DIR
from .state import MarketSnapshot

EVENTS_CACHE = STATE_DIR / "open_election_events.json"
LEGACY_CACHE = REPO_ROOT / "open_election_events.json"

STOP = {"the", "and", "for", "with", "says", "new", "after", "from", "that",
        "will", "his", "her", "amid", "over", "into", "out", "who", "how"}


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", s.lower())
            if len(t) >= 4 and t not in STOP}


def load_events() -> list[dict]:
    for p in (EVENTS_CACHE, LEGACY_CACHE):
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
    return []


def refresh_events_cache(client) -> int:
    """Page through open events, keep Elections/Politics, cache locally."""
    events: list[dict] = []
    cursor = None
    for _ in range(8):
        kwargs = {"status": "open", "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        data = client.get_events(**kwargs)
        batch = data.get("events") or []
        events.extend(e for e in batch
                      if e.get("category") in ("Elections", "Politics"))
        cursor = data.get("cursor")
        if not cursor:
            break
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    EVENTS_CACHE.write_text(json.dumps(events, indent=1), encoding="utf-8")
    return len(events)


def _dollars_to_cents(v) -> float | None:
    """Kalshi FixedPointDollars ("0.9850") -> cents (98.5). None stays None."""
    if v is None:
        return None
    try:
        return float(v) * 100.0
    except (TypeError, ValueError):
        return None


def _fp(v) -> float:
    """Kalshi FixedPointCount ("7000239.28") -> float. Missing -> 0.0."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _snapshot(client, series_ticker: str, market: dict) -> MarketSnapshot:
    ticker = market.get("ticker", "")
    # Kalshi fixed-point fields: prices are dollar-strings under a _dollars
    # suffix ("0.9850"), quantities use _fp. The bare yes_bid/yes_ask keys are
    # gone and read as None -- see docs.kalshi.com/getting_started/
    # fixed_point_migration. Convert to cents here so the rest of the agent
    # (and risk.py's cent-denominated limits) keep working unchanged.
    bid = _dollars_to_cents(market.get("yes_bid_dollars"))
    ask = _dollars_to_cents(market.get("yes_ask_dollars"))
    depth = 0.0
    try:
        ob = client.get_orderbook(ticker)
        book = ob.get("orderbook_fp", {})
        yes_levels = book.get("yes_dollars") or []
        no_levels = book.get("no_dollars") or []
        depth = sum(float(q) for _, q in yes_levels[-5:]) + \
                sum(float(q) for _, q in no_levels[-5:])
        # derive quotes from the book when the market payload omits them
        if yes_levels and bid is None:
            bid = float(yes_levels[-1][0]) * 100
        if no_levels and ask is None:
            ask = 100.0 - float(no_levels[-1][0]) * 100
    except Exception:
        pass
    bid_c = float(bid) if bid is not None else 0.0
    ask_c = float(ask) if ask is not None else 0.0
    return {
        "ticker": ticker,
        "series_ticker": series_ticker,
        "title": market.get("title") or market.get("yes_sub_title") or "",
        "yes_bid_cents": bid_c,
        "yes_ask_cents": ask_c,
        "spread_cents": max(0.0, ask_c - bid_c),
        "book_depth_contracts": depth,
        "last_price_cents": _dollars_to_cents(market.get("last_price_dollars")) or 0.0,
        "volume_recent": _fp(market.get("volume_24h_fp")),
        # carried so a filled position knows its own deadline; without it the
        # time-based exit in agent/exits.py can never arm
        "close_time": market.get("close_time") or "",
    }


def quote_positions(client, tickers: list[str]) -> dict[str, dict]:
    """Fresh snapshots for tickers we already hold, keyed by ticker.

    Separate from find_candidate_markets: exits must be priced every cycle
    regardless of whether any headline happened to mention the position.
    """
    quotes: dict[str, dict] = {}
    for t in tickers:
        try:
            market = (client.get_market(t) or {}).get("market", {})
        except Exception:
            continue
        if not market:
            continue
        quotes[t] = _snapshot(client, market.get("event_ticker", ""), market)
    return quotes


def find_candidate_markets(headline: str, entities: list[str], client=None,
                            max_events: int = 3) -> list[MarketSnapshot]:
    """Return live market snapshots plausibly related to this headline."""
    events = load_events()
    if not events:
        return []

    want = _tokens(headline) | {t for e in entities for t in _tokens(e)}
    if not want:
        return []

    scored: list[tuple[int, dict]] = []
    for e in events:
        hay = _tokens(f"{e.get('title','')} {e.get('event_ticker','')} "
                      f"{e.get('sub_title','')}")
        overlap = len(want & hay)
        if overlap:
            scored.append((overlap, e))
    if not scored:
        return []
    scored.sort(key=lambda x: x[0], reverse=True)

    if client is None:
        try:
            from kalshi_client import KalshiClient
            client = KalshiClient.from_env()
        except Exception:
            return []

    snapshots: list[MarketSnapshot] = []
    for _, event in scored[:max_events]:
        try:
            md = client.get_markets(event_ticker=event["event_ticker"])
        except Exception:
            continue
        for m in (md.get("markets") or [])[:4]:
            snapshots.append(_snapshot(client, event.get("series_ticker", ""), m))
    # best quoted markets first
    snapshots.sort(key=lambda s: (s["yes_bid_cents"] <= 0, s["spread_cents"]))
    return snapshots
