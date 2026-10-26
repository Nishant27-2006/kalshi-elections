"""
Kalshi API client — RSA-PSS request signing per official docs.

Auth scheme (sourced from https://docs.kalshi.com/getting_started/api_keys
and https://docs.kalshi.com/getting_started/quick_start_authenticated_requests,
fetched 2026-08-06):

  Headers:
    KALSHI-ACCESS-KEY        — your API key ID
    KALSHI-ACCESS-TIMESTAMP  — milliseconds since epoch, as a string
    KALSHI-ACCESS-SIGNATURE  — base64(RSA-PSS-SHA256(f"{timestamp}{method}{path}"))

  Signing details:
    - message = f"{timestamp}{method}{path}".encode("utf-8")
      (no separators; path excludes the query string but includes /trade-api/v2)
    - padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH)
    - hashes.SHA256()
    - signature is base64-encoded

Base URLs (from https://docs.kalshi.com/getting_started/api_environments):
    Production : https://api.elections.kalshi.com/trade-api/v2
                 (despite the "elections" subdomain, this serves ALL Kalshi
                 markets — not just political ones)
    Demo       : https://demo-api.kalshi.co/trade-api/v2

Credentials are NOT interchangeable between environments.
"""

from __future__ import annotations

import base64
import datetime
import os
import random
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# Recommended dedicated Trade API hosts (docs.kalshi.com/getting_started/
# api_environments, checked 2026-08-17). The older shared hosts --
# api.elections.kalshi.com / demo-api.kalshi.co -- remain supported for
# compatibility and are kept below as fallbacks, not as defaults.
PROD_BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
DEMO_BASE_URL = "https://external-api.demo.kalshi.co/trade-api/v2"

LEGACY_PROD_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
LEGACY_DEMO_BASE_URL = "https://demo-api.kalshi.co/trade-api/v2"


def load_private_key(key_path: str):
    """Load an RSA private key from a PEM file (no passphrase)."""
    with open(key_path, "rb") as f:
        return serialization.load_pem_private_key(
            f.read(), password=None, backend=default_backend()
        )


def _sign(private_key, timestamp_ms: str, method: str, path: str) -> str:
    message = f"{timestamp_ms}{method}{path}".encode("utf-8")
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


@dataclass
class KalshiClient:
    """Thin, transparent REST client for the Kalshi Trade API v2.

    Read-only market-data calls (exchange status, events, markets, orderbooks,
    series, candlesticks) do NOT require authentication. Portfolio/order
    endpoints do. This client signs every request when credentials are
    present; if they're absent, unauthenticated GETs to public endpoints
    still work.

    Usage:
        client = KalshiClient.from_env()               # demo or prod via env
        status = client.get("/exchange/status")
        events = client.get("/events", params={"series_ticker": "KXNJGOV"})
    """

    base_url: str = PROD_BASE_URL
    api_key_id: str | None = None
    private_key_path: str | None = None
    _private_key: object = None

    def __post_init__(self):
        if self.private_key_path and self._private_key is None:
            self._private_key = load_private_key(self.private_key_path)

    @classmethod
    def from_env(cls, demo: bool | None = None) -> "KalshiClient":
        """Build a client from environment variables.

        Env vars:
            KALSHI_API_KEY_ID
            KALSHI_PRIVATE_KEY_PATH
            KALSHI_ENV = "demo" | "prod"   (default: prod)
        """
        env = (os.environ.get("KALSHI_ENV") or "prod").lower()
        if demo is None:
            demo = env == "demo"
        base_url = DEMO_BASE_URL if demo else PROD_BASE_URL
        return cls(
            base_url=base_url,
            api_key_id=os.environ.get("KALSHI_API_KEY_ID"),
            private_key_path=os.environ.get("KALSHI_PRIVATE_KEY_PATH"),
        )

    @property
    def authenticated(self) -> bool:
        return bool(self.api_key_id and self._private_key)

    def _auth_headers(self, method: str, full_path: str) -> dict:
        if not self.authenticated:
            return {}
        timestamp_ms = str(int(datetime.datetime.now().timestamp() * 1000))
        sign_path = urlparse(self.base_url + full_path).path
        signature = _sign(self._private_key, timestamp_ms, method, sign_path)
        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
        }

    # Batch sweeps get rate-limited: one 62-series pass returned HTTP 429 on 13
    # of them, and a 351-series pass on 146 (41.6%). Without a retry the caller
    # sees an empty result and cannot tell throttling from a dead series.
    MAX_RETRIES = 5
    BACKOFF_BASE_SECONDS = 0.75
    # Jitter matters more than the base here. Without it every worker that got
    # throttled in the same instant backs off for the SAME interval and they
    # all return together, reproducing the burst that caused the 429 -- a
    # parallel 6-worker sweep still lost 7 requests after all retries, and
    # re-running those same 7 serially succeeded immediately. Full jitter
    # spreads the retries across the window instead.
    BACKOFF_JITTER = 0.5          # fraction of the delay that is randomised
    RETRY_STATUS = frozenset({429, 500, 502, 503, 504})

    def _backoff_seconds(self, attempt: int) -> float:
        """Exponential backoff with jitter, for retry number `attempt`."""
        delay = self.BACKOFF_BASE_SECONDS * (2 ** attempt)
        return delay * (1.0 - self.BACKOFF_JITTER * random.random())

    def get(self, path: str, params: dict | None = None) -> dict:
        """Authenticated-if-possible GET with backoff on throttling.

        Retries only on 429 and 5xx -- a 400 or 404 is a real answer and
        retrying it just wastes time. Raises the last error if every attempt
        fails, so a caller still learns that the read did not happen.
        """
        last_exc: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            headers = self._auth_headers("GET", path)
            try:
                resp = requests.get(self.base_url + path, headers=headers,
                                    params=params, timeout=15)
            except requests.RequestException as e:
                last_exc = e                       # connection/timeout: retry
            else:
                if resp.status_code not in self.RETRY_STATUS:
                    resp.raise_for_status()
                    return resp.json()
                last_exc = requests.HTTPError(
                    f"{resp.status_code} for {path}", response=resp)
                # Honour Retry-After when the server sends one.
                wait = resp.headers.get("Retry-After")
                if wait:
                    try:
                        time.sleep(min(float(wait), 10.0))
                        continue
                    except ValueError:
                        pass
            if attempt < self.MAX_RETRIES - 1:
                time.sleep(self._backoff_seconds(attempt))
        raise last_exc if last_exc else RuntimeError(f"GET {path} failed")

    def post(self, path: str, json_body: dict | None = None) -> dict:
        """Authenticated POST. Used for order placement — NOT called by
        anything in this repo yet. Requires credentials."""
        if not self.authenticated:
            raise RuntimeError("POST requires KALSHI_API_KEY_ID + KALSHI_PRIVATE_KEY_PATH")
        headers = self._auth_headers("POST", path)
        resp = requests.post(self.base_url + path, headers=headers, json=json_body, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def delete(self, path: str) -> dict:
        if not self.authenticated:
            raise RuntimeError("DELETE requires KALSHI_API_KEY_ID + KALSHI_PRIVATE_KEY_PATH")
        headers = self._auth_headers("DELETE", path)
        resp = requests.delete(self.base_url + path, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ---- Convenience wrappers (read-only, no auth required) ----

    def exchange_status(self) -> dict:
        return self.get("/exchange/status")

    def get_series_list(self, category: str | None = None) -> dict:
        params = {"category": category} if category else None
        return self.get("/series", params=params)

    def get_series(self, series_ticker: str) -> dict:
        return self.get(f"/series/{series_ticker}")

    def get_events(self, series_ticker: str | None = None, status: str | None = None,
                    limit: int = 200, cursor: str | None = None) -> dict:
        params = {"limit": limit}
        if series_ticker:
            params["series_ticker"] = series_ticker
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor
        return self.get("/events", params=params)

    def get_event(self, event_ticker: str) -> dict:
        return self.get(f"/events/{event_ticker}")

    def get_markets(self, event_ticker: str | None = None, series_ticker: str | None = None,
                     status: str | None = None, limit: int = 200,
                     cursor: str | None = None) -> dict:
        params = {"limit": limit}
        if event_ticker:
            params["event_ticker"] = event_ticker
        if series_ticker:
            params["series_ticker"] = series_ticker
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor
        return self.get("/markets", params=params)

    def get_market(self, ticker: str) -> dict:
        return self.get(f"/markets/{ticker}")

    def get_orderbook(self, ticker: str, depth: int | None = None) -> dict:
        params = {"depth": depth} if depth else None
        return self.get(f"/markets/{ticker}/orderbook", params=params)

    def get_market_candlesticks(self, series_ticker: str, ticker: str, start_ts: int,
                                 end_ts: int, period_interval: int = 60,
                                 include_latest_before_start: bool = True) -> dict:
        """period_interval in minutes: 1, 60, or 1440 (1min/1hr/1day)."""
        params = {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "period_interval": period_interval,
            "include_latest_before_start": include_latest_before_start,
        }
        return self.get(f"/series/{series_ticker}/markets/{ticker}/candlesticks", params=params)

    def get_trades(self, ticker: str | None = None, limit: int = 200,
                    min_ts: int | None = None, max_ts: int | None = None,
                    cursor: str | None = None) -> dict:
        params = {"limit": limit}
        if ticker:
            params["ticker"] = ticker
        if min_ts:
            params["min_ts"] = min_ts
        if max_ts:
            params["max_ts"] = max_ts
        if cursor:
            params["cursor"] = cursor
        return self.get("/trades", params=params)

    # ---- Portfolio (authenticated) ----

    def get_balance(self) -> dict:
        return self.get("/portfolio/balance")

    def get_positions(self) -> dict:
        return self.get("/portfolio/positions")

    def get_orders(self, status: str | None = None) -> dict:
        params = {"status": status} if status else None
        return self.get("/portfolio/orders", params=params)
