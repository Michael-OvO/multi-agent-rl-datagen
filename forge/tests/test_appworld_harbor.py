"""What gets rendered into a Harbor task, and what must never be.

`forge/appworld/harbor.py` had no tests. Two defects lived in that gap:

  * the sidecar imported a module the renderer did not copy, which is only
    discoverable at container start -- long after `pytest` is green;
  * the committed tasks under `tasks/` drifted behind the generator, so a fix
    landed in `forge/` (the answer-type conversion, which was capping every
    action task at 0.833) and never reached the artifacts anyone would run.

Both are the same shape: the thing under test is a *file tree*, and nothing was
looking at it. These tests look at it.
"""

import ast
import json
import os
import subprocess
from pathlib import Path

import pytest

from forge.appworld.harbor import (
    SIDECAR_MODULES,
    VERBATIM_COPIES,
    write_task,
)
from forge.appworld.partition import Constraints, Topology, Visibility
from forge.appworld.reference import REFERENCE_PATHS

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "forge" / "appworld"
CONTAINER = SOURCE / "container"

C = Constraints(roster=("phone", "venmo"), topology=Topology.STAR,
                visibility=Visibility.DOCS)


@pytest.fixture
def rendered(tmp_path):
    return write_task("2a163ab_1", "Like every transaction from today.", C,
                      tmp_path, token="deadbeef")


def _forge_imports(path: Path) -> set[str]:
    """Which `forge.appworld.<module>` names a file imports."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "forge.appworld"):
            parts = node.module.split(".")
            if len(parts) >= 3:
                found.add(parts[2])
    return found


# -- the sidecar must be able to start -------------------------------------


def test_the_sidecar_ships_every_forge_module_it_imports(rendered):
    pkg = rendered / "environment" / "maf_appworld"
    shipped = {p.stem for p in pkg.glob("*.py")}

    needed: set[str] = set()
    for src in [*pkg.glob("*.py"), rendered / "environment" / "server.py"]:
        needed |= _forge_imports(src)

    missing = needed - shipped
    assert not missing, (
        f"the sidecar imports {sorted(missing)} but the renderer does not copy "
        f"them; the container would crash on start, and no unit test would say so"
    )


def test_the_sandbox_reaches_the_sidecar(rendered):
    # Named explicitly: without it the specialist's app boundary silently
    # reverts to being a sentence in a system prompt.
    assert (rendered / "environment" / "maf_appworld" / "sandbox.py").exists()


def test_the_sidecar_pins_what_it_installs(rendered):
    # An unpinned `pip install appworld openai` means a task rendered today and
    # a task rebuilt in six months are different experiments wearing the same
    # task id -- and every number in WRITEUP.md is attributed to the wrong
    # thing. The dataset is a known remaining gap; see the Dockerfile.
    text = (rendered / "environment" / "Dockerfile.sidecar").read_text()
    for pkg in ("appworld", "openai"):
        assert f"{pkg}==" in text, f"{pkg} is unpinned; the sidecar is not reproducible"


# -- the boundary the whole design rests on --------------------------------


def test_the_agent_image_never_copies_the_sidecar(rendered):
    dockerfile = (rendered / "environment" / "Dockerfile").read_text()
    assert "maf_appworld" not in dockerfile, "that is AppWorld in the Main's image"
    assert "server.py" not in dockerfile
    assert "COPY team" in dockerfile, "the Main gets the HTTP client and nothing else"


def test_the_verifier_token_stays_out_of_the_agents_reach(rendered):
    assert (rendered / "tests" / "verifier_token.txt").read_text() == "deadbeef"
    env = rendered / "environment"
    for path in env.rglob("*"):
        if path.is_file():
            assert "deadbeef" not in path.read_text(errors="ignore") or \
                path.name == "docker-compose.yaml", (
                    f"{path.name} carries the token into the build context")


# -- the solution must actually orchestrate --------------------------------
#
# These run the generated solve.sh for real, against a fake `team` on PATH. No
# Docker, no API key, no specialists -- but the script, the argument passing and
# the {prev} substitution are the real ones. What is left untested here is
# whether the specialists do good work, which is what the container run in
# WRITEUP.md §5 is for.


FAKE_TEAM = '''#!/usr/bin/env python3
import json, pathlib, sys
pathlib.Path(__file__).with_name("calls.jsonl").open("a").write(
    json.dumps(sys.argv[1:]) + "\\n")
print(json.dumps({"report": "Ada Lovelace, Grace Hopper"}
                 if sys.argv[1] == "ask" else {"ok": True}))
'''


@pytest.fixture
def fake_team(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    team = bindir / "team"
    team.write_text(FAKE_TEAM)
    team.chmod(0o755)
    return bindir


def _run_solution(task_dir, bindir):
    return subprocess.run(
        ["bash", str(task_dir / "solution" / "solve.sh")],
        env={**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"},
        capture_output=True, text=True,
    )


def _calls(bindir):
    log = bindir / "calls.jsonl"
    return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []


def test_a_task_with_a_reference_gets_a_solution_that_runs(tmp_path, fake_team):
    d = write_task("2a163ab_1", "Like today's transactions.", C, tmp_path,
                   token="t", reference=REFERENCE_PATHS["2a163ab_1"])
    result = _run_solution(d, fake_team)
    assert result.returncode == 0, f"the oracle failed: {result.stderr}"


def test_the_solution_delegates_in_order_and_carries_the_fact(tmp_path, fake_team):
    d = write_task("2a163ab_1", "Like today's transactions.", C, tmp_path,
                   token="t", reference=REFERENCE_PATHS["2a163ab_1"])
    _run_solution(d, fake_team)
    calls = _calls(fake_team)

    assert [c[:2] for c in calls[:2]] == [["ask", "phone"], ["ask", "venmo"]], \
        "the reference must ask the app that knows the names before the app that needs them"
    assert "Ada Lovelace, Grace Hopper" in calls[1][2], \
        "{prev} must carry phone's report into venmo's brief -- that is the whole task"
    assert calls[-1] == ["done", "completed"], \
        "an action task answering prose is capped at 0.833"


def test_the_solution_never_touches_an_app_itself(tmp_path, fake_team):
    d = write_task("2a163ab_1", "x", C, tmp_path, token="t",
                   reference=REFERENCE_PATHS["2a163ab_1"])
    solve = (d / "solution" / "solve.sh").read_text()
    assert "apis." not in solve, "the oracle is an orchestration, not an API script"
    # An oracle that reads the scorer proves the scorer works, not the task.
    assert "/state" not in solve
    assert "verifier_token" not in solve
    assert "MAF_VERIFIER_TOKEN" not in solve


def test_a_task_without_a_reference_fails_loudly(tmp_path, fake_team):
    d = write_task("9999999_9", "unknown task", C, tmp_path, token="t")
    result = _run_solution(d, fake_team)
    assert result.returncode != 0, "no reference means no demonstrated solution"
    assert "no reference" in result.stderr.lower()
    assert _calls(fake_team) == [], "it must not half-run and look like a solve"


def test_the_reference_decomposition_lives_only_in_the_solution(tmp_path):
    # The decomposition IS the task. Anything that hands it to the Main -- the
    # instruction, or any file in the build context -- answers the question the
    # Main is being asked. Matched on the exact brief rather than a keyword:
    # `runtime.py` legitimately says "roommates" in its docstring, and it belongs
    # to the sidecar, which the Main's image does not copy.
    ref = REFERENCE_PATHS["2a163ab_1"]
    d = write_task("2a163ab_1", "Like today's transactions.", C, tmp_path,
                   token="t", reference=ref)
    brief = ref.steps[0].brief

    assert brief in (d / "solution" / "solve.sh").read_text(), "sanity"
    for path in [d / "instruction.md", *(d / "environment").rglob("*")]:
        if path.is_file():
            assert brief not in path.read_text(errors="ignore"), \
                f"{path.name} hands the Main the decomposition it must find"


def test_render_attaches_the_reference_to_every_task_that_has_one(tmp_path):
    from forge.appworld.cli import main

    main(["render", "--n", str(len(REFERENCE_PATHS)),
          "--span", str(REPO / "sweep" / "appworld_span.json"),
          "--out", str(tmp_path)])

    rendered = sorted(tmp_path.glob("appworld-*"))
    assert rendered, "render produced nothing"
    for task in rendered:
        solve = (task / "solution" / "solve.sh").read_text()
        assert "no reference orchestration" not in solve, (
            f"{task.name} rendered without its reference, so it ships no solution"
        )


# -- the artifacts under tasks/ must not drift behind the generator --------

_TASKS = sorted((REPO / "tasks").glob("appworld-*"))


@pytest.mark.skipif(not _TASKS, reason="no rendered appworld tasks in the repo")
@pytest.mark.parametrize("task", _TASKS, ids=lambda p: p.name)
@pytest.mark.parametrize("dest", sorted(VERBATIM_COPIES), ids=lambda d: d)
def test_committed_tasks_match_the_generator(task, dest):
    """A committed task running old code is a task measuring the old bug.

    Driven off `harbor.VERBATIM_COPIES`, not a list kept here by hand. The hand
    list is what failed: the renderer copied five things and this guard checked
    three, so a stale `verify.py` -- the code that computes the reward -- and a
    stale `Dockerfile.sidecar` both shipped silently. Verified 2026-07-17 by
    appending a line to each and watching the suite stay green.

    Reading the manifest means a copy added to the renderer is guarded the day
    it is added, rather than the day someone remembers this file.
    """
    shipped = task / dest
    assert shipped.exists(), (
        f"{task.name} does not ship {dest}, which the renderer copies -- "
        f"re-render with `python -m forge.appworld.cli render`"
    )
    assert shipped.read_text() == VERBATIM_COPIES[dest].read_text(), (
        f"{task.name} ships a stale {dest} -- re-render with "
        f"`python -m forge.appworld.cli render`"
    )


@pytest.mark.skipif(not _TASKS, reason="no rendered appworld tasks in the repo")
@pytest.mark.parametrize("task", _TASKS, ids=lambda p: p.name)
def test_committed_tasks_ship_no_module_the_generator_dropped(task):
    """The other direction: a file the renderer stopped copying, still shipped.

    The old guard globbed the *shipped* package, so it could only ever compare
    files that were there -- a module the renderer no longer emits would sit in
    `tasks/` forever, and a module it newly emits would be missing with nothing
    to say so. Both directions are drift.
    """
    shipped = {p.name for p in (task / "environment" / "maf_appworld").glob("*.py")}
    assert shipped == set(SIDECAR_MODULES), (
        f"{task.name} ships {sorted(shipped)} but the renderer emits "
        f"{sorted(SIDECAR_MODULES)}"
    )
