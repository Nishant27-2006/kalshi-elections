# kalshi-elections

A minimal, transparent Python client for the Kalshi Trade API v2, built for
pulling political prediction-market data into the
[election-markets Obsidian vault](../obsidian-personal-space/vault/).

No black-box SDK — `kalshi_client.py` implements the RSA-PSS request signing
directly from Kalshi's official docs (fetched 2026-08-06), so you can see
exactly what's being sent. **~150 lines, read it before you trust it.**

## Status

- ✅ Auth scheme implemented and **sourced verbatim** from Kalshi's docs
  (`KALSHI-ACCESS-KEY` / `-SIGNATURE` / `-TIMESTAMP` headers, RSA-PSS-SHA256,
  MGF1, salt=DIGEST_LENGTH, base64).
- ✅ **Tested live** against production (unauthenticated): exchange status
  returns `exchange_active: true, trading_active: true`.
- ✅ **Verified real tickers** for several vault-tracked 2026 battleground
  districts, including the exact market from your screenshot:
  `HOUSEPARTY-MI07` = "Michigan 7th District House race" (William Lawrence
  vs Tom Barrett). See `watchlist.py`.
- ⚠️ Authenticated calls (balance, orders, placing trades) are **untested**
  — no API key has been added yet. That's the next step, on you.
- ⚠️ Order placement (`client.post(...)`) is wired but never called by
  anything here. Placing real trades is a separate, deliberate step.

## Setup

1. **Install dependencies** (already done in this session):
   ```
   pip install -r requirements.txt
   ```

2. **Get an API key from Kalshi**: kalshi.com → Account → API Keys.
   Kalshi generates an RSA keypair for you — download the **private key**
   as a `.pem` file. Put it somewhere outside version control, e.g.:
   ```
   mkdir keys
   # save your downloaded key as keys/kalshi_private_key.pem
   ```

3. **Configure credentials**:
   ```
   cp .env.example .env
   ```
   Edit `.env`:
   ```
   KALSHI_API_KEY_ID=<your key ID from the Kalshi dashboard>
   KALSHI_PRIVATE_KEY_PATH=./keys/kalshi_private_key.pem
   KALSHI_ENV=demo        # start here — paper trading, no real money
   ```
   `.env` and `keys/` are already gitignored. **Never paste your private
   key or key ID into a chat session** — set them directly in `.env`.

4. **Test the connection**:
   ```
   python test_connection.py
   ```
   This checks the unauthenticated exchange-status endpoint first (should
   always pass), then — if credentials are set — an authenticated balance
   call to confirm your signing works end to end.

5. **Switch to production** only when you're ready to trade with real
   money: generate a *separate* prod API key (demo and prod keys are not
   interchangeable) and set `KALSHI_ENV=prod`.

## Usage

```
# Explore political markets (category="Elections" — not "Politics";
# Kalshi's own category taxonomy is inconsistent, see fetch_political_markets.py)
python fetch_political_markets.py --search "house"

# List events in a series
python fetch_political_markets.py --series HOUSEPARTY-MI07

# Show one market + live orderbook
python fetch_political_markets.py --market <TICKER>

# See the curated map of vault battleground districts -> real tickers
python watchlist.py
```

```python
from kalshi_client import KalshiClient
from dotenv import load_dotenv
load_dotenv()

client = KalshiClient.from_env()
print(client.exchange_status())

# once .env has real credentials:
print(client.get_balance())
print(client.get_positions())
```

## What's confirmed vs. what's a lead

Kalshi's series taxonomy for House races isn't fully consistent — some
districts use `HOUSEPARTY-<ST><NN>`, others `HOUSE<ST><NN>` (no "PARTY"),
and primaries use `KX<ST><NN>D`/`KX<ST><NN>R`. `watchlist.py` records what
was **confirmed live** for each vault-tracked district (NY-17, PA-10,
CA-13, CA-45, OH-13, TX-34, several primary tickers) vs. what's still
**"not yet located"** — don't assume a ticker is real until you've run
`fetch_political_markets.py --search` and seen it come back.

One open item: `HOUSEPARTY-MI07` the series exists and matches your
screenshot's market title exactly, but `/events?series_ticker=` and
`/markets?series_ticker=` both return empty for it right now. The event
may not be linked to the series in the public API yet. If you find the
event ticker directly in the Kalshi app's market URL, fetch it with
`fetch_political_markets.py --event <ticker>`.

## Rate limits & good citizenship

Unauthenticated calls share a lower-tier rate limit; authenticated calls
get a higher one (see `docs.kalshi.com/getting_started/rate_limits`). Don't
hammer `/events` with no filters and a high `limit` — it returns *all*
Kalshi markets (crypto, sports, weather, everything), not just political
ones, and paginating the whole thing is slow and wasteful. Filter by
`series_ticker` or `category` wherever possible.

## Next steps (not done yet — deliberate choice points)

- **Locate the remaining "not yet located" tickers** in `watchlist.py`
  (PA-08, CO-08, AZ-06, NE-02, IA-01, NM-02, OH-09, WA-03, and the general-
  election series for MI-07's siblings that only have primary tickers so
  far).
- **Wire a vault-sync script**: pull live prices for watchlist tickers and
  write them into the corresponding `Race:` notes' "Trade view" sections —
  a natural next build once more tickers are located.
- **Order placement**: `client.post()` supports it, but nothing calls it.
  That's real money — build and test it deliberately, on `KALSHI_ENV=demo`
  first, when you're ready.
