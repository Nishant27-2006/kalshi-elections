"""Invariant C: when T2 cannot run, nothing reaches T4.

The regression this guards: triage used to return is_relevant=True with no
API key, so every vault entity match fell through to market_match and spent
real Kalshi API calls on headlines judge_node could never judge.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import graph as graph_mod
from agent import nodes
from agent.config import RiskLimits


@pytest.fixture
def no_llm_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(nodes, "_anthropic", lambda: None)


@pytest.fixture
def counters(monkeypatch):
    """Count T4 invocations and every outbound HTTP call."""
    c = {"t4": 0, "http": 0}
    real_t4 = nodes.market_match_node

    def counting_t4(state, client=None):
        c["t4"] += 1
        return real_t4(state, client=client)

    def counting_get(*a, **k):
        c["http"] += 1
        raise AssertionError(f"unexpected HTTP call: {a[:1]}")

    monkeypatch.setattr(nodes, "market_match_node", counting_t4)
    monkeypatch.setattr(graph_mod, "market_match_node", counting_t4)
    monkeypatch.setattr("requests.get", counting_get)
    monkeypatch.setattr("requests.post", counting_get)
    return c


HEADLINE = {"news": {"title": "Byron Donalds leads Florida governor primary poll",
                     "source": "Test", "pub_date": "", "hash": "t"},
            "notes": []}


def test_no_key_terminates_at_triage_with_zero_t4_and_zero_http(no_llm_key, counters):
    result = graph_mod.run_sequential(dict(HEADLINE))
    assert result["terminated_at"] == "triage"
    assert result["is_relevant"] is False
    assert counters["t4"] == 0, "T4 must not be reached without triage"
    assert counters["http"] == 0, "no network call may happen without triage"


def test_no_key_records_the_degradation_explicitly(no_llm_key, counters):
    """Only asserted when the vault actually matched -- a no-match headline
    terminates one step earlier, which is also fine."""
    result = graph_mod.run_sequential(dict(HEADLINE))
    if result.get("entities"):
        assert result["decision"] == "SKIPPED_NO_KEY"
        assert "T2 skipped" in result["triage_reason"]


def test_override_flag_is_the_only_way_through(no_llm_key, counters, monkeypatch):
    """ALLOW_MARKET_SNAPSHOT_WITHOUT_TRIAGE=true is the documented escape
    hatch for collecting backtest data. It must be the ONLY one."""
    monkeypatch.setattr(nodes, "RISK",
                        RiskLimits(allow_market_snapshot_without_triage=True))
    result = nodes.triage_node(dict(HEADLINE))
    if result.get("entities"):
        assert result["is_relevant"] is True
        assert "override ON" in result["triage_reason"]
    else:
        assert result["is_relevant"] is False


def test_t5_degrades_with_the_full_six_field_schema(no_llm_key):
    """Invariant D: _declined() writes every field, never None-as-missing."""
    out = nodes.judge_node({"market": {"ticker": "KXTEST", "title": "t"}})
    j = out["judgment"]
    assert set(j) == {"should_trade", "side", "fair_value_cents",
                      "confidence", "reasoning", "key_risk"}
    assert j["should_trade"] is False and j["side"] == "none"
    assert out["decision"] == "SKIPPED_NO_KEY"


def test_t5_no_market_path_also_writes_six_fields(no_llm_key):
    out = nodes.judge_node({"market": None})
    assert set(out["judgment"]) == {"should_trade", "side", "fair_value_cents",
                                    "confidence", "reasoning", "key_risk"}
    assert out["judgment"]["should_trade"] is False
