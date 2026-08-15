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

    def is_live(self) -> bool:
        return self.execution_enabled and self.env == "prod"


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


@dataclass
class ModelConfig:
    # Cheap model for high-frequency triage (T2). Runs often, must be cheap.
    triage_model: str = "claude-haiku-4-5-20251001"
    # Expensive model for the real judgment call (T5). Runs rarely.
    judge_model: str = "claude-sonnet-5"
    max_judge_calls_per_hour: int = int(os.environ.get("MAX_JUDGE_CALLS_PER_HOUR", 20))


RISK = RiskLimits()
POLLING = PollingConfig()
MODELS = ModelConfig()


def ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
