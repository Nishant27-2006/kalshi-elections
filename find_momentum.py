"""
Scan political markets for recent price momentum.

"Momentum" here = measurable price movement over a recent window, computed
from real candlestick data — not a prediction of what will happen, a
readout of what already is. Combines with the vault's political-knowledge
frameworks to explain WHY a mover is moving, where explainable.

Strategy (Kalshi's /markets endpoint has no volume-sort or category filter,
so we build a candidate list explicitly):
  1. Pull open markets from known high-salience series (chamber control,
     the vault's battleground-district watchlist, and a title-search sweep
     of the Elections category for "senate"/"governor"/"primary"/"control").
  2. For each open market with nonzero volume, pull 1-hour candles over the
     last N hours and 1-minute candles over the last hour.
  3. Flag movers by absolute price delta, weighted by volume (a big move on
     no volume is noise).

Usage:
    python find_momentum.py                 # scan the default candidate set
    python find_momentum.py --hours 24       # look back further for trend
    python find_momentum.py --min-volume 50  # require this much recent volume
"""

import argparse
import json
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

from kalshi_client import KalshiClient
from momentum_filter import (annotate, ask_sums_by_event, closes_within,
                             event_ticker, parse_day, rank, series_matches,
                             ticker_matches, window_for_election_day)
from watchlist import WATCHLIST

load_dotenv()


# Kalshi's own category names. "Elections" was the only one this scanner
# swept, which made --series-match useless outside politics: a KXHIGHNY or
# KXCPIYOY filter matched nothing because discovery never returned them.
# Every category the live API serves, verified 2026-08-19 with its series
# count. Six were missing and 5,538 series were therefore unreachable by the
# scanner at all -- Entertainment alone is 2,536, the largest block on the
# exchange, so `--series-match KXTOPSONG` swept nothing no matter what else
# was passed.
#
# "Elections" (1,592) and "Politics" (2,196) are BOTH live and are different
# groupings, not synonyms -- keep both.
#
# "Culture" is deliberately absent: it returns `"series": null`, which is the
# exact payload that used to crash the whole sweep before the `or []` fix.
CATEGORIES = ("Elections", "Politics", "Climate and Weather", "Economics",
              "Financials", "Crypto", "Science and Technology", "Sports",
              "Entertainment", "Companies", "World", "Health",
              "Transportation")

# Title keywords worth scanning, per category. Elections keeps its original
# list; the others are deliberately broad because there is no equivalent of a
# watchlist for them yet.
CATEGORY_KEYWORDS = {
    "Elections": ["senate", "governor", "control of", "primary", "president",
                  "generic ballot", "midterm"],
}


def discover_candidate_series(client: KalshiClient,
                              series_match: list[str] | None = None,
                              categories: list[str] | None = None) -> list[str]:
    """Series tickers worth scanning.

    Politics gets the curated watchlist plus a keyword sweep of Elections.
    Any other category is swept wholesale and narrowed by `series_match`,
    since no watchlist exists for those markets.

    When `series_match` is supplied the watchlist seed is skipped: asking for
    KXHIGHNY should not drag in every political series by default.
    """
    cats = categories or ["Elections"]
    tickers = set()

    if "Elections" in cats and not series_match:
        for info in WATCHLIST.values():
            s = info.get("series")
            if s and " / " not in s:  # skip the "A / B" dual-ticker placeholders
                tickers.add(s)

    for cat in cats:
        try:
            data = client.get_series_list(category=cat)
        except Exception as e:
            print(f"  category {cat!r} failed: {str(e)[:80]}")
            continue
        keywords = CATEGORY_KEYWORDS.get(cat)
        # `or []`, not a get() default: the default fires only when the key
        # is ABSENT. Kalshi sends `"series": null` for an empty category
        # (observed live on category="Culture"), so get("series", []) hands
        # back None and this loop raised TypeError -- killing the WHOLE
        # sweep, not just that category.
        for s in data.get("series") or []:
            ticker = s.get("ticker")
            if not ticker:
                continue
            if series_match:
                # An explicit filter is the selection criterion; a keyword
                # list would only narrow it further and hide matches.
                if series_matches(ticker, series_match):
                    tickers.add(ticker)
            elif keywords is None or any(
                    k in s.get("title", "").lower() for k in keywords):
                tickers.add(ticker)

    out = sorted(t for t in tickers if t)
    if series_match:
        out = [t for t in out if series_matches(t, series_match)]
    return out


MAX_MARKET_PAGES = 12


def _all_open_markets(client: KalshiClient, series_ticker: str,
                      page_size: int = 200) -> list[dict]:
    """Every open market in a series, following the cursor.

    The scanner used to take a single `limit=50` page and say nothing about
    the rest. For a multi-event series that silently discarded the part that
    matters: KXCPIYOY's first page held 50 legs across three months with ZERO
    24h volume, missing the liquid T3.4 leg entirely, so the series scored
    nothing and looked simply inactive. KXFLPRIMARY spans nine districts and
    had the same exposure.
    """
    out: list[dict] = []
    cursor = None
    for page in range(MAX_MARKET_PAGES):
        params = {"series_ticker": series_ticker, "status": "open",
                  "limit": page_size}
        if cursor:
            params["cursor"] = cursor
        data = client.get("/markets", params=params)
        out.extend(data.get("markets") or [])
        cursor = data.get("cursor")
        if not cursor:
            return out
    # Hit the page cap with a cursor still outstanding -- say so rather than
    # returning a truncated set that reads as complete.
    print(f"  {series_ticker}: stopped at {MAX_MARKET_PAGES} pages "
          f"({len(out)} markets); more remain")
    return out


def attach_event_flags(client: KalshiClient, records: list[dict]) -> int:
    """Fill each record's `mutually_exclusive` from its EVENT.

    The flag is not on the market payload, only on `get_event`. Without this
    the classifier only ever saw None and fell back to the shape heuristic,
    which cannot recognise an unordered field at all: KXRAIN-26AUG19 (20
    independent cities, ME=False) came out `exclusive_field` with a +176c
    "premium" that means nothing.

    One request per distinct EVENT, cached -- events are far fewer than legs
    (a 39-record KXRAIN sweep touches 2 events). A lookup failure leaves the
    record at None rather than guessing, so the shape path still applies.
    """
    cache: dict[str, object] = {}
    filled = 0
    for r in records:
        ev = r.get("event_ticker") or event_ticker(r.get("ticker", ""))
        if not ev:
            continue
        if ev not in cache:
            try:
                cache[ev] = (client.get_event(ev).get("event", {})
                             .get("mutually_exclusive"))
            except Exception as e:
                print(f"  event flag lookup failed for {ev}: {str(e)[:80]}")
                cache[ev] = None
        if cache[ev] is not None:
            r["mutually_exclusive"] = cache[ev]
            filled += 1
    return filled


def scan_series(client: KalshiClient, series_ticker: str, hours_back: int,
                 min_volume: float, close_after=None, close_before=None) -> list[dict]:
    """Return momentum records for open markets in this series.

    `close_after`/`close_before` bound the market's close_time. Filtering here
    rather than after the scan matters for cost: each market that survives
    costs a candlestick request, and the unfiltered sweep spent ~45 minutes
    across 575 series pulling candles for contracts resolving years out.
    """
    results = []
    try:
        markets = _all_open_markets(client, series_ticker)
    except Exception as e:
        return [{"series": series_ticker, "error": str(e)}]
    now = int(time.time())
    start_ts = now - hours_back * 3600

    skipped_window = 0
    for m in markets:
        ticker = m.get("ticker")
        if not ticker:
            continue
        if not closes_within(m, close_after, close_before):
            skipped_window += 1
            continue
        try:
            candles_data = client.get_market_candlesticks(
                series_ticker=series_ticker, ticker=ticker,
                start_ts=start_ts, end_ts=now, period_interval=60,
            )
        except Exception as e:
            results.append({"series": series_ticker, "ticker": ticker, "error": str(e)})
            continue

        candles = candles_data.get("candlesticks", [])
        priced = [c for c in candles if c.get("price", {}).get("close_dollars") is not None]
        if len(priced) < 2:
            continue

        first_price = float(priced[0]["price"]["close_dollars"])
        last_price = float(priced[-1]["price"]["close_dollars"])
        delta = last_price - first_price
        total_volume = sum(float(c.get("volume_fp") or 0) for c in candles)

        if total_volume < min_volume:
            continue

        # last-hour-specific delta (most recent candle vs the one before it)
        recent_delta = None
        if len(priced) >= 2:
            recent_delta = float(priced[-1]["price"]["close_dollars"]) - float(priced[-2]["price"]["close_dollars"])

        results.append({
            "series": series_ticker,
            "ticker": ticker,
            "title": m.get("title") or m.get("yes_sub_title") or "",
            "first_price": first_price,
            "last_price": last_price,
            "delta": delta,
            "recent_hour_delta": recent_delta,
            "volume": total_volume,
            # fixed-point: dollar-strings, not bare cents. Store as cents.
            "yes_bid": (lambda v: float(v) * 100 if v is not None else None)(
                m.get("yes_bid_dollars")),
            "yes_ask": (lambda v: float(v) * 100 if v is not None else None)(
                m.get("yes_ask_dollars")),
            "close_time": m.get("close_time"),
            # NOTE: the /markets payload does NOT carry mutually_exclusive --
            # it is EVENT-level. Left None here and filled by
            # attach_event_flags() after the sweep; see that function.
            "mutually_exclusive": None,
            # authoritative event grouping; the ticker heuristic cannot handle
            # series tickers that themselves contain a hyphen (KXMLBWINS-BOS)
            "event_ticker": m.get("event_ticker"),
        })

    if skipped_window:
        # Never let a filter drop markets silently -- a quiet cap reads as
        # "we looked at everything" when we did not.
        print(f"  {series_ticker}: {skipped_window} market(s) outside the close-time window")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=12, help="Lookback window in hours")
    parser.add_argument("--min-volume", type=float, default=10.0,
                        help="Minimum contracts traded in window")
    parser.add_argument("--election-day", metavar="YYYY-MM-DD",
                        help="Only markets closing within +/-1 day of this date")
    parser.add_argument("--close-after", metavar="YYYY-MM-DD",
                        help="Only markets closing on/after this date")
    parser.add_argument("--close-before", metavar="YYYY-MM-DD",
                        help="Only markets closing strictly before this date")
    parser.add_argument("--series-match", action="append", metavar="PATTERN",
                        help="Restrict to series tickers matching this substring "
                             "or regex; repeatable (e.g. --series-match FL)")
    parser.add_argument("--ticker-match", action="append", metavar="PATTERN",
                        help="Restrict to market tickers matching this substring "
                             "or regex; repeatable. Use this for an election day: "
                             "close_time is NOT a reliable proxy (KXFLRGOVEXACT-"
                             "26AUG18-* closes 2027-08-18, and the KXGOVFLNOMR "
                             "nomination markets close on the general, 2026-11-03)")
    parser.add_argument("--category", action="append", metavar="NAME",
                        choices=CATEGORIES,
                        help="Kalshi category to sweep; repeatable. Defaults to "
                             "Elections. Required to reach non-political "
                             "markets at all -- discovery previously swept "
                             "Elections only.")
    parser.add_argument("--thin-book", type=float, default=20000.0,
                        help="Contracts below which a move is discounted as "
                             "thin-book repricing")
    parser.add_argument("--rank-by", choices=("conviction", "delta"),
                        default="conviction",
                        help="conviction = |delta| discounted for book depth "
                             "(default); delta = the old absolute ranking")
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--out", metavar="FILE", help="Write full results as JSON")
    args = parser.parse_args()

    if args.election_day:
        close_after, close_before = window_for_election_day(args.election_day)
    else:
        close_after = parse_day(args.close_after)
        close_before = parse_day(args.close_before)

    client = KalshiClient.from_env()
    started = time.time()

    print("Discovering candidate series...")
    series_list = discover_candidate_series(client, args.series_match,
                                            args.category)
    print(f"{len(series_list)} candidate series to scan.")
    print(f"  categories: {args.category or ['Elections']}")
    if args.series_match:
        print(f"  series filter: {args.series_match}")
    if close_after or close_before:
        print(f"  close-time window: {close_after} -> {close_before}")
    print()

    all_results, errors = [], 0
    for st in series_list:
        recs = scan_series(client, st, args.hours, args.min_volume,
                           close_after=close_after, close_before=close_before)
        for r in recs:
            if "error" in r:
                errors += 1
                # Show it. A bare error COUNT is indistinguishable from a
                # dead series, and transient API failures under load look
                # exactly like "this vertical has no markets".
                print(f"  ERROR {r.get('series')}"
                      f"{'/' + r['ticker'] if r.get('ticker') else ''}: "
                      f"{str(r['error'])[:120]}")
            else:
                all_results.append(r)

    # The exchange's structure flag lives on the event, not the market, so it
    # must be fetched before anything classifies these records.
    if all_results:
        filled = attach_event_flags(client, all_results)
        print(f"  event flags attached: {filled}/{len(all_results)} records")

    if args.ticker_match:
        before = len(all_results)
        all_results = [r for r in all_results
                       if ticker_matches(r["ticker"], args.ticker_match)]
        print(f"  ticker filter {args.ticker_match}: "
              f"{before - len(all_results)} of {before} markets dropped")

    annotate(all_results, thin_book_contracts=args.thin_book)
    ranked = rank(all_results, by=args.rank_by)
    elapsed = time.time() - started

    print(f"=== Top movers, last {args.hours}h "
          f"(min volume {args.min_volume}, ranked by {args.rank_by}) ===")
    print(f"scanned {len(series_list)} series in {elapsed:.1f}s | "
          f"{len(all_results)} markets scored | {errors} errors")
    print()

    if not ranked:
        print("No markets cleared the filters in this window.")
        print("Try --min-volume 0, a longer --hours, or widen the close-time window.")
    else:
        for r in ranked[:args.top]:
            direction = "UP" if r["delta"] > 0 else "DOWN" if r["delta"] < 0 else "flat"
            flag = " THIN" if r["thin_book"] else ""
            print(f"{r['ticker']:24s} {direction:5s} {r['delta']:+.3f}  "
                  f"conv={r['conviction']:.4f}  "
                  f"({r['first_price']:.2f}->{r['last_price']:.2f})  "
                  f"vol={r['volume']:.0f}{flag}  {r['title'][:44]}")

        # Field coherence: an ask-sum well above 100 that is decaying means the
        # longshots are being marked down. Moves produced by that decay are
        # repricing, not news -- the Askar case.
        print()
        print("=== Field ask-sums PER EVENT (>100 = longshot premium) ===")
        sums = ask_sums_by_event(all_results)
        for ev, info in sorted(sums.items()):
            # 1-leg standalone binaries are shown too: filtering them out
            # hid an entire structure category from the report.
            if info["legs"] > 1 or info["structure"] == "standalone_binary":
                if info["premium_cents"] is not None:
                    prem = f"premium={info['premium_cents']:+6.2f}c"
                elif info["structure"] == "standalone_binary":
                    prem = "premium=n/a (standalone binary)"
                elif info["structure"] == "indeterminate":
                    prem = "premium=n/a (2 legs, structure undecidable)"
                elif info["structure"] == "disputed":
                    prem = f"premium={info['premium_cents']:+6.2f}c DISPUTED"
                elif info["structure"] == "independent_basket":
                    prem = "premium=n/a (independent basket)"
                else:
                    prem = "premium=n/a (cumulative ladder)"
                print(f"  {ev:26s} ask_sum={info['ask_sum_cents']:7.2f}c  "
                      f"{prem}  legs={info['legs']}")
                if info.get("note"):
                    print(f"    ^ {info['note'][:150]}")

    if args.out:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "params": vars(args),
            "series_scanned": len(series_list),
            "elapsed_seconds": round(elapsed, 1),
            "errors": errors,
            "results": ranked,
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        print()
        print(f"wrote {len(ranked)} records -> {args.out}")



if __name__ == "__main__":
    main()
