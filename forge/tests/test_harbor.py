import json
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
