"""Vault compression contract.

Two regressions are guarded here:
  1. a fixed per-slot allowance let the first slots eat the whole budget, so
     later slots silently never rendered;
  2. the budget was applied to the bare facts, so a nominal 800-char cap
     rendered 898 chars into the prompt.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.config import VAULT_PATH
from agent.knowledge_graph import CONTEXT_HEADER, SLOT_LABELS, VaultGraph
from agent.nodes import format_expert_context

pytestmark = pytest.mark.skipif(not VAULT_PATH.exists(),
                                reason="local Obsidian vault not present")

HEADLINES = [
    "Casey Askar surges in Florida FL-22 GOP primary",
    "James Fishback closes gap on Byron Donalds in Florida governor primary",
    "Bernard Taylor overtakes James Martin in FL-22",
    "Jay Collins campaigns across Florida",
]


@pytest.fixture(scope="module")
def g():
    return VaultGraph()


def _block(g, headline, max_chars=800):
    titles, ctx = g.retrieve_context(headline, max_notes=6)
    expert = g.expert_context(titles, max_chars=max_chars)
    return titles, ctx, expert, format_expert_context(expert)


@pytest.mark.parametrize("headline", HEADLINES)
def test_every_slot_including_resolution_source_is_filled(g, headline):
    _, _, expert, _ = _block(g, headline)
    assert set(expert) == set(SLOT_LABELS), f"missing: {set(SLOT_LABELS) - set(expert)}"


@pytest.mark.parametrize("headline", HEADLINES)
def test_rendered_block_respects_the_prompt_cap(g, headline):
    """The cap is a promise about the prompt, not about the bare facts."""
    _, _, _, block = _block(g, headline)
    assert len(block) <= 800, f"rendered {len(block)} chars"


@pytest.mark.parametrize("headline", HEADLINES)
def test_compression_is_real(g, headline):
    _, ctx, _, block = _block(g, headline)
    assert len(ctx) > 5000, "expected the raw retrieval to be large"
    assert len(block) < len(ctx) / 5, "expected at least 5x compression"


def test_resolution_source_comes_from_a_resolution_rules_section(g):
    """The slot went live only because notes now carry the section."""
    _, _, expert, _ = _block(g, HEADLINES[0])
    assert "resolution_source" in expert
    hits = list(VAULT_PATH.glob("*.md"))
    with_rules = [p for p in hits
                  if "## Resolution Rules" in p.read_text(encoding="utf-8", errors="ignore")]
    assert with_rules, "no vault note carries a Resolution Rules section"


def test_empty_retrieval_injects_nothing_at_all(g):
    """No-info must be an absent section, never a section saying 'no info'."""
    assert format_expert_context({}) == ""
    assert format_expert_context(None) == ""
    assert format_expert_context({"timing_risk": ""}) == ""


def test_block_is_labelled_and_headed(g):
    _, _, _, block = _block(g, HEADLINES[0])
    assert block.startswith(CONTEXT_HEADER)
    for label in SLOT_LABELS.values():
        assert f"{label}: " in block


def test_a_tiny_budget_degrades_to_fewer_slots_not_to_overflow(g):
    _, _, expert, block = _block(g, HEADLINES[0], max_chars=300)
    assert len(block) <= 300
    assert len(expert) < len(SLOT_LABELS)


def test_slot_labels_are_the_single_source_of_truth():
    """format_expert_context must not carry its own copy of the labels."""
    src = (Path(__file__).resolve().parent.parent / "agent" / "nodes.py").read_text(encoding="utf-8")
    assert '"Resolution rule"' not in src, "labels duplicated in nodes.py"
