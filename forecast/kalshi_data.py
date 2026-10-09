"""Read-only fetch of resolved Kalshi political markets and their daily candles.

GET only. Nothing here can place, amend or cancel an order.

Kalshi splits settled markets across two endpoint families: markets settled
before the historical cutoff (2026-08-09 when this was written, see
/historical/cutoff) live under /historical/markets, newer ones under
/markets?status=settled. Both are read and merged by ticker.

    python -m forecast.kalshi_data series      # Elections + Politics series list
    python -m forecast.kalshi_data markets     # settled markets per series
    python -m forecast.kalshi_data candles     # daily candles for the universe
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data_cache")
CANDLE_DIR = os.path.join(CACHE, "candles")
CATEGORIES = ("Elections", "Politics")

# Universe filter applied before spending candle calls. Final volume is an
# end-of-life field, so it is used ONLY to cut API cost, never as a feature;
# the backtest re-filters on liquidity observed at decision time.
MIN_FINAL_VOLUME = 200.0
MIN_LIFE_DAYS = 3.0

_lock = threading.Lock()
_last = [0.0]
MIN_INTERVAL = 0.2  # ~5 req/s; the IP is shared with research agents hitting the same API

_session = requests.Session()
_n429 = [0]


def _get(path: str, params: dict | None = None) -> dict:
    for attempt in range(12):
        with _lock:
            wait = _last[0] + MIN_INTERVAL - time.time()
            if wait > 0:
                time.sleep(wait)
            _last[0] = time.time()
        try:
            r = _session.get(BASE + path, params=params, timeout=30)
        except requests.RequestException:
            time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            _n429[0] += 1
            time.sleep(min(4.0, 0.5 * 2 ** attempt))
            continue
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"GET {path} {params} failed after retries")


def ts(iso: str | None) -> float | None:
    if not iso:
        return None
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def fetch_series() -> list[dict]:
    out = {}
    for cat in CATEGORIES:
        d = _get("/series", {"category": cat})
        for s in d.get("series") or []:
            s["_category"] = cat
            out[s["ticker"]] = s
    rows = list(out.values())
    _dump(os.path.join(CACHE, "series.json"), rows)
    print(f"series: {len(rows)}")
    return rows


def _paginate(path: str, params: dict, key: str, limit: int = 1000) -> list[dict]:
    out, cursor = [], None
    for _ in range(2000):
        p = dict(params, limit=limit)
        if cursor:
            p["cursor"] = cursor
        d = _get(path, p)
        out.extend(d.get(key) or [])
        cursor = d.get("cursor")
        if not cursor:
            break
    return out


def _settled_for_series(series: str) -> list[dict]:
    live = _paginate("/markets", {"series_ticker": series, "status": "settled"}, "markets")
    hist = _paginate("/historical/markets", {"series_ticker": series}, "markets")
    for m in live:
        m["_source"] = "live"
    for m in hist:
        m["_source"] = "historical"
    merged = {m["ticker"]: m for m in hist}
    merged.update({m["ticker"]: m for m in live})
    for m in merged.values():
        m["_series"] = series
    return list(merged.values())


def fetch_markets(workers: int = 4) -> None:
    series = _load(os.path.join(CACHE, "series.json"))
    out_path = os.path.join(CACHE, "markets.jsonl")
    done = set()
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as fh:
            for line in fh:
                done.add(json.loads(line)["_series"])
    todo = [s for s in series if s["ticker"] not in done]
    print(f"series to scan: {len(todo)} (already {len(done)})", flush=True)
    meta = {s["ticker"]: s for s in series}
    n = 0
    with open(out_path, "a", encoding="utf-8") as fh, ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(_settled_for_series, s["ticker"]): s["ticker"] for s in todo}
        for f in as_completed(futs):
            st = futs[f]
            try:
                ms = f.result()
            except Exception as e:  # noqa: BLE001 - log and keep scanning
                print(f"  fail {st}: {e}", flush=True)
                continue
            if not ms:
                ms = [{"_series": st, "_empty": True}]
            for m in ms:
                m["_series_title"] = meta[st].get("title")
                m["_category"] = meta[st].get("_category")
                fh.write(json.dumps(m) + "\n")
            n += 1
            if n % 100 == 0:
                print(f"  {n}/{len(todo)} series, 429s so far {_n429[0]}, {time.strftime('%H:%M:%S')}", flush=True)
                fh.flush()


def load_markets() -> list[dict]:
    rows = []
    with open(os.path.join(CACHE, "markets.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            m = json.loads(line)
            if not m.get("_empty"):
                rows.append(m)
    return rows


def universe(markets: list[dict] | None = None) -> list[dict]:
    markets = markets if markets is not None else load_markets()
    out = []
    for m in markets:
        if m.get("market_type") != "binary" or m.get("result") not in ("yes", "no"):
            continue
        vol = float(m.get("volume_fp") or m.get("volume") or 0)
        o, c = ts(m.get("open_time")), ts(m.get("close_time"))
        if not o or not c or (c - o) / 86400 < MIN_LIFE_DAYS or vol < MIN_FINAL_VOLUME:
            continue
        out.append(m)
    return out


def _candles(m: dict) -> list[dict]:
    o, c = int(ts(m["open_time"])), int(ts(m["close_time"]))
    if m["_source"] == "historical":
        path = f"/historical/markets/{m['ticker']}/candlesticks"
    else:
        path = f"/series/{m['_series']}/markets/{m['ticker']}/candlesticks"
    out, s = [], o
    step = 4500 * 86400
    while s < c:
        e = min(c, s + step)
        d = _get(path, {"start_ts": s, "end_ts": e, "period_interval": 1440})
        out.extend(d.get("candlesticks") or [])
        s = e
    return out


def fetch_candles(workers: int = 8) -> None:
    os.makedirs(CANDLE_DIR, exist_ok=True)
    uni = universe()
    todo = [m for m in uni if not os.path.exists(_candle_path(m["ticker"]))]
    print(f"universe {len(uni)}, candles to fetch {len(todo)}", flush=True)
    n = 0
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(_candles, m): m for m in todo}
        for f in as_completed(futs):
            m = futs[f]
            try:
                cs = f.result()
            except Exception as e:  # noqa: BLE001
                print(f"  fail {m['ticker']}: {e}", flush=True)
                continue
            _dump(_candle_path(m["ticker"]), cs)
            n += 1
            if n % 500 == 0:
                print(f"  {n}/{len(todo)}", flush=True)


def _candle_path(ticker: str) -> str:
    return os.path.join(CANDLE_DIR, ticker.replace("/", "_") + ".json")


def load_candles(ticker: str) -> list[dict] | None:
    p = _candle_path(ticker)
    return _load(p) if os.path.exists(p) else None


def _dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"series": fetch_series, "markets": fetch_markets, "candles": fetch_candles}[cmd]()
