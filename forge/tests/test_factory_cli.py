"""The factory command line: the only way a human moves a job.

Every verb is exercised against a tmp_path root, so these tests need no git,
no network, and no sessions -- the same property that lets the board be built
before the orchestrator exists.
"""

from __future__ import annotations

import json

import pytest

from forge.factory import machine, store
from forge.factory.cli import main

CHARTER = """---
status: ready
owner: michael
ability: capability-discovery
---

# Charter: the hidden knower

**Capability claim.** A coordinator can identify which teammate can know a fact.
"""


def _charter_dir(tmp_path, slug="2026-08-10-hidden-knower", text=CHARTER):
    d = tmp_path / "genjobs" / slug
    d.mkdir(parents=True)
    (d / "charter.md").write_text(text)
    return d


def test_queue_registers_a_job_and_reports_it(tmp_path, capsys):
    d = _charter_dir(tmp_path)
    main(["queue", str(d), "--root", str(tmp_path / "genjobs")])
    out = capsys.readouterr().out
    assert "2026-08-10-hidden-knower" in out
    assert "queued" in out
    assert json.loads((d / "state.json").read_text())["status"] == "queued"


def test_queue_refuses_a_draft_and_says_why(tmp_path):
    d = _charter_dir(tmp_path, text=CHARTER.replace("status: ready", "status: draft"))
    with pytest.raises(SystemExit, match="draft"):
        main(["queue", str(d), "--root", str(tmp_path / "genjobs")])


def test_status_lists_every_job(tmp_path, capsys):
    for slug in ("2026-08-10-a", "2026-08-10-b"):
        d = _charter_dir(tmp_path, slug=slug)
        main(["queue", str(d), "--root", str(tmp_path / "genjobs")])
    capsys.readouterr()
    main(["status", "--root", str(tmp_path / "genjobs")])
    out = capsys.readouterr().out
    assert "2026-08-10-a" in out and "2026-08-10-b" in out


def test_status_on_an_empty_root_says_so_rather_than_printing_nothing(tmp_path, capsys):
    main(["status", "--root", str(tmp_path / "genjobs")])
    assert "no jobs" in capsys.readouterr().out.lower()


def test_status_with_job_filters_to_that_job_alone(tmp_path, capsys):
    for slug in ("2026-08-10-a", "2026-08-10-b"):
        d = _charter_dir(tmp_path, slug=slug)
        main(["queue", str(d), "--root", str(tmp_path / "genjobs")])
    capsys.readouterr()
    main(["status", "--job", "2026-08-10-a", "--root", str(tmp_path / "genjobs")])
    out = capsys.readouterr().out
    assert "2026-08-10-a" in out
    assert "2026-08-10-b" not in out


def test_status_with_unknown_job_names_what_exists(tmp_path):
    d = _charter_dir(tmp_path)
    main(["queue", str(d), "--root", str(tmp_path / "genjobs")])
    with pytest.raises(SystemExit, match="2026-08-10-hidden-knower|no jobs"):
        main(["status", "--job", "nope", "--root", str(tmp_path / "genjobs")])


def test_abandon_marks_the_job_and_persists(tmp_path, capsys):
    d = _charter_dir(tmp_path)
    root = str(tmp_path / "genjobs")
    main(["queue", str(d), "--root", root])
    main(["abandon", "2026-08-10-hidden-knower", "--root", root])
    assert json.loads((d / "state.json").read_text())["status"] == "abandoned"


def test_abandoning_an_unknown_job_names_what_exists(tmp_path):
    _charter_dir(tmp_path)
    with pytest.raises(SystemExit, match="2026-08-10-hidden-knower|no jobs"):
        main(["abandon", "nope", "--root", str(tmp_path / "genjobs")])


def test_board_writes_a_self_contained_page(tmp_path):
    d = _charter_dir(tmp_path)
    root = tmp_path / "genjobs"
    main(["queue", str(d), "--root", str(root)])
    main(["board", "--root", str(root)])
    page = (root / "board.html").read_text()
    assert page.lstrip().startswith("<!doctype html>")
    assert "2026-08-10-hidden-knower" in page


def test_approve_spec_advances_a_parked_job_and_persists(tmp_path, capsys):
    d = _charter_dir(tmp_path)
    root = tmp_path / "genjobs"
    main(["queue", str(d), "--root", str(root)])
    parked = machine.park_for_spec_approval(store.read_state(d), now="2026-08-10T15:00:00-07:00")
    store.write_state(d, parked)
    capsys.readouterr()

    main(["approve", "2026-08-10-hidden-knower", "--spec", "--by", "michael",
          "--root", str(root)])
    out = capsys.readouterr().out
    assert "running" in out

    after = store.read_state(d)
    assert after.status == "running"
    assert after.stage == 3, "stage 2 is what was approved; work resumes at 3"
    assert after.approvals.spec is not None
    assert after.approvals.spec.by == "michael"


def test_approve_release_ships_a_ready_job_and_persists(tmp_path, capsys):
    d = _charter_dir(tmp_path)
    root = tmp_path / "genjobs"
    main(["queue", str(d), "--root", str(root)])
    parked = machine.park_for_release(
        store.read_state(d), decision="READY",
        now="2026-08-10T15:00:00-07:00")
    store.write_state(d, parked)
    capsys.readouterr()

    main(["approve", "2026-08-10-hidden-knower", "--release", "--by", "michael",
          "--root", str(root)])
    out = capsys.readouterr().out
    assert "shipped" in out
    assert store.read_state(d).status == "shipped"


def test_approving_a_job_not_parked_at_the_spec_gate_refuses_cleanly(tmp_path):
    # machine.approve_spec raises TransitionError, a plain Exception -- every
    # other CLI-boundary refusal here is SystemExit with a full sentence
    # (cmd_queue, cmd_abandon, parse_charter). Left uncaught, this would leak
    # a raw traceback instead of the message the machine already wrote.
    d = _charter_dir(tmp_path)
    root = tmp_path / "genjobs"
    main(["queue", str(d), "--root", str(root)])  # status is "queued", not parked

    with pytest.raises(SystemExit, match="awaiting-spec-approval"):
        main(["approve", "2026-08-10-hidden-knower", "--spec", "--by", "michael",
              "--root", str(root)])


def test_approve_requires_exactly_one_of_spec_or_release(tmp_path):
    d = _charter_dir(tmp_path)
    root = tmp_path / "genjobs"
    main(["queue", str(d), "--root", str(root)])
    with pytest.raises(SystemExit):
        main(["approve", "2026-08-10-hidden-knower", "--by", "michael",
              "--root", str(root)])
    with pytest.raises(SystemExit):
        main(["approve", "2026-08-10-hidden-knower", "--spec", "--release",
              "--by", "michael", "--root", str(root)])
