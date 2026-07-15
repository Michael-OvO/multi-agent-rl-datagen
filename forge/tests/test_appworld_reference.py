"""The reference orchestrations, and the claim they let the repo make.

A Harbor task with no passing solution is a task nobody has shown is solvable.
These paths are what makes `solution/solve.sh` real, and the deliverable requires
at least three of them.

They are not replays. The specialists are LLMs and do the actual work; a
reference path supplies only the *decomposition* -- ask `phone` who the roommates
are, then tell `venmo` their names -- which is exactly the thing the Main is
being measured on and exactly the thing it fails to find. That is also why an
oracle here is probabilistic rather than deterministic, which
`WRITEUP.md` says out loud.
"""

import json
from pathlib import Path

import pytest

from forge.appworld.reference import REFERENCE_PATHS, Reference, Step

REPO = Path(__file__).resolve().parents[2]
SPAN = json.loads((REPO / "sweep" / "appworld_span.json").read_text())
BY_ID = {r["task_id"]: r for r in SPAN}


def test_the_deliverable_has_at_least_three_reference_paths():
    assert len(REFERENCE_PATHS) >= 3, (
        "the deliverable requires >= 3 Harbor tasks with a passing solution"
    )


def test_at_least_three_solutions_have_actually_been_run_and_passed():
    """A reference path is a claim. This is the receipt.

    `sweep/appworld_oracle.json` is written by
    `scripts/appworld_oracle_report.py` from real `harbor run --agent oracle`
    jobs, in the containers, against AppWorld's own evaluate(). "Ships a
    solution" and "ships a solution that works" are different sentences, and
    this repo has already published the first while meaning the second.
    """
    evidence = REPO / "sweep" / "appworld_oracle.json"
    assert evidence.exists(), (
        "no oracle evidence -- run `harbor run --agent oracle` and "
        "`python -m scripts.appworld_oracle_report jobs/<job>`"
    )
    rows = json.loads(evidence.read_text())
    passed = [r for r in rows if r["success"]]
    assert len(passed) >= 3, (
        f"only {len(passed)} of {len(rows)} recorded oracle runs reached "
        f"success=True; the deliverable requires >= 3"
    )
    for row in passed:
        assert row["partial"] == 1.0, f"{row['task']} passed but not completely"
        assert row["blocked"] == 0, (
            f"{row['task']}'s reference brief tripped the sandbox -- a reference "
            f"orchestration must never need to leave its app"
        )


@pytest.mark.parametrize("task_id", sorted(REFERENCE_PATHS))
def test_every_reference_path_names_a_measured_task(task_id):
    assert task_id in BY_ID, f"{task_id} is not in the measured span"


@pytest.mark.parametrize("task_id", sorted(REFERENCE_PATHS))
def test_every_step_addresses_a_specialist_the_task_actually_needs(task_id):
    roster = set(BY_ID[task_id]["roster"])
    for step in REFERENCE_PATHS[task_id].steps:
        assert step.specialist in roster, (
            f"{task_id} references {step.specialist!r}, which is not in its "
            f"task-determined roster {sorted(roster)}"
        )


@pytest.mark.parametrize("task_id", sorted(REFERENCE_PATHS))
def test_a_reference_path_crosses_at_least_two_apps(task_id):
    # A single-app reference would prove nothing about orchestration: the whole
    # difficulty is the cross-app fact the Main has to carry itself.
    apps = {s.specialist for s in REFERENCE_PATHS[task_id].steps}
    assert len(apps) >= 2, f"{task_id}'s reference never leaves one app"


@pytest.mark.parametrize("task_id", sorted(REFERENCE_PATHS))
def test_the_first_step_cannot_depend_on_a_previous_report(task_id):
    first = REFERENCE_PATHS[task_id].steps[0]
    assert "{prev}" not in first.brief, "there is no previous report to substitute"


@pytest.mark.parametrize("task_id", sorted(REFERENCE_PATHS))
def test_a_later_step_carries_the_fact_the_main_would_have_to_carry(task_id):
    later = REFERENCE_PATHS[task_id].steps[1:]
    assert any("{prev}" in s.brief for s in later), (
        f"{task_id}'s reference never passes a fact between apps, so it is not "
        f"demonstrating the orchestration the task is about"
    )


def test_render_substitutes_the_previous_report():
    ref = Reference(steps=(
        Step("phone", "who are my roommates?"),
        Step("venmo", "like today's transactions involving: {prev}"),
    ))
    assert ref.steps[1].brief.replace("{prev}", "Ada, Grace") == (
        "like today's transactions involving: Ada, Grace"
    )


def test_an_action_task_answers_completed():
    # Anything else re-introduces the prose-answer bug that capped these at
    # 0.833; see container/server.py's _as_answer.
    for task_id, ref in REFERENCE_PATHS.items():
        assert ref.answer == "completed", (
            f"{task_id} is an action task and must answer 'completed'"
        )
