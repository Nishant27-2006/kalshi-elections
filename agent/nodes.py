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

from .config import EXITS, MODELS, ORDER_STP, ORDER_TIME_IN_FORCE, RISK
from .exits import default_levels, evaluate_exit
from .knowledge_graph import CONTEXT_HEADER, SLOT_LABELS, VaultGraph
from .portfolio import Portfolio, Position
from .risk import evaluate
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
        # T2 cannot run. Degrade CLOSED, matching T5: previously this returned
        # is_relevant=True, so every entity match fell through to T4 and spent
        # real Kalshi API calls on headlines that judge_node could never judge.
        # seed_search above is free and local, so it still runs -- it is the
        # graph edge, not the search, that reaches T4.
        allowed = RISK.allow_market_snapshot_without_triage
        return {**state,
                "is_relevant": allowed,
                "decision": "SKIPPED_NO_KEY",
                "triage_reason": (
                    "T2 skipped - no API key. Pipeline short-circuit to END "
                    "unless ALLOW_MARKET_SNAPSHOT_WITHOUT_TRIAGE=true"
                    + (" (override ON: proceeding to T4)" if allowed else "")),
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
    """Knowledge-graph retrieval from the vault (free, local).

    Produces two things:
      kg_context     -- the full prose blocks (kept for the audit log)
      expert_context -- <=800 chars of compressed, slot-tagged facts, which is
                        what actually goes into the T5 prompt. The point is
                        that the expensive model reasons over pre-computed
                        facts instead of paying to read 6 x 900 chars of note
                        body every time.
    """
    title = state.get("news", {}).get("title", "")
    g = vault()
    titles, ctx = g.retrieve_context(title, max_notes=6)
    expert = g.expert_context(titles, max_chars=800) if titles else {}
    return {**state, "kg_titles": titles, "kg_context": ctx,
            "expert_context": expert or None}


def format_expert_context(expert: dict | None) -> str:
    """Render the compressed facts for the judge prompt.

    Returns "" when there is nothing to say -- per the no-empty-block rule, an
    absent section is better than a section that says "no information", which
    reads as evidence of absence.
    """
    if not expert:
        return ""
    # Labels and header live in knowledge_graph so expert_context can
    # charge its budget for the exact text this function will emit.
    lines = [f"{SLOT_LABELS.get(k, k)}: {v}" for k, v in expert.items() if v]
    if not lines:
        return ""
    return CONTEXT_HEADER + "\n".join(lines) + "\n\n"



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


def _declined(reason: str) -> dict:
    """A complete, explicit no-trade Judgment. Every field the schema defines
    is present; `should_trade=False` is what actually stops the graph."""
    return {"should_trade": False, "side": "none", "fair_value_cents": None,
            "confidence": 0.0, "reasoning": reason, "key_risk": "degraded"}


def judge_node(state: AgentState) -> AgentState:
    """The expensive call. Only reached by genuine candidates."""
    market = state.get("market")
    if not market:
        return {**state, "judgment": _declined("no market matched at T4")}

    client = _anthropic()
    if client is None:
        # Degrade closed, but write the FULL schema rather than None so the
        # audit log and any downstream consumer see an explicit refusal
        # instead of a missing field they have to interpret.
        return {**state, "judgment": _declined("T5 unavailable - no LLM key"),
                "decision": "SKIPPED_NO_KEY",
                "notes": [*state.get("notes", []), "no ANTHROPIC_API_KEY; judge skipped"]}

    news = state.get("news", {})
    prompt = (
        format_expert_context(state.get("expert_context"))
        + f"=== MARKET DATA (from T4) ===\n"
        f"Ticker: {market.get('ticker')}\n"
        f"Question: {market.get('title')}\n"
        f"YES bid/ask: {market.get('yes_bid_cents')}c / {market.get('yes_ask_cents')}c\n"
        f"Book depth: {market.get('book_depth_contracts')} contracts\n"
        f"Recent volume: {market.get('volume_recent')}\n\n"
        f"=== HEADLINE ===\n{news.get('title','')}\n"
        f"SOURCE: {news.get('source','')}  TIME: {news.get('pub_date','')}\n"
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
        # Fail closed: an LLM/parse error must never become a trade.
        return {**state, "judgment": _declined(f"judge error: {e}"[:150]),
                "notes": [*state.get("notes", []), f"judge error: {e}"[:150]]}


# ---------------------------------------------------------------- T6

def risk_node(state: AgentState) -> AgentState:
    judgment = state.get("judgment")
    market = state.get("market")
    if not judgment or not market:
        return {**state, "risk": {"approved": False, "reason": "no judgment/market",
                                   "size_contracts": 0, "size_usd": 0.0,
                                   "limit_price_cents": 0.0}}
    # The real ledger, not a blank PortfolioState. This is what makes the
    # duplicate-position / max-open / daily-loss / capital caps bind at all.
    portfolio = Portfolio.load()
    decision = evaluate(judgment, market, portfolio.risk_state(), RISK)
    return {**state, "risk": decision}


# ---------------------------------------------------------------- T7

# Create Order v2. The legacy /portfolio/orders endpoint was slated for
# deprecation "no earlier than May 6, 2026" -- already past. Schema per
# docs.kalshi.com/api-reference/orders/create-order-v2 (checked 2026-08-17).
ORDER_PATH = "/portfolio/events/orders"


def translate_side(side: str, price_cents: float, *,
                   action: str = "open") -> tuple[str, float]:
    """(our side, price in our side's cents) -> (v2 side, YES-leg price cents).

    The one subtle thing in the whole execution path, so it lives in one pure
    function that tests can assert without a network. Kalshi v2 expresses
    every order on the YES leg: `bid` = buy YES, `ask` = sell YES (which is
    economically identical to buying NO). Prices everywhere else in this repo
    are denominated in the price of the side we chose, so a NO at Xc goes on
    the wire as the YES leg at (100 - X)c.

        open  yes @63c -> ("bid", 63.0)   pays 63.0c
        open  no  @22c -> ("ask", 78.0)   pays 22.0c
        close yes @70c -> ("ask", 70.0)   sell the YES we hold
        close no  @30c -> ("bid", 70.0)   buy YES back to flatten the NO
    """
    if action not in ("open", "close"):
        raise ValueError(f"action must be open|close, got {action!r}")
    if side == "yes":
        return ("bid" if action == "open" else "ask"), float(price_cents)
    if side == "no":
        return ("ask" if action == "open" else "bid"), 100.0 - float(price_cents)
    raise ValueError(f"cannot build order for side {side!r}")


def _order_body(ticker: str, v2_side: str, price_c: float, count: int) -> dict:
    return {
        "ticker": ticker,
        "side": v2_side,
        # fixed-point strings, not ints: count 2dp, price up to 4dp
        "count": f"{int(count)}.00",
        "price": f"{price_c / 100.0:.4f}",
        "time_in_force": ORDER_TIME_IN_FORCE,
        "self_trade_prevention_type": ORDER_STP,
        "client_order_id": f"agent-{int(time.time() * 1000)}",
    }


def build_order_payload(market: dict, judgment: dict, decision: dict) -> dict:
    """Translate an approved RiskDecision into a Create Order v2 body.

    Pure and I/O-free so it can be asserted against the schema in tests
    without touching the network.
    """
    v2_side, price_c = translate_side(judgment.get("side"),
                                      float(decision["limit_price_cents"]),
                                      action="open")
    return _order_body(market.get("ticker"), v2_side, price_c,
                       int(decision["size_contracts"]))


def build_exit_payload(pos: "Position", exit_price_cents: float) -> dict:
    """Create Order v2 body that flattens `pos` -- the mirror of the entry."""
    v2_side, price_c = translate_side(pos.side, float(exit_price_cents),
                                      action="close")
    return _order_body(pos.ticker, v2_side, price_c, pos.size_contracts)


def _record_fill(market: dict, judgment: dict, decision: dict, *,
                 paper: bool, note: str) -> Position:
    """Write the position to the ledger. Called on every fill, paper or real.

    Paper fills are recorded deliberately: if a dry run does not consume a
    position slot, the four portfolio caps stay unbound and a dry run tells you
    nothing about how the live loop would behave.
    """
    entry = float(decision["limit_price_cents"])
    tp, sl, hold = default_levels(entry, EXITS)
    pos = Position(
        ticker=market.get("ticker", ""),
        side=judgment.get("side", "none"),
        size_contracts=int(decision["size_contracts"]),
        entry_price_cents=entry,
        cost_usd=float(decision["size_usd"]),
        take_profit_cents=tp,
        stop_loss_cents=sl,
        close_ts=market.get("close_time") or market.get("close_ts"),
        hold_to_resolution=hold,
        paper=paper,
        note=note,
    )
    book = Portfolio.load()
    book.open_position(pos)
    return pos


def execute_node(state: AgentState) -> AgentState:
    """Place the order — only if execution is explicitly enabled AND live.

    Gate is `is_live()`, not `execution_enabled`: the latter alone would let
    EXECUTION_ENABLED=true with env=demo reach client.post().
    """
    decision = state.get("risk") or {}
    if not decision.get("approved"):
        return {**state, "executed": False}

    market = state.get("market") or {}
    judgment = state.get("judgment") or {}

    if not RISK.is_live():
        pos = _record_fill(market, judgment, decision, paper=True,
                           note="dry-run paper fill")
        return {**state, "executed": False,
                "execution_result": {
                    "status": "DRY_RUN",
                    "detail": (f"execution_enabled={RISK.execution_enabled} "
                               f"env={RISK.env} -> is_live=False"),
                    "would_send": build_order_payload(market, judgment, decision),
                    "paper_position": pos.ticker}}

    from kalshi_client import KalshiClient
    client = KalshiClient.from_env()
    if not client.authenticated:
        return {**state, "executed": False,
                "execution_result": {"status": "NO_CREDENTIALS"}}

    order = build_order_payload(market, judgment, decision)
    try:
        result = client.post(ORDER_PATH, order)
    except Exception as e:
        return {**state, "executed": False,
                "execution_result": {"status": "ERROR", "detail": str(e)[:300]}}

    # Ledger write happens only after the API accepted the order, so a failed
    # POST can never leave a phantom position blocking the ticker.
    pos = _record_fill(market, judgment, decision, paper=False, note="live fill")
    return {**state, "executed": True,
            "execution_result": {"status": "SUBMITTED", "response": result,
                                 "position": pos.ticker}}


# ---------------------------------------------------------------- T8 (exits)

def manage_positions(quotes: dict[str, dict], *, now=None,
                     client=None) -> list[dict]:
    """Walk every open position and close the ones that triggered.

    `quotes` maps ticker -> MarketSnapshot-shaped dict. Passing quotes in
    (rather than fetching here) keeps this testable offline and keeps the
    network in one place. Returns one record per position for the audit log.
    """
    book = Portfolio.load()
    results: list[dict] = []

    for pos in list(book.positions):
        market = quotes.get(pos.ticker)
        if not market:
            results.append({"ticker": pos.ticker, "action": "hold",
                            "reason": "no quote available this cycle"})
            continue

        ex = evaluate_exit(pos, market, now=now)
        if not ex["should_exit"]:
            results.append({"ticker": pos.ticker, "action": "hold",
                            "reason": ex["reason"],
                            "unrealized_usd": pos.unrealized_usd(market)})
            continue

        payload = build_exit_payload(pos, ex["exit_price_cents"])
        if not RISK.is_live():
            trade = book.close_position(pos.ticker, ex["exit_price_cents"],
                                        f"{ex['kind']}: {ex['reason']}")
            results.append({"ticker": pos.ticker, "action": "exit_dry_run",
                            "kind": ex["kind"], "reason": ex["reason"],
                            "realized_usd": trade.realized_usd,
                            "would_send": payload})
            continue

        from kalshi_client import KalshiClient
        c = client or KalshiClient.from_env()
        if not c.authenticated:
            results.append({"ticker": pos.ticker, "action": "exit_failed",
                            "reason": "NO_CREDENTIALS"})
            continue
        try:
            resp = c.post(ORDER_PATH, payload)
        except Exception as e:
            # Leave the position open: an unsent exit must not book a fake P&L.
            results.append({"ticker": pos.ticker, "action": "exit_failed",
                            "reason": str(e)[:200]})
            continue
        trade = book.close_position(pos.ticker, ex["exit_price_cents"],
                                    f"{ex['kind']}: {ex['reason']}")
        results.append({"ticker": pos.ticker, "action": "exit_submitted",
                        "kind": ex["kind"], "realized_usd": trade.realized_usd,
                        "response": resp})

    return results
