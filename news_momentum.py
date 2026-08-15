"""
Cross-reference recent political news (Google News RSS, `when:Nh` recency
filter) against live Kalshi markets to find news-driven momentum.

This is deliberately NOT a prediction of what will move — it's a detector:
(1) what broke in the last N hours, (2) does it map to a tracked entity
(state, district, candidate) in the vault, (3) is there real Kalshi price
action correlating with it.

Google News' `when:Nh` query operator is undocumented-but-reliable; the RSS
endpoint is fetchable directly with `requests` (no API key, no WebFetch
tool dependency — this runs standalone).

Usage:
    python news_momentum.py                      # last 3h, default query
    python news_momentum.py --hours 6 --query "senate race"
"""

import argparse
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from kalshi_client import KalshiClient

load_dotenv()

# Entities the vault tracks — states, districts, candidates, keywords.
# Extend this as the vault's coverage grows (pull from watchlist.py too).
VAULT_ENTITIES = {
    "Michigan Senate / El-Sayed": {
        "keywords": ["el-sayed", "el sayed", "michigan senate", "michigan primary", "rogers"],
        "kalshi_event": "KXMISENGOVCOMBO-26NOV",
        "series_ticker": "KXMISENGOVCOMBO",
    },
    "Ohio-7 / Max Miller scandal": {
        "keywords": ["max miller", "husted", "moreno", "ohio 7", "oh-07"],
        "kalshi_event": "KXMIDTERMVOTETURN-OH07",  # turnout only; no winner market found yet
        "series_ticker": "KXMIDTERMVOTETURN",
    },
    "New Hampshire Governor": {
        "keywords": ["kiper", "new hampshire gov", "nh governor"],
        "kalshi_event": None,
    },
    "North Carolina-11 / Chuck Edwards": {
        "keywords": ["chuck edwards", "nc-11", "western north carolina"],
        "kalshi_event": None,
    },
    "South Carolina Governor": {
        "keywords": ["evette", "sc gov", "south carolina governor", "sanford"],
        "kalshi_event": None,
    },
    "Fauci contempt vote": {
        "keywords": ["fauci", "contempt"],
        "kalshi_event": None,
    },
}


def fetch_news(query: str, hours: int) -> list[dict]:
    url = (f"https://news.google.com/rss/search?q={quote(query)}+when:{hours}h"
           f"&hl=en-US&gl=US&ceid=US:en")
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    items = []
    for item in root.findall(".//item"):
        title = item.findtext("title") or ""
        pub_date = item.findtext("pubDate") or ""
        source_el = item.find("source")
        source = source_el.text if source_el is not None else ""
        items.append({"title": title, "pub_date": pub_date, "source": source})
    return items


def match_entities(news_items: list[dict]) -> dict:
    hits = {name: [] for name in VAULT_ENTITIES}
    for item in news_items:
        title_lower = item["title"].lower()
        for name, info in VAULT_ENTITIES.items():
            if any(kw in title_lower for kw in info["keywords"]):
                hits[name].append(item)
    return {k: v for k, v in hits.items() if v}


def check_kalshi_momentum(client: KalshiClient, entity_name: str, info: dict, hours: int) -> None:
    import time
    if not info.get("kalshi_event"):
        print(f"    No Kalshi market located yet for this entity.")
        return
    try:
        md = client.get_markets(event_ticker=info["kalshi_event"])  # no status filter — it
        # has repeatedly under-returned real live markets when combined with status=open
    except Exception as e:
        print(f"    Kalshi lookup failed: {e}")
        return
    markets = md.get("markets", [])
    if not markets:
        print(f"    Event {info['kalshi_event']} returned no markets from the API right now"
              f" (known Kalshi listing quirk — try the ticker directly if you have it).")
        return
    print(f"    {len(markets)} market(s) found under {info['kalshi_event']}:")
    now = int(time.time())
    for m in markets[:6]:
        tk = m.get("ticker")
        try:
            cd = client.get_market_candlesticks(
                series_ticker=info["series_ticker"], ticker=tk,
                start_ts=now - hours * 3600, end_ts=now, period_interval=60,
            )
        except Exception:
            continue
        priced = [c for c in cd.get("candlesticks", []) if c.get("price", {}).get("close_dollars")]
        vol = sum(float(c.get("volume_fp") or 0) for c in cd.get("candlesticks", []))
        title = (m.get("title") or m.get("yes_sub_title") or "")[:60]
        if len(priced) >= 2:
            first = float(priced[0]["price"]["close_dollars"])
            last = float(priced[-1]["price"]["close_dollars"])
            tag = "MOVED" if abs(last - first) > 0.001 else "flat"
            print(f"      {tk}: {first:.3f}->{last:.3f} (Δ{last-first:+.3f}) vol={vol:.0f} [{tag}]  {title}")
        elif priced:
            print(f"      {tk}: 1 priced candle only, vol={vol:.0f} (thin)  {title}")
        else:
            print(f"      {tk}: no trades in window  {title}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=3, help="News + market lookback window")
    parser.add_argument("--query", default="politics", help="Google News search query")
    args = parser.parse_args()

    print(f"Fetching political news from the last {args.hours}h...")
    news = fetch_news(args.query, args.hours)
    print(f"{len(news)} headlines found.\n")

    hits = match_entities(news)
    if not hits:
        print("No headlines matched a tracked vault entity in this window.")
        return

    client = KalshiClient.from_env()

    print("=== Vault entities with breaking news in the window ===\n")
    for entity, items in hits.items():
        print(f"## {entity}  ({len(items)} headline(s))")
        for it in items[:5]:
            print(f"  - [{it['source']}] {it['title']}  ({it['pub_date']})")
        print(f"  Kalshi momentum check:")
        check_kalshi_momentum(client, entity, VAULT_ENTITIES[entity], args.hours)
        print()


if __name__ == "__main__":
    main()
