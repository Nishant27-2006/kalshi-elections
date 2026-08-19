"""
The 24/7 loop.

Cheap by construction: polls RSS on an interval, kills ~all headlines with
free local checks, and only escalates survivors to paid LLM calls. Writes
every decision -- including rejections -- to an append-only audit log.

Run:
    python -m agent.runner            # continuous
    python -m agent.runner --once     # single cycle (for cron/testing)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from .config import (AUDIT_LOG, KILL_SWITCH, MODELS, POLLING, RISK,
                     SEEN_HASHES, ensure_dirs)
from .graph import build_graph, run_sequential
from .market_lookup import quote_positions, refresh_events_cache
from .nodes import manage_positions, vault
from .portfolio import Portfolio
from .vault_writer import ingest_news

_judge_calls: list[float] = []


def _load_seen() -> set[str]:
    if SEEN_HASHES.exists():
        try:
            return set(json.loads(SEEN_HASHES.read_text()))
        except Exception:
            return set()
    return set()


def _save_seen(seen: set[str]) -> None:
    # bound the file; keep the most recent 5000
    SEEN_HASHES.write_text(json.dumps(list(seen)[-5000:]))


def fetch_news(query: str, hours: int) -> list[dict]:
    url = (f"https://news.google.com/rss/search?q={quote(query)}+when:{hours}h"
           f"&hl=en-US&gl=US&ceid=US:en")
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception:
        return []
    items = []
    for item in root.findall(".//item"):
        title = item.findtext("title") or ""
        src_el = item.find("source")
        items.append({
            "title": title,
            "source": src_el.text if src_el is not None else "",
            "pub_date": item.findtext("pubDate") or "",
            "hash": hashlib.sha256(title.encode()).hexdigest()[:16],
        })
    return items


def audit(record: dict) -> None:
    ensure_dirs()
    record["logged_at"] = datetime.now(timezone.utc).isoformat()
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _judge_budget_ok() -> bool:
    now = time.time()
    _judge_calls[:] = [t for t in _judge_calls if now - t < 3600]
    return len(_judge_calls) < MODELS.max_judge_calls_per_hour


def manage_open_positions() -> dict:
    """Price every open position and close the ones that triggered.

    Runs BEFORE the news pass, every cycle, unconditionally. Exits must not
    depend on a headline happening to mention a ticker we hold -- that was the
    structural reason nothing in this repo ever sold.
    """
    book = Portfolio.load()
    if not book.positions:
        return {"open": 0, "exited": 0}

    tickers = [p.ticker for p in book.positions]
    try:
        from kalshi_client import KalshiClient
        quotes = quote_positions(KalshiClient.from_env(), tickers)
    except Exception as e:
        audit({"stage": "exit_scan_error", "error": str(e)[:300],
               "tickers": tickers})
        return {"open": len(tickers), "exited": 0, "error": str(e)[:120]}

    results = manage_positions(quotes)
    exited = 0
    for r in results:
        if r.get("action") in ("exit_dry_run", "exit_submitted"):
            exited += 1
        if r.get("action") != "hold":
            audit({"stage": "exit", **r})
    return {"open": len(tickers), "exited": exited}


def cycle(graph=None, *, update_vault: bool = True) -> dict:
    """One poll -> process pass. Returns a summary."""
    seen = _load_seen()
    stats = {"fetched": 0, "new": 0, "relevant": 0, "judged": 0,
             "approved": 0, "executed": 0}
    stats["exits"] = manage_open_positions()
    fresh_items: list[dict] = []

    for query in POLLING.queries:
        for item in fetch_news(query, POLLING.news_lookback_hours):
            stats["fetched"] += 1
            if item["hash"] in seen:
                continue
            seen.add(item["hash"])
            stats["new"] += 1

            fresh_items.append(item)

            state = {"news": item, "notes": []}
            try:
                if graph is not None:
                    result = graph.invoke(state)
                else:
                    result = run_sequential(state)
            except Exception as e:
                audit({"stage": "error", "news": item, "error": str(e)[:300]})
                continue

            if not result.get("is_relevant"):
                continue
            stats["relevant"] += 1

            if result.get("judgment"):
                stats["judged"] += 1
                _judge_calls.append(time.time())
            decision = result.get("risk") or {}
            if decision.get("approved"):
                stats["approved"] += 1
            if result.get("executed"):
                stats["executed"] += 1

            audit({
                "stage": "decision",
                "news": item,
                "entities": result.get("entities"),
                "kg_titles": result.get("kg_titles"),
                "market": (result.get("market") or {}).get("ticker"),
                "judgment": result.get("judgment"),
                "risk": decision,
                "executed": result.get("executed", False),
                "execution_result": result.get("execution_result"),
                "terminated_at": result.get("terminated_at"),
            })

    # Political knowledge is a time series. Every headline that reached this
    # cycle carries a pub_date, so it is written into the notes it matches
    # with that timestamp -- otherwise the vault silently ages while the
    # judge keeps reading it as current.
    if update_vault and fresh_items:
        try:
            results = ingest_news(vault(), fresh_items)
            written = sum(r.get("added", 0) for r in results)
            stats["vault_events_added"] = written
            for r in results:
                if r.get("added"):
                    audit({"stage": "vault_update", **r})
        except Exception as e:
            audit({"stage": "vault_update_error", "error": str(e)[:300]})
            stats["vault_events_added"] = 0

    _save_seen(seen)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--no-vault-update", action="store_true",
                    help="do not write timestamped headlines into the vault")
    ap.add_argument("--refresh-markets", action="store_true",
                    help="re-cache the Kalshi open-events list first")
    args = ap.parse_args()

    ensure_dirs()
    graph = build_graph()

    print(f"env={RISK.env}  execution_enabled={RISK.execution_enabled}  "
          f"LIVE={RISK.is_live()}")
    print(f"limits: max_position=${RISK.max_position_usd} "
          f"daily_loss_cap=${RISK.max_daily_loss_usd} "
          f"total_capital=${RISK.total_capital_usd}")
    print(f"poll every {POLLING.interval_seconds}s | kill switch: {KILL_SWITCH}")
    book = Portfolio.load()
    rs = book.risk_state()
    print(f"ledger: {rs.open_positions} open (${rs.deployed_usd:.2f} deployed) "
          f"| today realized ${rs.realized_pnl_today_usd:+.2f}")

    if args.refresh_markets:
        from kalshi_client import KalshiClient
        n = refresh_events_cache(KalshiClient.from_env())
        print(f"cached {n} open election/politics events")

    while True:
        if KILL_SWITCH.exists():
            print("KILL switch present -- halting.")
            return
        started = time.time()
        stats = cycle(graph, update_vault=not args.no_vault_update)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {stats} "
              f"({time.time()-started:.1f}s)")
        if args.once:
            return
        time.sleep(POLLING.interval_seconds)


if __name__ == "__main__":
    main()
