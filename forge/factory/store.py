"""The job queue on disk: one directory per job, state.json its whole truth.

Writes are atomic -- temp file in the same directory, then `os.replace` --
because the board reads state.json on a timer while the orchestrator rewrites
it after every transition. A half-written file is a job that cannot resume and
a board rendering nonsense, and both would be silent.

Note what this module does NOT do: create the git branch or the worktree.
Those are side effects on the developer's machine that the state records
(`branch`, `worktree`) but that the CLI performs, so every function here stays
testable in a tmp_path with no git at all.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from forge.factory.charter import parse_charter
from forge.factory.state import (
    Approvals,
    Caps,
    JobState,
    Spend,
    state_from_dict,
    state_to_dict,
)

#: Repo-level default ceilings, overridable per charter (budget only).
DEFAULT_ATTEMPTS_PER_STAGE = 3
DEFAULT_TOTAL_TOKENS = 20_000_000

STATE_FILE = "state.json"


def now_iso() -> str:
    """A timezone-aware ISO-8601 stamp. One helper so tests can pin time."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_state(job_path: Path) -> JobState:
    """Read state.json, and refuse if it disagrees with its own directory.

    `cli.cmd_abandon` and `cmd_approve` both reconstruct a job's directory
    as `root / state.job` -- cheaper than threading a Path through every
    transition. That reconstruction is only sound if a directory's name and
    its state.json `job` field always agree, so the check happens at the one
    place both are in hand: here, on read, as a named refusal instead of a
    raw traceback wherever the mismatch would next be felt.
    """
    state = state_from_dict(json.loads((job_path / STATE_FILE).read_text()))
    if state.job != job_path.name:
        raise SystemExit(
            f"{job_path}: state.json says job={state.job!r}, but the "
            f"directory is named {job_path.name!r}; the two must agree, or "
            f"anything that reconstructs this job's directory from its "
            f"name (the CLI's abandon and approve) will look in the wrong "
            f"place")
    return state


def write_state(job_path: Path, state: JobState) -> None:
    """Write state.json atomically: temp file beside it, then rename."""
    target = job_path / STATE_FILE
    tmp = job_path / f".{STATE_FILE}.tmp"
    tmp.write_text(json.dumps(state_to_dict(state), indent=1) + "\n")
    os.replace(tmp, target)


def discover(root: Path) -> list[JobState]:
    """Every job under `root`, by name. Directories without a state.json are
    not jobs -- a charter directory that was never queued lives here too."""
    if not root.is_dir():
        return []
    states = []
    for path in sorted(root.iterdir()):
        if (path / STATE_FILE).is_file():
            states.append(read_state(path))
    return states


def queue_job(root: Path, charter_dir: Path, *, now: str,
              worktree_root: Path) -> JobState:
    """Validate a charter and register its directory as a job.

    Refuses before writing anything: a charter_dir that is not root's direct
    child, a draft charter, a directory with no charter, or a job that is
    already queued.
    """
    root_r = root.resolve()
    charter_r = charter_dir.resolve()
    if charter_r.parent != root_r:
        # `root_r not in charter_r.parents` is not enough: that is true for
        # ANY descendant, including root/sub/charter-dir -- but discover()
        # only ever calls root.iterdir(), one level deep. A charter nested
        # one directory further passes an ancestor-chain check yet is just
        # as invisible to discover() as a charter outside root entirely, so
        # the check has to match discover's actual reach: a direct child.
        raise SystemExit(
            f"{charter_dir}: is not a direct child of {root}; discover({root}) "
            f"only ever walks its own immediate children, so a charter "
            f"nested any deeper would report 'queued' and then be invisible "
            f"to every later `status` or `board`")

    slug = charter_dir.name
    charter_file = charter_dir / "charter.md"
    if not charter_file.is_file():
        raise SystemExit(
            f"{slug}: no charter.md in {charter_dir}; a job directory is a "
            f"charter plus whatever the factory writes beside it")
    if (charter_dir / STATE_FILE).exists():
        raise SystemExit(
            f"{slug}: already queued ({charter_dir / STATE_FILE} exists); "
            f"use `status` to see where it is, or `abandon` to stop it")

    charter = parse_charter(charter_file.read_text(), slug=slug)
    state = JobState(
        job=slug,
        created=now,
        updated=now,
        status="queued",
        stage=1,
        branch=f"genjob/{slug}",
        worktree=str(worktree_root / slug),
        caps=Caps(attempts_per_stage=DEFAULT_ATTEMPTS_PER_STAGE,
                  total_tokens=charter.budget_tokens or DEFAULT_TOTAL_TOKENS),
        spend=Spend(total_tokens=0, sessions=0),
        attempts=(),
        approvals=Approvals(spec=None, release=None),
        release_decision=None,
    )
    write_state(charter_dir, state)
    return state
