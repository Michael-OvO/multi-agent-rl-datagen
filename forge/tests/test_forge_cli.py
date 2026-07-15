import json
import subprocess
import sys

import pytest

from forge.forge_cli import QUARANTINED, main


def _run(*args, cwd="."):
    return subprocess.run(
        [sys.executable, "-m", "forge.forge_cli", *args],
        capture_output=True, text=True, cwd=cwd,
    )


def test_cli_ships_only_passing_tasks(tmp_path):
    out = tmp_path / "tasks"
    r = _run("gen", "--dim", "parallel-scheduling", "--seed", "0", "--n", "3",
             "--difficulty", "medium", "--out", str(out))
    assert r.returncode == 0, r.stderr
    summary = json.loads(r.stdout)
    assert summary["shipped"] >= 1
    dirs = list(out.glob("parallel-scheduling-*"))
    assert len(dirs) == summary["shipped"]
    for d in dirs:
        assert (d / "task.toml").exists()


def test_cli_rejects_unknown_dimension(tmp_path):
    r = _run("gen", "--dim", "nope", "--out", str(tmp_path))
    assert r.returncode != 0


def test_quarantined_dimension_cannot_be_rendered(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["gen", "--dim", "theory-of-mind", "--out", str(tmp_path)])
    assert exc.value.code != 0
    assert not list(tmp_path.iterdir())


def test_quarantine_names_the_reason():
    assert "theory-of-mind" in QUARANTINED
    assert "failure-recovery" in QUARANTINED
    for reason in QUARANTINED.values():
        assert "sidecar" in reason.lower()
