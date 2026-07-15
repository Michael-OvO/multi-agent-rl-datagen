"""Regression tests for exploits executed against the shipped tasks on 2026-07-14.

Exploits 1, 3, and 4 scored reward 1.0 on parallel-scheduling or on the
interactive dimensions. They are structural now -- the files are gone -- so
these tests assert absence from the agent image.

Exploit 2 (forging the graded artifact) does NOT apply to parallel-scheduling:
its submission is a schedule the verifier independently re-executes, so
"forging" it means solving the problem. Exploit 2 is interactive-only and its
regression test lands in Plan 2 with the sidecar. It is named here so the gap
is explicit rather than silently absent.
"""

import json

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
