"""Kalshi perpetual futures as the underlying price the ladders lack.

DELIVERED PLUMBING -- this file is not yours to write. The maths that uses
it (eqr/puts.py, eqr/surface.py) is.

WHY THIS FILE EXISTS. agent/digital.py opens by saying Kalshi publishes no
underlying price, so the forward has to be recovered from the ladder's own
risk-neutral mean -- which makes any implied vol a statement about the
ladder's internal consistency rather than about a real spot. The
2026-08-22 spec logged that as open question 2.

Perps close it. `/margin/markets` serves 21 perpetual futures WITHOUT
authentication, quoted in decimal dollars, and

    underlying spot = price / contract_size

Verified live 2026-08-31: KXBTCPERP bid 7.8746 at contract_size 0.0001
gives 78,746, consistent with the KXBTCD ladder quoting P(>=77,499) = 0.995
and P(>=87,299) = 0.005. KXETHPERP gives 2,470, and the KXETHD ladder turns
over between 2,400 and 2,500.

CAVEAT YOU MUST CARRY. A perp is not a forward to the ladder's expiry. It
is a funding-anchored perpetual, so using it as F assumes the basis over
the ladder's tenor is negligible. At Kalshi's intraday tenors that is
usually fine and it is still far better than bootstrapping F from the
ladder you are trying to test -- but it IS an assumption, and an
interviewer is entitled to ask you to bound it.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

BASE = "https://external-api.kalshi.com/trade-api/v2"

# Perp ticker -> the threshold-ladder series it prices the underlying for.
# Only pairs that actually exist on both sides are listed.
PERP_TO_SERIES: dict[str, tuple[str, ...]] = {
    "KXBTCPERP": ("KXBTCD", "KXBTC"),
    "KXETHPERP": ("KXETHD", "KXETH"),
    "KXSOLPERP": ("KXSOLD", "KXSOL"),
    "KXXRPPERP": ("KXXRPD", "KXXRP"),
}


def _f(v) -> float | None:
    """Kalshi numerics arrive as decimal strings. None stays None."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _get(path: str, **params) -> dict:
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    with urllib.request.urlopen(url, timeout=25) as r:
        return json.loads(r.read().decode())


def exchange_status() -> dict:
    """Live exchange status. `trading_active` is false outside hours."""
    return _get("/exchange/status")


def fetch_perps() -> list[dict]:
    """Every perp, with `spot` derived and None-safe numeric fields.

    A perp quoting bid 0 / ask 0 has no market -- `spot` is None for those
    rather than 0.0, because a spot of zero is not a price.
    """
    out: list[dict] = []
    for m in _get("/margin/markets", limit=1000).get("markets", []):
        try:
            csize = float(m.get("contract_size") or 0)
            bid = float(m.get("bid") or 0)
            ask = float(m.get("ask") or 0)
        except (TypeError, ValueError):
            continue
        mid = 0.5 * (bid + ask)
        spot = (mid / csize) if (csize > 0 and mid > 0) else None
        out.append({
            "ticker": m.get("ticker"),
            "title": m.get("title"),
            "bid": bid or None,
            "ask": ask or None,
            "mid": mid or None,
            "contract_size": csize,
            "spot": spot,
            "spot_bid": (bid / csize) if (csize > 0 and bid > 0) else None,
            "spot_ask": (ask / csize) if (csize > 0 and ask > 0) else None,
            "reference_price": _f(m.get("reference_price")),
            # Kalshi serves these as DECIMAL STRINGS ("200461867.00"), not
            # numbers. Passing them through untouched made the terminal
            # print "--" for every one, because a string is not finite.
            "open_interest": _f(m.get("open_interest")),
            "volume_24h": _f(m.get("volume_24h")),
            "leverage_estimate": _f(m.get("leverage_estimate")),
            "status": m.get("status"),
        })
    out.sort(key=lambda p: -(float(p.get("volume_24h") or 0)))
    return out


def series_forward(perps: list[dict]) -> dict[str, float]:
    """series ticker -> underlying spot, for every series a perp covers.

    This is the F you feed to agent/digital.py and to eqr/puts.py, instead
    of the ladder-implied mean.
    """
    by_ticker = {p["ticker"]: p for p in perps}
    out: dict[str, float] = {}
    for perp, series_list in PERP_TO_SERIES.items():
        p = by_ticker.get(perp)
        if p is None or p.get("spot") is None:
            continue
        for s in series_list:
            out[s] = float(p["spot"])
    return out
