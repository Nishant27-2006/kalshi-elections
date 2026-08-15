"""Typed state passed between graph nodes."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class NewsItem(TypedDict, total=False):
    title: str
    source: str
    pub_date: str
    hash: str


class MarketSnapshot(TypedDict, total=False):
    ticker: str
    series_ticker: str
    title: str
    yes_bid_cents: float
    yes_ask_cents: float
    spread_cents: float
    book_depth_contracts: float
    last_price_cents: float
    volume_recent: float


class Judgment(TypedDict, total=False):
    """What the LLM is allowed to produce. Note there is NO position size
    here — sizing is decided by deterministic code in risk.py."""
    should_trade: bool
    side: Literal["yes", "no", "none"]
    fair_value_cents: float
    confidence: float          # 0.0 - 1.0
    reasoning: str
    key_risk: str


class RiskDecision(TypedDict, total=False):
    approved: bool
    reason: str
    size_contracts: int
    size_usd: float
    limit_price_cents: float


class AgentState(TypedDict, total=False):
    # input
    news: NewsItem

    # T2 triage
    is_relevant: bool
    triage_reason: str
    entities: list[str]

    # T3 knowledge graph
    kg_titles: list[str]
    kg_context: str

    # T4 market match
    candidates: list[MarketSnapshot]
    market: MarketSnapshot | None

    # T5 judgment
    judgment: Judgment | None

    # T6 risk
    risk: RiskDecision | None

    # T7 execution
    executed: bool
    execution_result: dict[str, Any] | None

    # bookkeeping
    terminated_at: str
    notes: list[str]
