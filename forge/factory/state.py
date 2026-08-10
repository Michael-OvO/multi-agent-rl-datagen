"""The state of one generation job, as a value.

`state.json` is a job's whole truth: the orchestrator resumes from it after
any kill, and the board renders the queue from nothing else. That makes the
dict round-trip load-bearing rather than a convenience -- a field dropped on
load is a job that resumes into a state it never parked in, and a board that
reports it. Every field the two design docs specify is represented here, and
`test_factory_state.py` pins the round-trip exactly.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The lifecycle states, in the order a healthy job passes through them.
#: `stuck` is entered from any running state when a cap is exhausted;
#: `abandoned` is a human decision available from anywhere.
STATUSES = (
    "queued",
    "running",
    "awaiting-spec-approval",
    "awaiting-release-review",
    "shipped",
    "quarantined",
    "blocked",
    "stuck",
    "abandoned",
)

#: The ten skill stages. The cursor is 1-based and maps one-to-one onto
#: `skills/build-ground-up-multi-agent-tasks/SKILL.md`.
FIRST_STAGE = 1
LAST_STAGE = 10


@dataclass(frozen=True)
class Caps:
    """Per-job ceilings. Exhausting either parks the job `stuck` with the
    spend recorded -- never a silent stop."""

    attempts_per_stage: int
    total_tokens: int


@dataclass(frozen=True)
class Spend:
    """What the job has cost so far, accumulated from session results."""

    total_tokens: int
    sessions: int


@dataclass(frozen=True)
class Attempt:
    """One session run against one stage.

    Recorded whatever the outcome, including infrastructure failures, because
    the skill's audit trail needs the principals: `session_id` is what proves
    a reviewer was a different principal than the author.
    """

    stage: int
    attempt: int
    role: str
    session_id: str
    model: str
    started: str
    #: None while the session is in flight; the board reads that as running.
    ended: str | None
    tokens: int
    outcome: str
    #: Path to the gate checker's verdict, relative to the job directory.
    #: None until the checker has run.
    check: str | None


@dataclass(frozen=True)
class Approval:
    """A human gate, passed. `by` comes from the charter's owner field."""

    by: str
    at: str


@dataclass(frozen=True)
class Approvals:
    spec: Approval | None
    release: Approval | None


@dataclass(frozen=True)
class JobState:
    job: str
    created: str
    #: Timestamp of the last transition. The board renders it always, so a
    #: stopped orchestrator reads as stale rather than as live.
    updated: str
    status: str
    stage: int
    branch: str
    worktree: str
    caps: Caps
    spend: Spend
    attempts: tuple[Attempt, ...]
    approvals: Approvals
    release_decision: str | None


def _approval_from_dict(value: dict | None) -> Approval | None:
    return None if value is None else Approval(by=value["by"], at=value["at"])


def _approval_to_dict(value: Approval | None) -> dict | None:
    return None if value is None else {"by": value.by, "at": value.at}


def state_from_dict(data: dict) -> JobState:
    """Parse `state.json`'s contents. Raises KeyError on a missing field --
    a truncated state file is a bug to surface, not a default to invent."""
    approvals = data["approvals"]
    return JobState(
        job=data["job"],
        created=data["created"],
        updated=data["updated"],
        status=data["status"],
        stage=data["stage"],
        branch=data["branch"],
        worktree=data["worktree"],
        caps=Caps(**data["caps"]),
        spend=Spend(**data["spend"]),
        attempts=tuple(Attempt(**a) for a in data["attempts"]),
        approvals=Approvals(
            spec=_approval_from_dict(approvals["spec"]),
            release=_approval_from_dict(approvals["release"]),
        ),
        release_decision=data["release_decision"],
    )


def state_to_dict(state: JobState) -> dict:
    """The inverse of `state_from_dict`, key-for-key."""
    return {
        "job": state.job,
        "created": state.created,
        "updated": state.updated,
        "status": state.status,
        "stage": state.stage,
        "branch": state.branch,
        "worktree": state.worktree,
        "caps": {"attempts_per_stage": state.caps.attempts_per_stage,
                 "total_tokens": state.caps.total_tokens},
        "spend": {"total_tokens": state.spend.total_tokens,
                  "sessions": state.spend.sessions},
        "attempts": [
            {"stage": a.stage, "attempt": a.attempt, "role": a.role,
             "session_id": a.session_id, "model": a.model,
             "started": a.started, "ended": a.ended, "tokens": a.tokens,
             "outcome": a.outcome, "check": a.check}
            for a in state.attempts
        ],
        "approvals": {"spec": _approval_to_dict(state.approvals.spec),
                      "release": _approval_to_dict(state.approvals.release)},
        "release_decision": state.release_decision,
    }
