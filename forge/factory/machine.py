"""The generation-job lifecycle, apart from the filesystem.

The orchestrator's resumability contract (kill it anywhere, relaunch, it
picks up from state.json) only holds if a transition is a function of the
state and nothing else. So these are pure: each takes a JobState and returns
a new one, and `store` is the only thing that writes. Three rules the design
docs leave implicit are decided here, in the refusals: approving the spec
resumes at stage 3 because stage 2 is what was approved; a reopen is legal
only from a running or release-parked job, because reopening a queued job
would skip the stages between; and a shipped family can never be abandoned,
because it has already been delivered and the history would lie.
"""

from __future__ import annotations

from dataclasses import replace

from forge.factory.state import LAST_STAGE, Approval, JobState

#: The release verdicts stage 10 may record, and the status each becomes when
#: the human approves the review. A verdict that is not READY does not ship;
#: approving it records that the review happened.
RELEASE_DECISIONS = {
    "READY": "shipped",
    "QUARANTINED": "quarantined",
    "BLOCKED": "blocked",
}

#: Statuses a reopen may interrupt.
_REOPENABLE = ("running", "awaiting-release-review")


class TransitionError(Exception):
    """An illegal lifecycle move. Carries what was attempted and from where."""


def advance(state: JobState, *, now: str) -> JobState:
    """Gate passed: move the cursor to the next stage."""
    if state.stage >= LAST_STAGE:
        raise TransitionError(
            f"{state.job}: cannot advance past stage {LAST_STAGE}; stage 10 "
            f"parks at awaiting-release-review instead")
    return replace(state, stage=state.stage + 1, status="running", updated=now)


def park_for_spec_approval(state: JobState, *, now: str) -> JobState:
    """Stage 2 passed: stop for the human to read the task contract."""
    return replace(state, status="awaiting-spec-approval", updated=now)


def approve_spec(state: JobState, *, by: str, now: str) -> JobState:
    """The human approved the contract; work resumes at stage 3."""
    if state.status != "awaiting-spec-approval":
        raise TransitionError(
            f"{state.job}: is {state.status!r}, not 'awaiting-spec-approval'; "
            f"there is no spec gate to approve")
    approvals = replace(state.approvals, spec=Approval(by=by, at=now))
    return replace(state, status="running", stage=3, approvals=approvals,
                   updated=now)


def park_for_release(state: JobState, *, decision: str, now: str) -> JobState:
    """Stage 10 finished: park carrying the skill's release verdict."""
    if decision not in RELEASE_DECISIONS:
        raise TransitionError(
            f"{state.job}: release decision {decision!r} is not one of "
            f"{sorted(RELEASE_DECISIONS)}")
    return replace(state, status="awaiting-release-review",
                   release_decision=decision, updated=now)


def approve_release(state: JobState, *, by: str, now: str) -> JobState:
    """The human reviewed the release verdict. READY ships; the others record."""
    if state.status != "awaiting-release-review":
        raise TransitionError(
            f"{state.job}: is {state.status!r}, not 'awaiting-release-review'; "
            f"there is no release gate to approve")
    decision = state.release_decision or ""
    if decision not in RELEASE_DECISIONS:
        raise TransitionError(
            f"{state.job}: parked for release with no valid decision "
            f"({decision!r}); the stage-10 checker did not record one")
    approvals = replace(state.approvals, release=Approval(by=by, at=now))
    return replace(state, status=RELEASE_DECISIONS[decision],
                   approvals=approvals, updated=now)


def mark_stuck(state: JobState, *, reason: str, now: str) -> JobState:
    """A cap is exhausted or a gate needs a human. `reason` is for the caller
    to record beside the job; the state only carries that it stopped."""
    return replace(state, status="stuck", updated=now)


def reopen(state: JobState, *, stage: int, now: str) -> JobState:
    """A critical finding sends the job back to the stage the skill names."""
    if state.status not in _REOPENABLE:
        raise TransitionError(
            f"{state.job}: is {state.status!r}; only "
            f"{' or '.join(_REOPENABLE)} jobs can reopen a stage")
    return replace(state, stage=stage, status="running",
                   release_decision=None, updated=now)


def abandon(state: JobState, *, now: str) -> JobState:
    """A human decision, available everywhere except after delivery."""
    if state.status == "shipped":
        raise TransitionError(
            f"{state.job}: is shipped; abandoning a delivered family would "
            f"misrepresent what happened to it")
    return replace(state, status="abandoned", updated=now)
