"""FastAPI over the recorder file and the live Kalshi REST API.

No API key required: every endpoint used here is public. The WebSocket
polls the recorder and broadcasts, so the client-side interface is
identical whether or not an authenticated Kalshi socket exists later.

DEGRADE HONESTLY. Several endpoints call modules the author has not
written yet. Each catches NotImplementedError and returns a `pending`
field naming the file. The terminal must show "you have not written this
yet", never a crash and never a fabricated number.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import pkgutil
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from agent import ladder as ladder_mod
from eqr import density as density_mod
from eqr import evaluate, loader
from eqr import panel as panel_mod
from eqr import perps as perps_mod
from eqr import puts as puts_mod
from eqr import universe as universe_mod

REPO = Path(__file__).resolve().parents[1]
PANEL = REPO / "state" / "eqr_panel.jsonl"

app = FastAPI(title="Kalshi EQR Terminal")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

_COMBO = "KXMVECROSSCATEGORY"

# Perps and exchange status are live network reads, so they are cached with
# a short TTL. The WebSocket pushes every few seconds and every connected
# client would otherwise hit Kalshi independently.
_CACHE: dict[str, tuple[float, object]] = {}


def _cached(key: str, ttl: float, fn):
    import time as _t
    hit = _CACHE.get(key)
    now = _t.monotonic()
    if hit is not None and now - hit[0] < ttl:
        return hit[1]
    try:
        val = fn()
    except Exception:
        # A failed refresh serves stale data rather than an empty panel.
        # Staleness is visible in the header; a blank screen is not.
        if hit is not None:
            return hit[1]
        raise
    _CACHE[key] = (now, val)
    return val


def _perps() -> list[dict]:
    return _cached("perps", 2.0, perps_mod.fetch_perps)


def _status() -> dict:
    return _cached("status", 15.0, perps_mod.exchange_status)


# The panel file is APPEND-ONLY and grows without bound: the recorder writes
# ~1,340 rows per sweep every 300s, so ten days is roughly 3.8 million rows.
# Re-parsing it per request made five concurrent fetches queue behind each
# other on a single uvicorn worker and the slow ones lost, which showed up
# in the terminal as an empty header. So it is read INCREMENTALLY: keep a
# byte offset, parse only what was appended, and maintain the
# latest-per-ticker view as we go.
NEWLINE = bytes([10])
_TAIL: dict = {"offset": 0, "rows": [], "latest": {}}


def _ingest(chunk: str) -> None:
    for line in chunk.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue                      # torn line; the recorder is writing
        _TAIL["rows"].append(r)
        t = r.get("ticker")
        if t is not None:
            prev = _TAIL["latest"].get(t)
            if prev is None or r.get("ts", 0) >= prev.get("ts", 0):
                _TAIL["latest"][t] = r


def _sync() -> None:
    """Pull in whatever the recorder appended since the last call."""
    if not PANEL.exists():
        return
    size = PANEL.stat().st_size
    if size < _TAIL["offset"]:            # truncated or rotated: start over
        _TAIL.update(offset=0, rows=[], latest={})
    if size <= _TAIL["offset"]:
        return
    # Binary mode so the offset is real bytes; text mode newline translation
    # on Windows makes seek offsets lie.
    with open(PANEL, "rb") as fh:
        fh.seek(_TAIL["offset"])
        raw = fh.read(size - _TAIL["offset"])
    cut = raw.rfind(NEWLINE)
    if cut < 0:
        return                            # no complete line yet
    _ingest(raw[:cut].decode("utf-8", errors="replace"))
    _TAIL["offset"] += cut + 1


def _rows() -> list[dict]:
    _sync()
    return _TAIL["rows"]


def _live() -> list[dict]:
    _sync()
    out = [r for r in _TAIL["latest"].values()
           if not str(r.get("ticker", "")).startswith(_COMBO)]
    out.sort(key=lambda r: -(r.get("v24") or 0))
    return out


@app.get("/api/health")
def health() -> dict:
    rows = _rows()
    n = len(rows)
    stamps = sorted({r["ts"] for r in rows}) if rows else []
    return {"ok": True, "panel_rows": n, "sweeps": len(stamps),
            "first_ts": stamps[0] if stamps else None,
            "last_ts": stamps[-1] if stamps else None,
            "panel_path": str(PANEL)}


@app.get("/api/universe")
def universe(limit: int = 400) -> dict:
    live = _live()
    return {"count": len(live), "markets": live[:limit]}


@app.get("/api/events")
def events() -> dict:
    """Ladder candidates: events with at least 3 rungs, richest first."""
    by: dict[str, list[dict]] = {}
    for r in _live():
        by.setdefault(str(r.get("event_ticker")), []).append(r)
    out = [{"event_ticker": k, "rungs": len(v),
            "v24": sum(x.get("v24") or 0 for x in v),
            "series": (v[0].get("series") if v else None)}
           for k, v in by.items() if len(v) >= 3]
    out.sort(key=lambda e: (-e["rungs"], -e["v24"]))
    return {"count": len(out), "events": out}


def _ladder_pairs(event_ticker: str) -> tuple[list[tuple[float, float]], dict]:
    """Sorted (strike, mid) pairs plus the diagnostics that keep you honest.

    A survival function cannot rise, yet mid prices on a real ladder do.
    Measured live on KXETHD-26AUG3101 (300 rungs, every strike parsing
    cleanly and ascending): 11 upward steps.

    The cause is WIDE ONE-SIDED BOOKS, not missing data. A rung quoting
    bid 0 / ask 81 has an 81-cent spread; its mid of 0.405 is the midpoint
    of a hole, not a probability. 49 of those 300 rungs quote 10c or wider.
    Restrict to rungs with a spread of 2c or less and the 11 violations
    collapse to 1.

    This function does NOT filter them. Choosing the spread at which a
    quote stops being a price is a research decision and it belongs to the
    author, so the counts are reported and the pairs pass through intact.
    """
    pairs: list[tuple[float, float]] = []
    tight: list[tuple[float, float]] = []
    wide = 0
    for r in _live():
        if r.get("event_ticker") != event_ticker:
            continue
        k = ladder_mod.parse_strike(str(r.get("ticker", "")))
        bid, ask = r.get("yes_bid_c"), r.get("yes_ask_c")
        if k is None or bid is None or ask is None:
            continue
        spread = float(r.get("spread_c") or (float(ask) - float(bid)))
        mid = 0.5 * (float(bid) + float(ask)) / 100.0
        # WIDE and TIGHT are deliberately not complements. The band between
        # 2c and 10c is neither clearly a price nor clearly a hole, and
        # collapsing it into one of the two would hide the judgement call
        # this diagnostic exists to force.
        if spread >= 10.0:
            wide += 1
        if spread <= 2.0:
            tight.append((k, mid))
        pairs.append((k, mid))
    pairs.sort()
    tight.sort()

    def _up(xs: list[tuple[float, float]]) -> int:
        return sum(1 for i in range(len(xs) - 1)
                   if xs[i + 1][1] > xs[i][1] + 1e-9)

    return pairs, {"rungs": len(pairs), "wide_books": wide,
                   "upward_steps": _up(pairs),
                   "upward_steps_tight": _up(tight)}


@app.get("/api/ladder/{event_ticker}")
def ladder(event_ticker: str) -> dict:
    rungs = [r for r in _live() if r.get("event_ticker") == event_ticker]
    rungs.sort(key=lambda r: (ladder_mod.parse_strike(str(r.get("ticker", "")))
                              or 0.0))
    return {"event_ticker": event_ticker, "rungs": rungs}


@app.get("/api/density/{event_ticker}")
def density_endpoint(event_ticker: str) -> dict:
    pairs, diag = _ladder_pairs(event_ticker)
    base: dict = {"event_ticker": event_ticker,
                  "strikes": [k for k, _ in pairs],
                  "p_ge": [p for _, p in pairs],
                  "pdf": [], "moments": {}, "negative_buckets": [],
                  "diagnostics": diag}
    if len(pairs) < 3:
        base["pending"] = "not enough rungs recorded yet"
        return base
    try:
        pdf = density_mod.pdf_from_cdf(base["strikes"], base["p_ge"])
        base["pdf"] = pdf
        base["moments"] = density_mod.moments(pdf)
        base["negative_buckets"] = density_mod.negative_mass(pdf)
    except NotImplementedError as exc:
        base["pending"] = f"eqr/density.py -- {exc}"
    return base


def _discover_alphas() -> dict:
    import eqr.signals as pkg
    found = {}
    for m in pkgutil.iter_modules(pkg.__path__):
        if not m.name.startswith("alpha_"):
            continue
        mod = importlib.import_module(f"eqr.signals.{m.name}")
        cls = getattr(mod, "Alpha", None)
        if cls is not None:
            found[m.name] = cls()
    return found


@app.get("/api/alphas")
def alphas() -> dict:
    return {"alphas": [{"module": k, "name": getattr(v, "name", k)}
                       for k, v in sorted(_discover_alphas().items())]}


@app.get("/api/backtest/{alpha_module}")
def backtest(alpha_module: str, horizon_s: int = 3600,
             min_v24: float = 1000.0, max_spread_c: float = 10.0) -> dict:
    sig = _discover_alphas().get(alpha_module)
    if sig is None:
        return {"error": f"unknown alpha {alpha_module}"}
    rows = _rows()
    try:
        stamps = sorted({r["ts"] for r in rows})
        ics: list[dict] = []
        for asof in stamps[:-1]:
            screened = universe_mod.liquidity_screen(
                universe_mod.exclude_combos(rows), asof, min_v24, max_spread_c)
            xs, rets = panel_mod.cross_section(screened, asof, horizon_s)
            if len(xs) < 5:
                continue
            ic = evaluate.information_coefficient(sig.compute(xs), rets)
            if ic is not None:
                ics.append({"ts": asof, "ic": ic})
    except NotImplementedError as exc:
        return {"alpha": alpha_module, "pending": str(exc), "ics": [],
                "n_rebalances": 0, "mean_ic": None, "t_stat": None}
    mean_ic = sum(x["ic"] for x in ics) / len(ics) if ics else None
    return {"alpha": alpha_module, "n_rebalances": len(ics),
            "mean_ic": mean_ic,
            "t_stat": evaluate.ic_t_stat([x["ic"] for x in ics]), "ics": ics}


@app.get("/api/progress")
def progress() -> dict:
    """Which author-owned modules are still stubs. Drives the DRILL panel."""
    checks = [
        ("Day 1", "eqr.gbm", "mc_digital_call", (100.0, 100.0, 0.4, 1.0, 10, 1)),
        ("Day 2", "eqr.surface", "build_surface", (100.0, 0.25, [(100.0, 0.5)])),
        ("Day 3", "eqr.greeks", "vega_sign", (100.0, 110.0, 0.4, 0.25)),
        ("Day 4", "eqr.density", "pdf_from_cdf", ([1.0, 2.0], [0.6, 0.4])),
        ("Day 5", "eqr.universe", "exclude_combos", ([],)),
        ("Day 6", "eqr.evaluate", "information_coefficient",
         ([1.0, 2.0, 3.0], [0.1, 0.2, 0.3])),
        ("Day 7", "eqr.costs", "round_trip_cost", (0.5, 2.0)),
        ("Day 8", "eqr.neutralize", "zscore", ([1.0, 2.0, 3.0],)),
    ]
    out = []
    for day, mod_name, fn_name, args in checks:
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, fn_name)
        try:
            fn(*args)
            done = True
        except NotImplementedError:
            done = False
        except Exception:
            done = True      # it ran and raised something else: it is written
        out.append({"day": day, "module": mod_name, "fn": fn_name,
                    "done": done})
    return {"modules": out,
            "complete": sum(1 for m in out if m["done"]), "total": len(out)}


@app.websocket("/ws/quotes")
async def ws_quotes(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            await ws.send_text(json.dumps({"markets": _live()[:200]}))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return


@app.get("/api/exchange")
def exchange() -> dict:
    """Live exchange status. trading_active is false outside hours."""
    try:
        st = _status()
    except Exception as exc:                                  # noqa: BLE001
        return {"reachable": False, "error": f"{type(exc).__name__}"}
    idx = st.get("exchange_index_statuses") or []
    return {"reachable": True,
            "exchange_active": st.get("exchange_active"),
            "trading_active": st.get("trading_active"),
            "transfers_active": st.get("intra_exchange_transfers_active"),
            "estimated_resume": st.get("exchange_estimated_resume_time"),
            "indices": [{"name": i.get("description"),
                         "trading_active": i.get("trading_active")}
                        for i in idx]}


@app.get("/api/perps")
def perps_endpoint() -> dict:
    """Perpetual futures with the underlying spot derived.

    spot = price / contract_size. This is the forward the threshold ladders
    do not publish.
    """
    try:
        ps = _perps()
    except Exception as exc:                                  # noqa: BLE001
        return {"reachable": False, "error": f"{type(exc).__name__}", "perps": []}
    return {"reachable": True, "perps": ps,
            "forwards": perps_mod.series_forward(ps)}


@app.get("/api/puts/{event_ticker}")
def puts_endpoint(event_ticker: str, max_spread_c: float = 10.0) -> dict:
    """Synthetic puts across the ladder, priced against the PERP forward.

    Every author-owned step is guarded: density first, then puts. The
    response names the file it is waiting on rather than inventing a price.
    """
    pairs, diag = _ladder_pairs(event_ticker)
    series = event_ticker.split("-")[0]
    forward = None
    try:
        forward = perps_mod.series_forward(_perps()).get(series)
    except Exception:                                         # noqa: BLE001
        pass

    base: dict = {"event_ticker": event_ticker, "series": series,
                  "forward": forward, "diagnostics": diag, "strikes": [],
                  "rows": [], "ladder_mean": None}
    if len(pairs) < 3:
        base["pending"] = "not enough rungs recorded yet"
        return base

    strikes = [k for k, _ in pairs]
    p_ge = [p for _, p in pairs]
    try:
        pdf = density_mod.pdf_from_cdf(strikes, p_ge)
        mom = density_mod.moments(pdf)
    except NotImplementedError as exc:
        base["pending"] = f"eqr/density.py -- {exc}"
        return base
    base["ladder_mean"] = mom.get("mean")
    base["mass"] = mom.get("mass")

    rows = []
    try:
        # Sample about 30 strikes so the panel stays readable on a
        # 300-rung ladder.
        step = max(1, len(strikes) // 30)
        for i in range(0, len(strikes), step):
            k = strikes[i]
            row = {
                "strike": k,
                "p_ge": p_ge[i],
                "digital_put": puts_mod.digital_put(p_ge[i]),
                "vanilla_put": puts_mod.vanilla_put(pdf, k),
                "vanilla_call": puts_mod.vanilla_call(pdf, k),
                "put_strip": puts_mod.put_from_digitals(strikes, p_ge, k),
                "parity_vs_perp": (puts_mod.parity_error(pdf, k, forward)
                                   if forward is not None else None),
            }
            vp, ps_ = row["vanilla_put"], row["put_strip"]
            row["construction_gap"] = (
                None if vp is None or ps_ is None else ps_ - vp)
            rows.append(row)
    except NotImplementedError as exc:
        base["pending"] = f"eqr/puts.py -- {exc}"
        return base
    except ValueError as exc:
        base["pending"] = f"eqr/puts.py raised ValueError: {exc}"
        return base

    base["rows"] = rows
    return base


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket) -> None:
    """Real-time push: perps every 2s, exchange status and panel alongside.

    Kalshi's own WebSocket requires an authenticated key, which this repo
    does not yet have. This polls the public REST endpoints and presents
    the identical message shape, so installing a key later swaps the
    source without touching the client.
    """
    await ws.accept()
    try:
        while True:
            try:
                ps = _perps()
                fwd = perps_mod.series_forward(ps)
                st = _status()
                payload = {
                    "perps": ps,
                    "forwards": fwd,
                    "trading_active": st.get("trading_active"),
                    "exchange_active": st.get("exchange_active"),
                    "markets": _live()[:200],
                    "source": "rest-poll",
                }
            except Exception as exc:                          # noqa: BLE001
                payload = {"error": f"{type(exc).__name__}", "perps": [],
                           "markets": [], "source": "rest-poll"}
            await ws.send_text(json.dumps(payload))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
