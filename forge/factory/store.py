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
    return state_from_dict(json.loads((job_path / STATE_FILE).read_text()))


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

    Refuses before writing anything: a draft charter, a directory with no
    charter, or a job that is already queued.
    """
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
