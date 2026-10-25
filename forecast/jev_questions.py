"""Every question sent to Jev (TypeSafe System One model), in one place.

Jev makes small judgments about a contract's TEXT; code makes every decision.
State per market = title, YES outcome, series name and rules text, all of
which exist when the market opens. Nothing about settlement is ever sent
(no result, expiration_value, settlement fields).

Two kinds of question:
  TEXT   asks only about what the contract text says. Safe for backtests.
  WORLD  needs Jev's knowledge of the world. Jev may have read about how a
         past market resolved, so WORLD answers are only used forward, and
         only if the contamination probe says they are not leaking.
PROBE is never a feature: it asks Jev outright whether the outcome happened,
to measure how much Jev already knows about resolved markets.

Bump QSET_VERSION whenever any wording changes; the cache is keyed on it.
"""
from __future__ import annotations

from typesafe_sdk import Choice, Noul, Score

MODEL = "jev-1.14.0"   # pinned, not the alias, so answers are reproducible
QSET_VERSION = "q1"

TEXT_NOULS = {
    "yes_needs_new_event": dict(
        instructions="To resolve YES, does something new have to happen, as described in `rules`?",
        criteria={"true": "YES pays only if a new event occurs, such as a person resigning, a bill passing, a visit, or an announcement.",
                  "false": "YES pays if things simply stay as they are, or the market is one option in a scheduled contest between candidates."}),
    "deadline_no": dict(
        instructions="Do `rules` say the market resolves No if the event has not happened by a stated date?",
        criteria={"true": "The rules set a date and say the answer is No if the event has not happened by then.",
                  "false": "The rules settle the market on the result of a scheduled event, with no 'by this date' condition."}),
    "one_person_decides": dict(
        instructions="Is whether YES happens mainly up to one named person's own decision?",
        criteria={"true": "One named person can make YES happen by choosing to, for example by resigning, signing, pardoning, or visiting.",
                  "false": "The outcome depends on voters, a group, a court, or events no single person controls."}),
    "scheduled_contest": dict(
        instructions="Is the market settled by a scheduled vote, such as an election, primary, referendum, or legislative vote?",
        criteria={"true": "The outcome is decided by a vote that is scheduled to take place.",
                  "false": "The outcome is decided by some other event, such as an announcement, a ruling, a statement, or a number being published."}),
    "numeric_threshold": dict(
        instructions="Does YES depend on a number being above or below a stated threshold?",
        criteria={"true": "YES depends on a number, such as a vote margin, an approval rating, seats won, or a count, crossing a stated value.",
                  "false": "YES depends on who wins or whether an event happens, not on a number crossing a value."}),
    "words_spoken": dict(
        instructions="Does YES depend on a person saying a specific word or phrase?",
        criteria={"true": "The market pays YES if someone says a given word or phrase, for example in a speech or interview.",
                  "false": "The market is about an action, an event, or a result, not about words being said."}),
    "yes_is_one_of_many": dict(
        instructions="Is `yes_outcome` one option among several competing options for the same question?",
        criteria={"true": "This market is one candidate or option in a field, such as one of several people who could win a primary.",
                  "false": "This market asks a single yes-or-no question with no competing named options."}),
}

TEXT_SCORES = {
    "rules_ambiguity": dict(
        instructions="How much room do `rules` leave for dispute about whether YES happened?",
        criteria=["The rules name an exact official source and a clear test for YES.",
                  "The rules are clear, but deciding YES needs some judgment about sources or wording.",
                  "The rules leave real room to argue about whether YES happened."]),
}

TEXT_CHOICES = {
    "subject": dict(
        instructions="What is `market_question` mainly about?",
        criteria={"election_result": "Who wins an election, primary, or nomination, or by how much.",
                  "legislation": "A bill, law, budget, or vote in a legislature.",
                  "executive_action": "An action by a president, governor, or agency, such as an order, pardon, or appointment.",
                  "court_ruling": "A decision by a court or judge.",
                  "personnel_change": "Someone leaving, being fired, or being appointed to a post.",
                  "international": "Relations between countries, foreign leaders, wars, or treaties.",
                  "public_statement": "What a person says, posts, or mentions.",
                  "polling_or_approval": "A poll number, approval rating, or ranking."}),
}

WORLD_NOULS = {
    "dramatic_outcome": dict(
        instructions="Would YES, as described in `market_question`, be an unusual outcome that makes big news?",
        criteria={"true": "YES would be a surprising, dramatic, or rare outcome that would lead the news.",
                  "false": "YES would be a routine or expected outcome."}),
}

PROBE_NOULS = {
    "probe_happened": dict(
        instructions="Did the outcome described by `market_question` and `yes_outcome` actually happen?",
        criteria={"true": "It happened: the YES outcome occurred.",
                  "false": "It did not happen: the YES outcome did not occur."}),
}

FEATURES_NOUL = list(TEXT_NOULS)
FEATURES_SCORE = list(TEXT_SCORES)
FEATURES_CHOICE = {k: list(v["criteria"]) for k, v in TEXT_CHOICES.items()}


def questions(include_world: bool = True, include_probe: bool = True) -> dict:
    q = {k: Noul(**v) for k, v in TEXT_NOULS.items()}
    q.update({k: Score(**v) for k, v in TEXT_SCORES.items()})
    q.update({k: Choice(**v) for k, v in TEXT_CHOICES.items()})
    if include_world:
        q.update({k: Noul(**v) for k, v in WORLD_NOULS.items()})
    if include_probe:
        q.update({k: Noul(**v) for k, v in PROBE_NOULS.items()})
    return q
