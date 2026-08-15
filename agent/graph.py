"""
LangGraph wiring.

  triage -> [not relevant?] -> END
         -> retrieve -> market_match -> [no market?] -> END
         -> judge -> [no judgment / no trade?] -> END
         -> risk  -> [rejected?] -> END
         -> execute -> END

Every terminal path is logged, including rejections — the audit trail is the
point, not a side effect. Falls back to a plain sequential runner if
langgraph isn't installed, so the same nodes work either way.
"""

from __future__ import annotations

from .nodes import (execute_node, judge_node, market_match_node,
                    retrieve_node, risk_node, triage_node)
from .state import AgentState

try:
    from langgraph.graph import END, StateGraph
    HAS_LANGGRAPH = True
except ImportError:  # pragma: no cover
    HAS_LANGGRAPH = False


def _after_triage(state: AgentState) -> str:
    return "retrieve" if state.get("is_relevant") else "end"


def _after_market(state: AgentState) -> str:
    return "judge" if state.get("market") else "end"


def _after_judge(state: AgentState) -> str:
    j = state.get("judgment")
    return "risk_gate" if j and j.get("should_trade") else "end"


def _after_risk(state: AgentState) -> str:
    r = state.get("risk") or {}
    return "execute" if r.get("approved") else "end"


def build_graph():
    if not HAS_LANGGRAPH:
        return None
    g = StateGraph(AgentState)
    g.add_node("triage", triage_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("market_match", market_match_node)
    g.add_node("judge", judge_node)
    g.add_node("risk_gate", risk_node)
    g.add_node("execute", execute_node)

    g.set_entry_point("triage")
    g.add_conditional_edges("triage", _after_triage,
                            {"retrieve": "retrieve", "end": END})
    g.add_edge("retrieve", "market_match")
    g.add_conditional_edges("market_match", _after_market,
                            {"judge": "judge", "end": END})
    g.add_conditional_edges("judge", _after_judge,
                            {"risk_gate": "risk_gate", "end": END})
    g.add_conditional_edges("risk_gate", _after_risk,
                            {"execute": "execute", "end": END})
    g.add_edge("execute", END)
    return g.compile()


def run_sequential(state: AgentState) -> AgentState:
    """Same logic without LangGraph — used by the backtest and as fallback."""
    state = triage_node(state)
    if not state.get("is_relevant"):
        return {**state, "terminated_at": "triage"}
    state = retrieve_node(state)
    state = market_match_node(state)
    if not state.get("market"):
        return {**state, "terminated_at": "market_match"}
    state = judge_node(state)
    j = state.get("judgment")
    if not j or not j.get("should_trade"):
        return {**state, "terminated_at": "judge"}
    state = risk_node(state)
    if not (state.get("risk") or {}).get("approved"):
        return {**state, "terminated_at": "risk"}
    state = execute_node(state)
    return {**state, "terminated_at": "execute"}
