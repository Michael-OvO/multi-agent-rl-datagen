"""The generation-job lifecycle, as pure functions.

The orchestrator is resumable, which means every state change has to be
reconstructible from state.json alone -- so the transitions live here, apart
from the filesystem, and the store just applies what they return. Three rules
the design docs leave implicit are decided here and pinned by these tests:
approving the spec resumes at stage 3, a reopen is only legal from a running
or release-parked job, and a shipped job can never be abandoned.
"""

from __future__ import annotations

import pytest

from forge.factory.machine import (
    TransitionError,
    abandon,
    advance,
    approve_release,
    approve_spec,
    mark_stuck,
    park_for_release,
    park_for_spec_approval,
    reopen,
)
from forge.factory.state import state_from_dict

NOW = "2026-08-10T16:00:00-07:00"


def _state(**overrides):
    base = {
        "job": "2026-08-10-demo", "created": "2026-08-10T14:00:00-07:00",
        "updated": "2026-08-10T14:00:00-07:00", "status": "running",
        "stage": 1, "branch": "genjob/demo", "worktree": "/scratch/demo",
        "caps": {"attempts_per_stage": 3, "total_tokens": 20000000},
        "spend": {"total_tokens": 0, "sessions": 0}, "attempts": [],
        "approvals": {"spec": None, "release": None}, "release_decision": None,
    }
    base.update(overrides)
    return state_from_dict(base)


def test_advance_moves_the_cursor_and_stamps_updated():
    after = advance(_state(stage=3), now=NOW)
    assert after.stage == 4
    assert after.status == "running"
    assert after.updated == NOW


def test_advance_past_the_last_stage_is_refused():
    with pytest.raises(TransitionError, match="stage 10"):
        advance(_state(stage=10), now=NOW)


def test_the_spec_gate_parks_and_resumes_at_stage_three():
    parked = park_for_spec_approval(_state(stage=2), now=NOW)
    assert parked.status == "awaiting-spec-approval"
    assert parked.stage == 2, "the cursor stays on what is being approved"

    resumed = approve_spec(parked, by="michael", now=NOW)
    assert resumed.status == "running"
    assert resumed.stage == 3, "stage 2 is what was approved; work resumes at 3"
    assert resumed.approvals.spec is not None
    assert resumed.approvals.spec.by == "michael"


def test_approving_a_spec_that_was_never_parked_is_refused():
    with pytest.raises(TransitionError, match="awaiting-spec-approval"):
        approve_spec(_state(status="running"), by="michael", now=NOW)


def test_the_release_gate_carries_the_decision_and_ships():
    parked = park_for_release(_state(stage=10), decision="READY", now=NOW)
    assert parked.status == "awaiting-release-review"
    assert parked.release_decision == "READY"

    shipped = approve_release(parked, by="michael", now=NOW)
    assert shipped.status == "shipped"
    assert shipped.approvals.release is not None


def test_a_quarantined_decision_does_not_ship_on_approval():
    parked = park_for_release(_state(stage=10), decision="QUARANTINED", now=NOW)
    reviewed = approve_release(parked, by="michael", now=NOW)
    assert reviewed.status == "quarantined", (
        "approving a QUARANTINED verdict records the review, it does not ship")


def test_a_blocked_decision_lands_blocked():
    parked = park_for_release(_state(stage=10), decision="BLOCKED", now=NOW)
    assert approve_release(parked, by="michael", now=NOW).status == "blocked"


def test_an_unknown_release_decision_is_refused():
    with pytest.raises(TransitionError, match="READY"):
        park_for_release(_state(stage=10), decision="probably-fine", now=NOW)


def test_stuck_records_why():
    stuck = mark_stuck(_state(), reason="token budget exhausted", now=NOW)
    assert stuck.status == "stuck"
    assert stuck.release_decision is None


def test_a_stuck_job_can_reopen_at_an_earlier_stage():
    # A stage-9 critical finding reopens the stage the skill names.
    after = reopen(_state(stage=9, status="running"), stage=3, now=NOW)
    assert after.stage == 3 and after.status == "running"


def test_reopening_from_a_parked_release_is_legal():
    parked = park_for_release(_state(stage=10), decision="BLOCKED", now=NOW)
    assert reopen(parked, stage=7, now=NOW).stage == 7


def test_reopening_a_queued_job_is_refused():
    with pytest.raises(TransitionError, match="queued"):
        reopen(_state(status="queued", stage=1), stage=1, now=NOW)


def test_a_shipped_job_cannot_be_abandoned():
    parked = park_for_release(_state(stage=10), decision="READY", now=NOW)
    shipped = approve_release(parked, by="michael", now=NOW)
    with pytest.raises(TransitionError, match="shipped"):
        abandon(shipped, now=NOW)


def test_any_other_job_can_be_abandoned():
    for status in ("queued", "running", "awaiting-spec-approval", "stuck"):
        assert abandon(_state(status=status), now=NOW).status == "abandoned"


def test_every_transition_returns_a_new_object():
    before = _state(stage=1)
    after = advance(before, now=NOW)
    assert before.stage == 1, "transitions must not mutate their input"
    assert after is not before
