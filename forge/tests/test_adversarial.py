"""Regression tests for exploits executed against the shipped tasks on 2026-07-14.

Exploits 1, 3, and 4 scored reward 1.0 on parallel-scheduling or on the
interactive dimensions. They are structural now -- the files are gone -- so
these tests assert absence from the agent image.

Exploit 2 is the interesting one, and this docstring used to get it wrong. It
said:

    Exploit 2 (forging the graded artifact) does NOT apply to
    parallel-scheduling: its submission is a schedule the verifier
    independently re-executes, so "forging" it means solving the problem.

Every clause of that is true and the conclusion was false. The verifier does
re-execute the schedule -- against the scenario at `scenario_path`, which was
`/app/task.json`, which is the agent's own WORKDIR. So forging the *artifact*
did mean solving the problem, and nobody had to forge the artifact: you forge
the **problem** and submit an honest schedule for it. Measured 2026-07-17,
reward 1.0 on a makespan of 7 against the real optimum of 10.

The lesson is the repository's own. The claim was argued rather than tested --
"exploit 2 does not apply" was a paragraph, not an assertion -- and it sat above
five tests that all passed, in a suite whose subject is gates that measure
nothing. It is tested now, both structurally and by replaying the attack.
"""

import json
from pathlib import Path

from forge.maf.dimensions.scheduling import DIM
from forge.maf.harbor import write_task
from forge.maf.leak_audit import image_files


def _task(tmp_path):
    inst = DIM.generate(3, {"n": 6, "k": 2, "trap": True})
    return inst, write_task(DIM, inst, tmp_path, "0001")


def _json_keys(path):
    if path.suffix != ".json":
        return []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return []
    return list(data) if isinstance(data, dict) else []


def test_exploit1_ground_truth_absent_from_agent_image(tmp_path):
    # Attack: cat the scenario out of the image to read the answer.
    _, d = _task(tmp_path)
    for f in image_files(d):
        leaked = [k for k in _json_keys(f) if k.startswith("_")]
        assert not leaked, f"{f.name} leaks {leaked}"


def test_exploit3_oracle_absent_from_agent_image(tmp_path):
    # Attack: import maf_dim from /app/lib and run the shipped ORACLE.
    _, d = _task(tmp_path)
    for f in image_files(d):
        assert "ORACLE" not in f.read_text(errors="ignore"), f"{f.name} ships the oracle"


def test_exploit4_generator_absent_from_agent_image(tmp_path):
    # Attack: brute-force the seed against the shipped generate() until the
    # public fields match, then read the private ones out of the regenerated
    # instance. Recovered _planted at seed=3 and scored 1.0.
    _, d = _task(tmp_path)
    for f in image_files(d):
        assert "def generate(" not in f.read_text(errors="ignore"), (
            f"{f.name} ships the generator; seed brute-force defeats /tests isolation"
        )


def test_exploit2_the_verifier_reads_the_scenario_from_a_path_the_agent_cannot_write(
        tmp_path):
    """Attack: don't forge the schedule, forge the *problem*.

    The docstring above used to say exploit 2 did not apply here, because "its
    submission is a schedule the verifier independently re-executes, so forging
    it means solving the problem". The re-execution is real; the argument still
    failed, because `scenario_path` was `/app/task.json` and `/app` is the
    agent's own WORKDIR. The verifier re-executed the submission against
    whatever problem the agent had written there, then scored the resulting
    makespan against the *real* `_opt_makespan` from `/tests`. Measured
    2026-07-17: reward 1.0 with makespan 7 against opt 10, for a schedule of one
    invented subtask.

    Neither gate could see it. `selfcheck`'s C4 fuzzes the submission and always
    hands `verify()` a trusted instance; `leak_audit` inspects the image, where
    task.json legitimately belongs. Every check was green.

    So the property is structural: the verifier's scenario must live under
    /tests, which Harbor uploads only at verification time.
    """
    _, d = _task(tmp_path)
    cfg = json.loads((d / "tests" / "verify_config.json").read_text())

    assert cfg["scenario_path"].startswith("/tests/"), (
        f"the verifier reads its scenario from {cfg['scenario_path']!r}, which "
        f"the agent can rewrite; forge the problem and any schedule wins"
    )
    assert (d / "tests" / "scenario.json").exists(), (
        "verify_config points into /tests but the renderer shipped no scenario there"
    )


def test_exploit2_a_tampered_scenario_no_longer_pays(tmp_path):
    """The regression, run as the attack rather than asserted structurally.

    The path check above would pass if `scenario.json` were shipped but empty.
    This one replays the exploit end to end: rewrite the agent-visible problem
    into a trivial one, submit a schedule that is optimal *for that* problem,
    and grade exactly as `runtime/verify_entry.py` does.
    """
    inst, d = _task(tmp_path)
    cfg = json.loads((d / "tests" / "verify_config.json").read_text())

    # The agent rewrites its own copy of the problem into a triviality.
    trivial = {"workers": {"w0": ["code"]},
               "subtasks": {"t000": {"skill": "code", "dur": 1, "deps": []}}}
    (d / "environment" / "task.json").write_text(json.dumps(trivial))

    # verify_entry._grade(), verbatim: scenario, then the ground-truth overlay.
    scenario = json.loads(Path(cfg["scenario_path"].replace("/tests", str(d / "tests")))
                          .read_text())
    scenario.update(json.loads((d / "tests" / "ground_truth.json").read_text()))
    forged = [{"subtask": "t000", "worker": "w0", "start": 0}]

    assert DIM.verify(scenario, forged).reward == 0.0, (
        "a schedule for a problem the agent invented still scores; the verifier "
        "is reading the agent's scenario"
    )


def test_the_agent_still_gets_to_read_its_own_task(tmp_path):
    """The fix must not take the problem away from the agent.

    /tests is the verifier's copy. The agent's copy stays in the image, and the
    two must agree -- a task whose statement differs from what it is graded on
    is unsolvable rather than secure.
    """
    _, d = _task(tmp_path)
    agent_copy = json.loads((d / "environment" / "task.json").read_text())
    graded_copy = json.loads((d / "tests" / "scenario.json").read_text())
    assert agent_copy == graded_copy
    assert not [k for k in graded_copy if k.startswith("_")], (
        "the verifier's scenario carries ground-truth fields; /tests is not a "
        "reason to stop stripping them"
    )


def test_incomplete_schedule_scores_zero(tmp_path):
    # Not exploit 2 -- see module docstring. This pins the completeness gate:
    # a submission that does not schedule every subtask is invalid regardless
    # of makespan (_check_schedule's `set(seen) != set(subs)`).
    #
    # The id and worker are derived from the instance, never hardcoded. An
    # earlier draft used a literal "t0", which generate() never emits, so
    # _check_schedule rejected it on the *unknown-subtask-id* branch and the
    # test passed without ever reaching the completeness check it names.
    # Hardcoding any id re-arms that trap the moment the id scheme changes.
    inst, _ = _task(tmp_path)
    assert len(inst["subtasks"]) > 1, "fixture must be partial-schedulable"
    tid = sorted(inst["subtasks"])[0]
    worker = next(
        w for w, skills in inst["workers"].items()
        if inst["subtasks"][tid]["skill"] in skills
    )
    partial = [{"subtask": tid, "worker": worker, "start": 0}]
    assert DIM.verify(inst, partial).reward == 0.0


def test_empty_submission_scores_zero(tmp_path):
    inst, _ = _task(tmp_path)
    assert DIM.verify(inst, []).reward == 0.0
