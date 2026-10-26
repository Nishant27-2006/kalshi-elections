"""
Central configuration. Safe-by-default: execution is OFF, env is demo.

Every risk limit here is enforced in deterministic Python (agent/risk.py),
NEVER by the LLM. The LLM produces a directional view; this file's numbers
decide whether and how much is actually traded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VAULT_PATH = Path(
    os.environ.get(
        "VAULT_PATH",
        r"C:\Users\nisha\Desktop\obsidian-personal-space\vault",
    )
)
STATE_DIR = REPO_ROOT / "state"
AUDIT_LOG = STATE_DIR / "audit.jsonl"
SEEN_HASHES = STATE_DIR / "seen.json"
KILL_SWITCH = REPO_ROOT / "KILL"          # touch this file to halt the loop


@dataclass
class RiskLimits:
    """Hard bounds. The LLM cannot override any of these."""

    # --- capital ---
    # NOTE: deliberately small placeholder. Set TOTAL_CAPITAL_USD in .env to
    # your real ceiling before ever enabling live execution.
    total_capital_usd: float = float(os.environ.get("TOTAL_CAPITAL_USD", 100.0))
    max_position_usd: float = float(os.environ.get("MAX_POSITION_USD", 10.0))
    max_daily_loss_usd: float = float(os.environ.get("MAX_DAILY_LOSS_USD", 25.0))
    max_open_positions: int = int(os.environ.get("MAX_OPEN_POSITIONS", 5))

    # --- market quality gates ---
    min_confidence: float = 0.65      # LLM confidence floor to trade at all
    min_edge_cents: float = 5.0       # required gap between fair value and price
    max_spread_cents: float = 6.0     # refuse illiquid/wide books
    min_book_depth_contracts: float = 100.0
    min_price_cents: float = 3.0      # avoid lottery-ticket dust
    max_price_cents: float = 95.0     # avoid near-resolved contracts

    # --- execution posture ---
    execution_enabled: bool = os.environ.get("EXECUTION_ENABLED", "false").lower() == "true"
    env: str = os.environ.get("KALSHI_ENV", "demo")

    # If T2 (the cheap LLM triage) cannot run, the funnel short-circuits at
    # triage rather than letting every entity match fall through to T4 and
    # spend Kalshi API calls on headlines nothing will ever judge. Set true
    # only when you deliberately want market snapshots without triage
    # (e.g. collecting backtest data).
    allow_market_snapshot_without_triage: bool = os.environ.get(
        "ALLOW_MARKET_SNAPSHOT_WITHOUT_TRIAGE", "false").lower() == "true"

    def is_live(self) -> bool:
        return self.execution_enabled and self.env == "prod"


@dataclass
class ExitLimits:
    """When to get out. Nothing in this repo sold anything before this existed.

    All levels are in cents of the side we hold (a NO bought at 22c has
    entry=22), so the same arithmetic works for both directions.
    """

    # take profit at a multiple of entry; stop out at a fraction of it
    take_profit_multiple: float = float(os.environ.get("TAKE_PROFIT_MULTIPLE", 2.0))
    stop_loss_fraction: float = float(os.environ.get("STOP_LOSS_FRACTION", 0.5))
    # never place an exit outside the tradeable band
    max_exit_price_cents: float = 97.0
    min_exit_price_cents: float = 1.0
    # flatten this long before the market closes rather than riding resolution
    time_exit_buffer_hours: float = float(os.environ.get("TIME_EXIT_BUFFER_HOURS", 6.0))
    # Below this entry price a percentage stop rounds inside one tick (a 50%
    # stop on a 1.3c longshot is 0.65c, which cannot be quoted). Such positions
    # are marked hold_to_resolution instead of carrying a fake stop.
    min_stoppable_entry_cents: float = 3.0


@dataclass
class PollingConfig:
    interval_seconds: int = int(os.environ.get("POLL_INTERVAL_SECONDS", 300))  # 5 min
    news_lookback_hours: int = 2
    queries: list[str] = field(default_factory=lambda: [
        "politics",
        "senate race",
        "house race",
        "governor race",
        "resign OR indicted OR scandal congress",
    ])


# Create Order v2 enums. NOTE: the API wants full names -- "GTC"/"IOC"/"FOK"
# and "cancel_newest" are NOT valid values.
#   time_in_force: fill_or_kill | good_till_canceled | immediate_or_cancel
#   self_trade_prevention_type: taker_at_cross | maker
# Default to immediate_or_cancel: an unattended 24/7 loop should never leave a
# resting order behind it. Nothing here cancels or manages open orders.
ORDER_TIME_IN_FORCE = os.environ.get("ORDER_TIME_IN_FORCE", "immediate_or_cancel")
ORDER_STP = os.environ.get("ORDER_STP", "taker_at_cross")


@dataclass
class ModelConfig:
    # Cheap model for high-frequency triage (T2). Runs often, must be cheap.
    triage_model: str = "claude-haiku-4-5-20251001"
    # Expensive model for the real judgment call (T5). Runs rarely.
    judge_model: str = "claude-sonnet-5"
    max_judge_calls_per_hour: int = int(os.environ.get("MAX_JUDGE_CALLS_PER_HOUR", 20))


RISK = RiskLimits()
EXITS = ExitLimits()
POLLING = PollingConfig()
MODELS = ModelConfig()


def ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
