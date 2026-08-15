"""
Graph nodes. Each is a plain function State -> State so they can be unit
tested and replayed in the backtest without LangGraph.

Cost discipline: nodes are ordered cheapest-first and each can short-circuit.
`triage` uses a small model; `judge` uses the expensive one and only runs on
candidates that already passed entity match + market lookup.
"""

from __future__ import annotations

import json
import os
import time

from .config import MODELS, RISK
from .knowledge_graph import VaultGraph
from .risk import PortfolioState, evaluate
from .state import AgentState

_GRAPH: VaultGraph | None = None


def vault() -> VaultGraph:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = VaultGraph()
    return _GRAPH


def _anthropic():
    try:
        import anthropic
    except ImportError:
        return None
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    return anthropic.Anthropic(api_key=key)


# ---------------------------------------------------------------- T1/T2

def triage_node(state: AgentState) -> AgentState:
    """Cheap relevance filter.

    Tier 1 (free): does the headline touch anything in the vault graph?
    Tier 2 (cheap LLM): only if T1 passes, confirm it's genuinely
    market-relevant rather than an incidental name mention.
    """
    title = state.get("news", {}).get("title", "")
    seeds = vault().seed_search(title)
    if not seeds:
        return {**state, "is_relevant": False,
                "triage_reason": "no vault entity matched", "entities": []}

    client = _anthropic()
    if client is None:
        # No API key: fall back to entity match alone. Explicitly recorded so
        # the audit log never implies an LLM judged this.
        return {**state, "is_relevant": True,
                "triage_reason": "entity match (no LLM key; T2 skipped)",
                "entities": seeds}

    prompt = (
        "You are triaging news headlines for a political prediction-market "
        "trading system. Answer ONLY with JSON.\n\n"
        f"Headline: {title!r}\n"
        f"Source: {state.get('news', {}).get('source', '')}\n"
        f"Possibly-related tracked topics: {seeds}\n\n"
        "Is this headline a NEW, CONCRETE development that could move a "
        "political prediction market (election outcome, resignation, "
        "candidacy, indictment, vote result)? Opinion columns, retrospectives, "
        "and generic coverage are NOT concrete developments.\n\n"
        'JSON: {"relevant": true|false, "reason": "<10 words"}'
    )
    try:
        resp = client.messages.create(
            model=MODELS.triage_model, max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        text = text[text.find("{"): text.rfind("}") + 1]
        data = json.loads(text)
        return {**state, "is_relevant": bool(data.get("relevant")),
                "triage_reason": str(data.get("reason", ""))[:120],
                "entities": seeds}
    except Exception as e:
        # Fail closed: an LLM error must not create a trade.
        return {**state, "is_relevant": False,
                "triage_reason": f"triage error: {e}"[:120], "entities": seeds}


# ---------------------------------------------------------------- T3

def retrieve_node(state: AgentState) -> AgentState:
    """Knowledge-graph retrieval from the vault (free, local)."""
    title = state.get("news", {}).get("title", "")
    titles, ctx = vault().retrieve_context(title, max_notes=6)
    return {**state, "kg_titles": titles, "kg_context": ctx}


# ---------------------------------------------------------------- T4

def market_match_node(state: AgentState, client=None) -> AgentState:
    """Find candidate Kalshi markets for the matched entities.

    Uses the curated watchlist first (known-good tickers), then falls back
    to a keyword scan of the cached open-events list.
    """
    from .market_lookup import find_candidate_markets
    entities = state.get("entities", [])
    title = state.get("news", {}).get("title", "")
    candidates = find_candidate_markets(title, entities, client=client)
    return {**state, "candidates": candidates,
            "market": candidates[0] if candidates else None}


# ---------------------------------------------------------------- T5

JUDGE_SYSTEM = """You are a disciplined prediction-market analyst.

You are given (a) a breaking news headline, (b) retrieved analytical context
from a curated political knowledge base, and (c) a live Kalshi market with
current prices.

Estimate the FAIR probability of the market's YES outcome given the news.

Hard rules:
- You do NOT decide position size. Only direction, fair value, confidence.
- Distinguish the market's exact question from the news. A scandal getting
  worse does not automatically mean "candidate drops out by <date>" —
  severity and the specific contract outcome are different variables.
- If the news is already reflected in the price, say should_trade=false.
- Prefer false over true. Most headlines are not tradeable.

Reply ONLY with JSON:
{"should_trade": bool, "side": "yes"|"no"|"none",
 "fair_value_cents": 0-100, "confidence": 0.0-1.0,
 "reasoning": "<40 words", "key_risk": "<20 words"}"""


def judge_node(state: AgentState) -> AgentState:
    """The expensive call. Only reached by genuine candidates."""
    market = state.get("market")
    if not market:
        return {**state, "judgment": None}

    client = _anthropic()
    if client is None:
        return {**state, "judgment": None,
                "notes": [*state.get("notes", []), "no ANTHROPIC_API_KEY; judge skipped"]}

    news = state.get("news", {})
    prompt = (
        f"HEADLINE: {news.get('title','')}\n"
        f"SOURCE: {news.get('source','')}  TIME: {news.get('pub_date','')}\n\n"
        f"--- KNOWLEDGE BASE CONTEXT ---\n{state.get('kg_context','(none)')}\n\n"
        f"--- LIVE MARKET ---\n"
        f"Ticker: {market.get('ticker')}\n"
        f"Question: {market.get('title')}\n"
        f"YES bid/ask: {market.get('yes_bid_cents')}c / {market.get('yes_ask_cents')}c\n"
        f"Book depth: {market.get('book_depth_contracts')} contracts\n"
        f"Recent volume: {market.get('volume_recent')}\n"
    )
    try:
        resp = client.messages.create(
            model=MODELS.judge_model, max_tokens=400, system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        text = text[text.find("{"): text.rfind("}") + 1]
        data = json.loads(text)
        judgment = {
            "should_trade": bool(data.get("should_trade")),
            "side": data.get("side", "none"),
            "fair_value_cents": float(data.get("fair_value_cents", 0)),
            "confidence": float(data.get("confidence", 0)),
            "reasoning": str(data.get("reasoning", ""))[:300],
            "key_risk": str(data.get("key_risk", ""))[:200],
        }
        return {**state, "judgment": judgment}
    except Exception as e:
        return {**state, "judgment": None,
                "notes": [*state.get("notes", []), f"judge error: {e}"[:150]]}


# ---------------------------------------------------------------- T6

def risk_node(state: AgentState) -> AgentState:
    judgment = state.get("judgment")
    market = state.get("market")
    if not judgment or not market:
        return {**state, "risk": {"approved": False, "reason": "no judgment/market",
                                   "size_contracts": 0, "size_usd": 0.0,
                                   "limit_price_cents": 0.0}}
    portfolio = PortfolioState.load()
    decision = evaluate(judgment, market, portfolio, RISK)
    return {**state, "risk": decision}


# ---------------------------------------------------------------- T7

def execute_node(state: AgentState) -> AgentState:
    """Place the order — only if execution is explicitly enabled."""
    decision = state.get("risk") or {}
    if not decision.get("approved"):
        return {**state, "executed": False}

    if not RISK.execution_enabled:
        return {**state, "executed": False,
                "execution_result": {"status": "DRY_RUN",
                                      "detail": "EXECUTION_ENABLED is false"}}

    from kalshi_client import KalshiClient
    market = state.get("market") or {}
    judgment = state.get("judgment") or {}
    client = KalshiClient.from_env()
    if not client.authenticated:
        return {**state, "executed": False,
                "execution_result": {"status": "NO_CREDENTIALS"}}

    order = {
        "ticker": market.get("ticker"),
        "action": "buy",
        "side": judgment.get("side"),
        "count": int(decision["size_contracts"]),
        "type": "limit",
        "yes_price": int(decision["limit_price_cents"]),
        "client_order_id": f"agent-{int(time.time())}",
    }
    try:
        result = client.post("/portfolio/orders", order)
        return {**state, "executed": True,
                "execution_result": {"status": "SUBMITTED", "response": result}}
    except Exception as e:
        return {**state, "executed": False,
                "execution_result": {"status": "ERROR", "detail": str(e)[:300]}}
