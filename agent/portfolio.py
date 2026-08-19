"""
Persistent position ledger.

Why this exists: `PortfolioState` in risk.py is the *view* the risk gate needs
(counts and totals). It had a save() that nothing ever called, so load()
returned a blank portfolio on every cycle and four caps -- duplicate position,
max_open_positions, daily-loss, total-capital -- could never bind. This module
is the actual store: what we hold, at what price, with what exit levels.

No network, no LLM. Pure file I/O over state/positions.json so the backtest and
unit tests can drive it deterministically.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from .config import STATE_DIR
from .risk import PortfolioState

POSITIONS_PATH = STATE_DIR / "positions.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Position:
    """One open contract line.

    `entry_price_cents` and every exit level are denominated in the price of
    the side we actually hold -- a NO position bought at 22c has
    entry_price_cents=22, not 78. Translation to Kalshi's YES-leg wire format
    happens once, in nodes.translate_side().
    """

    ticker: str
    side: str                      # "yes" | "no"
    size_contracts: int
    entry_price_cents: float
    cost_usd: float
    opened_at: str = field(default_factory=_utcnow)
    take_profit_cents: float | None = None
    stop_loss_cents: float | None = None
    close_ts: str | None = None    # market close (ISO), drives the time exit
    hold_to_resolution: bool = False
    paper: bool = True             # False only for a real filled order
    note: str = ""

    def mark_price_cents(self, market: dict) -> float | None:
        """What we could sell this position for right now, in our side's terms.

        Exiting means hitting the other guy's bid, never our own ask:
          long YES -> sell YES at the YES bid
          long NO  -> sell NO  at the NO bid, which is (100 - YES ask)
        """
        bid = market.get("yes_bid_cents")
        ask = market.get("yes_ask_cents")
        if self.side == "yes":
            return None if bid in (None, 0) else float(bid)
        if self.side == "no":
            return None if ask in (None, 0) else 100.0 - float(ask)
        return None

    def unrealized_usd(self, market: dict) -> float | None:
        mark = self.mark_price_cents(market)
        if mark is None:
            return None
        return self.size_contracts * (mark - self.entry_price_cents) / 100.0


@dataclass
class ClosedTrade:
    ticker: str
    side: str
    size_contracts: int
    entry_price_cents: float
    exit_price_cents: float
    realized_usd: float
    opened_at: str
    closed_at: str
    reason: str
    paper: bool = True


@dataclass
class Portfolio:
    """Everything the risk gate needs, persisted between cycles."""

    date: str = field(default_factory=lambda: date.today().isoformat())
    positions: list[Position] = field(default_factory=list)
    closed_today: list[ClosedTrade] = field(default_factory=list)
    realized_pnl_today_usd: float = 0.0

    # ------------------------------------------------------------ persistence
    @classmethod
    def load(cls, path: Path | None = None) -> "Portfolio":
        path = path or POSITIONS_PATH
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            # A corrupt ledger must not silently look like "no positions" --
            # that would re-open everything we already hold. Fail loud.
            raise ValueError(f"corrupt portfolio ledger at {path}")
        p = cls(
            date=raw.get("date", date.today().isoformat()),
            positions=[Position(**d) for d in raw.get("positions", [])],
            closed_today=[ClosedTrade(**d) for d in raw.get("closed_today", [])],
            realized_pnl_today_usd=float(raw.get("realized_pnl_today_usd", 0.0)),
        )
        if p.date != date.today().isoformat():
            # New day: the daily-loss counter resets, open positions carry over.
            p.date = date.today().isoformat()
            p.realized_pnl_today_usd = 0.0
            p.closed_today = []
        return p

    def save(self, path: Path | None = None) -> None:
        path = path or POSITIONS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps({
            "date": self.date,
            "positions": [asdict(p) for p in self.positions],
            "closed_today": [asdict(c) for c in self.closed_today],
            "realized_pnl_today_usd": round(self.realized_pnl_today_usd, 4),
        }, indent=2), encoding="utf-8")
        tmp.replace(path)   # atomic: a crash mid-write can't truncate the ledger

    # ------------------------------------------------------------ mutation
    def get(self, ticker: str) -> Position | None:
        return next((p for p in self.positions if p.ticker == ticker), None)

    def open_position(self, pos: Position, *, path: Path | None = None) -> Position:
        if self.get(pos.ticker):
            raise ValueError(f"already hold {pos.ticker}")
        self.positions.append(pos)
        self.save(path)          # save() after every mutation -- the whole point
        return pos

    def close_position(self, ticker: str, exit_price_cents: float, reason: str,
                       *, path: Path | None = None) -> ClosedTrade:
        pos = self.get(ticker)
        if pos is None:
            raise ValueError(f"no open position in {ticker}")
        realized = pos.size_contracts * (exit_price_cents - pos.entry_price_cents) / 100.0
        trade = ClosedTrade(
            ticker=pos.ticker, side=pos.side, size_contracts=pos.size_contracts,
            entry_price_cents=pos.entry_price_cents,
            exit_price_cents=float(exit_price_cents),
            realized_usd=round(realized, 4), opened_at=pos.opened_at,
            closed_at=_utcnow(), reason=reason, paper=pos.paper,
        )
        self.positions = [p for p in self.positions if p.ticker != ticker]
        self.closed_today.append(trade)
        self.realized_pnl_today_usd += realized
        self.save(path)
        return trade

    # ------------------------------------------------------------ risk view
    @property
    def deployed_usd(self) -> float:
        return round(sum(p.cost_usd for p in self.positions), 4)

    def risk_state(self) -> PortfolioState:
        """Project the ledger into the shape risk.evaluate() consumes."""
        return PortfolioState(
            open_positions=len(self.positions),
            open_tickers=tuple(p.ticker for p in self.positions),
            realized_pnl_today_usd=round(self.realized_pnl_today_usd, 4),
            deployed_usd=self.deployed_usd,
        )
