"""The fixture tree is a contract, so it gets tested like one.

These fixtures are the board's only data source in M2 and the state machine's
realism check. A fixture whose stage disagrees with its attempts, or whose
spend does not add up, would teach the board to render states the orchestrator
can never produce -- and the bug would surface only against live jobs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.factory.state import LAST_STAGE, STATUSES
from forge.factory.store import discover

FIXTURES = Path(__file__).parent / "fixtures" / "factory" / "genjobs"

STATES = discover(FIXTURES)


def test_the_tree_covers_every_state_the_board_must_render():
    covered = {s.status for s in STATES}
    assert covered >= {"queued", "running", "awaiting-spec-approval",
                       "stuck", "awaiting-release-review", "abandoned"}


@pytest.mark.parametrize("state", STATES, ids=lambda s: s.job)
def test_every_fixture_is_internally_consistent(state):
    assert state.status in STATUSES
    assert 1 <= state.stage <= LAST_STAGE
    assert state.created <= state.updated
    assert state.spend.sessions >= len(state.attempts)
    for attempt in state.attempts:
        assert 1 <= attempt.stage <= state.stage, (
            f"{state.job}: attempt on stage {attempt.stage} but the cursor is "
            f"at {state.stage}")
        assert attempt.attempt <= state.caps.attempts_per_stage
        if attempt.ended is not None:
            assert attempt.started <= attempt.ended
        else:
            assert attempt.outcome == "running"
            assert attempt.check is None


@pytest.mark.parametrize("state", STATES, ids=lambda s: s.job)
def test_every_referenced_check_file_exists_and_parses(state):
    for attempt in state.attempts:
        if attempt.check is None:
            continue
        path = FIXTURES / state.job / attempt.check
        assert path.is_file(), f"{state.job}: {attempt.check} is referenced but absent"
        verdict = json.loads(path.read_text())
        assert verdict["stage"] == attempt.stage
        assert isinstance(verdict["passed"], bool)


def test_a_parked_release_carries_its_decision():
    for state in STATES:
        if state.status == "awaiting-release-review":
            assert state.release_decision in ("READY", "QUARANTINED", "BLOCKED")
