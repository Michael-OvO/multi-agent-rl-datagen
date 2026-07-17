import json
from pathlib import Path

import pytest
import tomllib

from forge.maf.dimensions.scheduling import DIM
from forge.maf.harbor import write_task
from forge.maf.leak_audit import audit


def test_write_task_produces_valid_tree(tmp_path):
    inst = DIM.generate(2, {"n": 5, "k": 2, "trap": True})
    d = write_task(DIM, inst, tmp_path, "0001")
    assert (d / "task.toml").exists()
    tomllib.loads((d / "task.toml").read_text())  # parses
    assert (d / "instruction.md").read_text().strip()
    assert (d / "environment" / "task.json").exists()
    assert (d / "environment" / "Dockerfile").exists()
    assert (d / "tests" / "lib" / "maf_core.py").exists()
    assert (d / "tests" / "lib" / "maf_dim.py").exists()
    assert (d / "solution" / "solve.sh").exists()
    assert (d / "tests" / "verify.py").exists()
    assert (d / "tests" / "ground_truth.json").exists()


def test_agent_image_hides_ground_truth_and_grader(tmp_path):
    # `assert audit(d) == []` alone is not enough, and this test is why the
    # rule exists: it once WAS only that line, delegating the whole claim in
    # its name to a detector no test could prove would ever fire (verified in
    # the final review -- disabling _ground_truth_keys() left this test
    # green). audit() is now pinned by its own red-verified tests in
    # test_leak_audit.py, but this test states its claim directly too: a
    # detector and a spot-check of the actual bytes fail independently.
    inst = DIM.generate(2, {"n": 5, "k": 2, "trap": True})
    d = write_task(DIM, inst, tmp_path, "0001")

    shipped = (d / "environment" / "task.json").read_text()
    assert "_planted" not in shipped
    assert "_opt_makespan" not in shipped
    # The ground truth exists -- it just lives in tests/, which Harbor uploads
    # only at verification time. Without this, the assertions above would also
    # pass if generate() had simply stopped planting anything.
    gt = json.loads((d / "tests" / "ground_truth.json").read_text())
    assert "_planted" in gt and "_opt_makespan" in gt

    assert audit(d) == []


def test_dimension_module_ships_to_tests_not_environment(tmp_path):
    inst = DIM.generate(2, {"n": 5, "k": 2, "trap": True})
    d = write_task(DIM, inst, tmp_path, "0001")
    assert (d / "tests" / "lib" / "maf_dim.py").exists()
    assert not (d / "environment" / "lib").exists()


def test_copied_module_has_no_package_imports(tmp_path):
    inst = DIM.generate(2, {"n": 5, "k": 2, "trap": True})
    d = write_task(DIM, inst, tmp_path, "0001")
    src = (d / "tests" / "lib" / "maf_dim.py").read_text()
    assert "from forge.maf.core" not in src
    assert "from maf_core import" in src


def test_embedded_oracle_solution_verifies(tmp_path):
    # The planted schedule embedded in solve.sh must score 1.0 through verify().
    inst = DIM.generate(2, {"n": 5, "k": 2, "trap": True})
    d = write_task(DIM, inst, tmp_path, "0001")
    solve = (d / "solution" / "solve.sh").read_text()
    start = solve.index("[")
    end = solve.rindex("]") + 1
    schedule = json.loads(solve[start:end])
    assert DIM.verify(inst, schedule).reward == 1.0


# -- the committed v1 task must not drift behind its generator ---------------


def test_the_committed_scheduling_task_matches_its_generator(tmp_path):
    """`tasks/parallel-scheduling-0003` is committed; nothing was checking it.

    `test_appworld_harbor.py` guards the appworld artifacts for exactly this
    reason, and its docstring records the burn: "a fix landed in forge/ and
    never reached the artifacts anyone would run". The v1 task had no such
    guard, which is how it kept shipping `scenario_path: /app/task.json` -- an
    agent-writable grading input, reward 1.0 for a forged problem -- while
    `_write_static` was the thing anyone would have read.

    The suffix is the seed (`forge_cli.gen`: f"{seed:04d}"), and generation is
    deterministic, so re-rendering seed 3 at the default difficulty must
    reproduce the committed tree byte for byte.
    """
    repo = Path(__file__).resolve().parents[2]
    committed = repo / "tasks" / "parallel-scheduling-0003"
    if not committed.exists():
        pytest.skip("no committed parallel-scheduling task")

    inst = DIM.generate(3, DIM.DIFFICULTY_PRESETS["medium"])
    fresh = write_task(DIM, inst, tmp_path, "0003")

    for rel in ("tests/verify_config.json", "tests/scenario.json",
                "tests/ground_truth.json", "environment/task.json",
                "environment/Dockerfile", "tests/verify.py",
                "tests/lib/maf_core.py", "tests/lib/maf_dim.py"):
        assert (committed / rel).exists(), f"the committed task lacks {rel}"
        assert (committed / rel).read_text() == (fresh / rel).read_text(), (
            f"tasks/parallel-scheduling-0003 ships a stale {rel} -- re-render "
            f"with `python -m forge.forge_cli gen --dim parallel-scheduling "
            f"--seed 3 --n 1 --out tasks`"
        )


def test_the_committed_scheduling_task_grades_from_a_path_the_agent_cannot_write():
    """The property, asserted on the artifact rather than on a fresh render.

    test_adversarial.py proves the renderer is fixed. This proves the thing in
    the repository is -- the two are different claims, and the gap between them
    is what this file's new guard exists to close.
    """
    repo = Path(__file__).resolve().parents[2]
    committed = repo / "tasks" / "parallel-scheduling-0003"
    if not committed.exists():
        pytest.skip("no committed parallel-scheduling task")

    cfg = json.loads((committed / "tests" / "verify_config.json").read_text())
    assert cfg["scenario_path"].startswith("/tests/")
    assert cfg["ground_truth_path"].startswith("/tests/")
