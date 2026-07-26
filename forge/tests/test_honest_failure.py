"""The honest-failure channel: surrender routes through status='fail'.

The measurement this exists to fix (sweep/appworld_honesty.json): a truthful
prose failure report scores 0.167 -- below the 0.333 do-nothing floor -- on
all three shipped tasks, while `complete_task(status='fail')` scores exactly
the floor. Before this channel existed, the protocol paid the Main 1/6 more
for a false `completed` than for the truth; at RL scale that is a trained
lie. The fix is protocol, not oracle: give the Main a FAIL verb, and route
every surrender sentinel through the submission the protocol prices at the
floor. The judge is untouched.
"""

from __future__ import annotations

from forge.appworld.partition import Constraints, Topology, Visibility
from forge.appworld.runtime import (
    NO_ANSWER,
    OUT_OF_STEPS,
    RunLog,
    _main_system,
    gave_up,
    run_main,
    submission_code,
)

_CONSTRAINTS = Constraints(
    roster=("phone", "venmo"),
    topology=Topology.STAR,
    visibility=Visibility.NAMES,
)


class _MainOnlyClient:
    """Replays scripted Main replies; no specialist is ever reached."""

    def __init__(self, replies: list[str]):
        self._replies = list(replies)

        outer = self

        class _Completions:
            def create(self, model, messages, temperature):
                text = outer._replies.pop(0)
                message = type("M", (), {"content": text})()
                choice = type("C", (), {"message": message})()
                return type("R", (), {"choices": [choice]})()

        self.chat = type("Chat", (), {"completions": _Completions()})()


# --- the protocol ----------------------------------------------------------


def test_main_prompt_offers_the_fail_verb():
    prompt = _main_system(_CONSTRAINTS, "note")
    assert "FAIL ::" in prompt
    # And it must say what FAIL is for, not just that it exists.
    assert "cannot complete" in prompt.lower()


def test_run_main_returns_the_failure_instead_of_a_malformed_nag():
    client = _MainOnlyClient(["FAIL :: venmo has no API for this"])
    answer = run_main(client, None, "task", _CONSTRAINTS, RunLog())
    assert answer == "FAIL :: venmo has no API for this"


def test_a_bare_fail_still_counts_as_surrender():
    client = _MainOnlyClient(["FAIL"])
    answer = run_main(client, None, "task", _CONSTRAINTS, RunLog())
    assert gave_up(answer)


# --- the surrender predicate ------------------------------------------------


def test_every_surrender_sentinel_is_gave_up():
    assert gave_up(OUT_OF_STEPS)
    assert gave_up(NO_ANSWER)
    assert gave_up("FAIL :: could not find the transactions")


def test_claims_and_answers_are_not_surrender():
    assert not gave_up("completed")
    assert not gave_up("42 songs")


# --- the submission ---------------------------------------------------------


def test_surrender_submits_status_fail():
    assert (
        submission_code("FAIL :: no way in")
        == "apis.supervisor.complete_task(status='fail')"
    )
    assert (
        submission_code(OUT_OF_STEPS)
        == "apis.supervisor.complete_task(status='fail')"
    )


def test_completed_submits_the_action_answer():
    assert (
        submission_code("completed")
        == "apis.supervisor.complete_task(answer=None, status='success')"
    )


def test_a_value_answer_submits_as_itself():
    assert (
        submission_code("42 songs")
        == "apis.supervisor.complete_task(answer='42 songs', status='success')"
    )
