"""Reading and writing the job queue on disk.

state.json is rewritten after every transition while the board may be reading
it, so writes are atomic (temp file, then rename) -- a half-written state file
is a job the orchestrator cannot resume and a board that renders nonsense.
"""

from __future__ import annotations

import json

import pytest

from forge.factory.store import (
    discover,
    queue_job,
    read_state,
    write_state,
)

CHARTER = """---
status: ready
owner: michael
ability: capability-discovery
---

# Charter: the hidden knower

**Capability claim.** A coordinator can identify which teammate can know a fact.
"""


def _seed(root, name, **overrides):
    data = {
        "job": name, "created": "2026-08-10T14:00:00-07:00",
        "updated": "2026-08-10T14:00:00-07:00", "status": "running",
        "stage": 1, "branch": f"genjob/{name}", "worktree": "/scratch/x",
        "caps": {"attempts_per_stage": 3, "total_tokens": 20000000},
        "spend": {"total_tokens": 0, "sessions": 0}, "attempts": [],
        "approvals": {"spec": None, "release": None}, "release_decision": None,
    }
    data.update(overrides)
    job = root / name
    job.mkdir(parents=True)
    (job / "state.json").write_text(json.dumps(data, indent=1))
    return job


def test_a_state_survives_a_write_read_round_trip(tmp_path):
    job = _seed(tmp_path, "2026-08-10-demo")
    state = read_state(job)
    write_state(job, state)
    assert read_state(job) == state


def test_writing_leaves_no_temp_file_behind(tmp_path):
    job = _seed(tmp_path, "2026-08-10-demo")
    write_state(job, read_state(job))
    assert [p.name for p in job.iterdir()] == ["state.json"]


def test_discover_finds_every_job_sorted_and_ignores_strays(tmp_path):
    _seed(tmp_path, "2026-08-10-b")
    _seed(tmp_path, "2026-08-10-a")
    (tmp_path / "not-a-job").mkdir()
    (tmp_path / "board.html").write_text("<!-- rendered -->")
    assert [s.job for s in discover(tmp_path)] == ["2026-08-10-a", "2026-08-10-b"]


def test_discover_on_a_missing_root_is_empty_not_an_error(tmp_path):
    assert discover(tmp_path / "nothing-here") == []


def test_queue_writes_a_queued_state_from_the_charter(tmp_path):
    charter_dir = tmp_path / "genjobs" / "2026-08-10-hidden-knower"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.md").write_text(CHARTER)

    state = queue_job(tmp_path / "genjobs", charter_dir,
                      now="2026-08-10T16:00:00-07:00",
                      worktree_root=tmp_path / "scratch")

    assert state.status == "queued"
    assert state.stage == 1
    assert state.job == "2026-08-10-hidden-knower"
    assert state.branch == "genjob/2026-08-10-hidden-knower"
    assert state.created == state.updated == "2026-08-10T16:00:00-07:00"
    assert read_state(charter_dir) == state


def test_queueing_a_draft_charter_is_refused_before_anything_is_written(tmp_path):
    charter_dir = tmp_path / "genjobs" / "2026-08-10-draft-job"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.md").write_text(
        CHARTER.replace("status: ready", "status: draft"))

    with pytest.raises(SystemExit, match="draft"):
        queue_job(tmp_path / "genjobs", charter_dir,
                  now="2026-08-10T16:00:00-07:00",
                  worktree_root=tmp_path / "scratch")
    assert not (charter_dir / "state.json").exists(), (
        "a refused charter must leave no state behind")


def test_queueing_twice_is_refused(tmp_path):
    charter_dir = tmp_path / "genjobs" / "2026-08-10-hidden-knower"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.md").write_text(CHARTER)
    kwargs = {"now": "2026-08-10T16:00:00-07:00",
              "worktree_root": tmp_path / "scratch"}
    queue_job(tmp_path / "genjobs", charter_dir, **kwargs)
    with pytest.raises(SystemExit, match="already queued"):
        queue_job(tmp_path / "genjobs", charter_dir, **kwargs)


def test_queueing_a_directory_without_a_charter_is_refused(tmp_path):
    empty = tmp_path / "genjobs" / "2026-08-10-empty"
    empty.mkdir(parents=True)
    with pytest.raises(SystemExit, match="charter.md"):
        queue_job(tmp_path / "genjobs", empty,
                  now="2026-08-10T16:00:00-07:00",
                  worktree_root=tmp_path / "scratch")
