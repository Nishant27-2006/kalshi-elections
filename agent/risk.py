"""
Deterministic risk gate. The safety core of the system.

Design rule: the LLM proposes a DIRECTION and CONFIDENCE. This module alone
decides whether a trade happens and how large it is. No LLM output can
raise a limit, bypass a check, or size a position. Every rejection is
returned with an explicit reason and gets written to the audit log.

Pure functions, no I/O, no network -> fully unit-testable, which is why the
backtest can exercise the exact same code path that live trading would.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .config import RISK, STATE_DIR, KILL_SWITCH, RiskLimits
from .state import Judgment, MarketSnapshot, RiskDecision


@dataclass
class PortfolioState:
    """Minimal view of what we currently hold / have lost today."""
    open_positions: int = 0
    open_tickers: tuple[str, ...] = ()
    realized_pnl_today_usd: float = 0.0
    deployed_usd: float = 0.0

    @classmethod
    def load(cls, path: Path | None = None) -> "PortfolioState":
        path = path or (STATE_DIR / "portfolio.json")
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text())
        except Exception:
            return cls()
        if raw.get("date") != date.today().isoformat():
            # new day -> daily loss counter resets, positions carry over
            raw["realized_pnl_today_usd"] = 0.0
        return cls(
            open_positions=raw.get("open_positions", 0),
            open_tickers=tuple(raw.get("open_tickers", ())),
            realized_pnl_today_usd=raw.get("realized_pnl_today_usd", 0.0),
            deployed_usd=raw.get("deployed_usd", 0.0),
        )

    def save(self, path: Path | None = None) -> None:
        path = path or (STATE_DIR / "portfolio.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "date": date.today().isoformat(),
            "open_positions": self.open_positions,
            "open_tickers": list(self.open_tickers),
            "realized_pnl_today_usd": self.realized_pnl_today_usd,
            "deployed_usd": self.deployed_usd,
        }, indent=2))


def _reject(reason: str) -> RiskDecision:
    return {"approved": False, "reason": reason, "size_contracts": 0,
            "size_usd": 0.0, "limit_price_cents": 0.0}


def evaluate(
    judgment: Judgment,
    market: MarketSnapshot,
    portfolio: PortfolioState,
    limits: RiskLimits | None = None,
    *,
    allow_whitelist: set[str] | None = None,
) -> RiskDecision:
    """Return an approved, sized trade or an explicit rejection.

    Checks run cheapest-and-most-fatal first.
    """
    lim = limits or RISK

    # --- 0. kill switch ---
    if KILL_SWITCH.exists():
        return _reject("kill switch file present")

    # --- 1. the LLM said no ---
    if not judgment.get("should_trade"):
        return _reject("llm declined to trade")
    side = judgment.get("side", "none")
    if side not in ("yes", "no"):
        return _reject(f"invalid side: {side!r}")

    # --- 2. confidence floor ---
    conf = float(judgment.get("confidence", 0.0))
    if conf < lim.min_confidence:
        return _reject(f"confidence {conf:.2f} < floor {lim.min_confidence:.2f}")

    # --- 3. whitelist ---
    ticker = market.get("ticker", "")
    if allow_whitelist is not None and ticker not in allow_whitelist:
        return _reject(f"ticker {ticker} not in whitelist")

    # --- 4. duplicate position ---
    if ticker in portfolio.open_tickers:
        return _reject(f"already hold a position in {ticker}")

    # --- 5. portfolio caps ---
    if portfolio.open_positions >= lim.max_open_positions:
        return _reject(f"at max open positions ({lim.max_open_positions})")
    if portfolio.realized_pnl_today_usd <= -abs(lim.max_daily_loss_usd):
        return _reject(
            f"daily loss cap hit ({portfolio.realized_pnl_today_usd:.2f} "
            f"<= -{abs(lim.max_daily_loss_usd):.2f})"
        )

    # --- 6. market quality ---
    bid = float(market.get("yes_bid_cents") or 0.0)
    ask = float(market.get("yes_ask_cents") or 0.0)
    if bid <= 0 or ask <= 0:
        return _reject("no two-sided quote")
    spread = ask - bid
    if spread > lim.max_spread_cents:
        return _reject(f"spread {spread:.1f}c > max {lim.max_spread_cents:.1f}c")
    depth = float(market.get("book_depth_contracts") or 0.0)
    if depth < lim.min_book_depth_contracts:
        return _reject(f"book depth {depth:.0f} < min {lim.min_book_depth_contracts:.0f}")

    # price we'd pay for the chosen side
    entry = ask if side == "yes" else (100.0 - bid)
    if entry < lim.min_price_cents:
        return _reject(f"entry {entry:.1f}c below min {lim.min_price_cents:.1f}c")
    if entry > lim.max_price_cents:
        return _reject(f"entry {entry:.1f}c above max {lim.max_price_cents:.1f}c")

    # --- 7. edge requirement ---
    fair = float(judgment.get("fair_value_cents", 0.0))
    if not (0.0 < fair < 100.0):
        return _reject(f"implausible fair value {fair}")
    fair_for_side = fair if side == "yes" else (100.0 - fair)
    edge = fair_for_side - entry
    if edge < lim.min_edge_cents:
        return _reject(
            f"edge {edge:.1f}c < required {lim.min_edge_cents:.1f}c "
            f"(fair {fair_for_side:.1f} vs entry {entry:.1f})"
        )

    # --- 8. sizing (deterministic, confidence-scaled, hard-capped) ---
    # scale from 0 at the confidence floor to 1.0 at full confidence
    span = max(1e-9, 1.0 - lim.min_confidence)
    conf_scale = min(1.0, max(0.0, (conf - lim.min_confidence) / span))
    # never below 25% of max once approved, never above the cap
    budget_usd = lim.max_position_usd * (0.25 + 0.75 * conf_scale)

    remaining_capital = max(0.0, lim.total_capital_usd - portfolio.deployed_usd)
    budget_usd = min(budget_usd, remaining_capital)
    if budget_usd <= 0:
        return _reject("no remaining capital")

    cost_per_contract = entry / 100.0
    size = int(budget_usd // cost_per_contract)
    if size < 1:
        return _reject(
            f"budget ${budget_usd:.2f} too small for 1 contract at {entry:.0f}c"
        )
    # never take more than a fraction of visible depth (slippage guard)
    size = min(size, int(depth * 0.25))
    if size < 1:
        return _reject("insufficient depth for minimum size")

    return {
        "approved": True,
        "reason": (f"ok: conf={conf:.2f} edge={edge:.1f}c "
                   f"entry={entry:.1f}c size={size}"),
        "size_contracts": size,
        "size_usd": round(size * cost_per_contract, 2),
        "limit_price_cents": entry,
    }
