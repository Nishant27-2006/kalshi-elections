"""
Verify the Kalshi setup end to end.

1. Unauthenticated call — exchange status (should always work).
2. Authenticated call — account balance (only if credentials are set).

Run:
    python test_connection.py
"""

import sys

from dotenv import load_dotenv

from kalshi_client import KalshiClient

load_dotenv()


def main() -> int:
    client = KalshiClient.from_env()
    print(f"Base URL   : {client.base_url}")
    print(f"Auth ready : {client.authenticated}")
    print()

    print("== Unauthenticated: exchange status ==")
    try:
        status = client.exchange_status()
        print(f"  exchange_active = {status.get('exchange_active')}")
        print(f"  trading_active  = {status.get('trading_active')}")
    except Exception as e:
        print(f"  FAILED: {e}")
        return 1

    print()
    if not client.authenticated:
        print("No KALSHI_API_KEY_ID / KALSHI_PRIVATE_KEY_PATH set — skipping "
              "authenticated check. Copy .env.example to .env and fill in "
              "your credentials to test signing.")
        return 0

    print("== Authenticated: portfolio balance ==")
    try:
        balance = client.get_balance()
        print(f"  balance response: {balance}")
        print("  Signing works. You're connected.")
    except Exception as e:
        print(f"  FAILED (check your key ID / private key path / KALSHI_ENV): {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
