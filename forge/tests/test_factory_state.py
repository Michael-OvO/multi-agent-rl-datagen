"""The generation-job state model: one file is a job's whole truth.

state.json is what the orchestrator resumes from and what the board renders,
so its round-trip must be exact -- a field silently dropped on load is a job
that resumes into a different state than it parked in. These tests pin the
schema shape the two design docs specify.
"""

from __future__ import annotations

import json

from forge.factory.state import state_from_dict, state_to_dict

MINIMAL = {
    "job": "2026-08-10-discovery-hidden-knower",
    "created": "2026-08-10T14:00:00-07:00",
    "updated": "2026-08-10T14:00:00-07:00",
    "status": "queued",
    "stage": 1,
    "branch": "genjob/discovery-hidden-knower",
    "worktree": "/scratch/worktrees/discovery-hidden-knower",
    "caps": {"attempts_per_stage": 3, "total_tokens": 20000000},
    "spend": {"total_tokens": 0, "sessions": 0},
    "attempts": [],
    "approvals": {"spec": None, "release": None},
    "release_decision": None,
}


def test_a_state_round_trips_through_dict_unchanged():
    assert state_to_dict(state_from_dict(MINIMAL)) == MINIMAL


def test_an_attempt_round_trips_with_every_field():
    raw = json.loads(json.dumps(MINIMAL))
    raw["attempts"] = [{
        "stage": 2, "attempt": 1, "role": "author",
        "session_id": "11111111-2222-3333-4444-555555555555",
        "model": "claude-opus-5",
        "started": "2026-08-10T14:03:11-07:00",
        "ended": "2026-08-10T14:19:47-07:00",
        "tokens": 123456,
        "outcome": "gate-passed",
        "check": "attempts/2-1/check.json",
    }]
    state = state_from_dict(raw)
    assert state.attempts[0].role == "author"
    assert state.attempts[0].tokens == 123456
    assert state_to_dict(state) == raw


def test_a_running_attempt_has_no_end_or_check_yet():
    raw = json.loads(json.dumps(MINIMAL))
    raw["attempts"] = [{
        "stage": 1, "attempt": 1, "role": "author",
        "session_id": "abc", "model": "claude-opus-5",
        "started": "2026-08-10T14:03:11-07:00",
        "ended": None, "tokens": 0, "outcome": "running", "check": None,
    }]
    state = state_from_dict(raw)
    assert state.attempts[0].ended is None
    assert state.attempts[0].check is None
    assert state_to_dict(state) == raw


def test_an_approval_round_trips():
    raw = json.loads(json.dumps(MINIMAL))
    raw["approvals"] = {"spec": {"by": "michael", "at": "2026-08-10T15:00:00-07:00"},
                        "release": None}
    state = state_from_dict(raw)
    assert state.approvals.spec is not None
    assert state.approvals.spec.by == "michael"
    assert state_to_dict(state) == raw
