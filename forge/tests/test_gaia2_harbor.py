"""Drift guards for rendered Gaia2 tasks, ported from test_appworld_harbor.py.

The defects these exist for are AppWorld's, inherited wholesale: a file
edited in forge/ and not re-rendered ships stale; a copy the renderer emits
but no guard checks is invisible; an instruction that promises a `team` verb
the client does not implement sends the Main into a wall. One Gaia2-specific
guard is new: the scenario file is the entire world, so a shipped
scenario.json that differs from the fetched dataset file is a different
experiment wearing the same task name.
"""

import json
import re
from pathlib import Path

import pytest

from forge.appworld.partition import Constraints, Topology, Visibility
from forge.gaia2.harbor import (
    SIDECAR_APPWORLD_MODULES,
    SIDECAR_GAIA2_MODULES,
    VERBATIM_COPIES,
    render_instruction,
    write_task,
)
from forge.gaia2.runtime import (
    OBJECTIVE_ACTION_CONTRACT,
    OBJECTIVE_ACTION_CONTRACT_VERSION,
)

REPO = Path(__file__).resolve().parents[2]
_SCENARIO = REPO / "gaia2_data" / "mini" / "scenario_universe_30_68r6vs.json"

C = Constraints(roster=("Cabs", "Calendar", "Messages"),
                topology=Topology.STAR, visibility=Visibility.DOCS)


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    if not _SCENARIO.exists():
        pytest.skip("gaia2_data is not fetched (gitignored); rendering needs it")
    out = tmp_path_factory.mktemp("gaia2")
    return write_task(_SCENARIO, "scenario_universe_30_68r6vs", C, out,
                      token="deadbeef")


def test_every_manifest_copy_lands_verbatim(rendered):
    for dest, src in VERBATIM_COPIES.items():
        assert (rendered / dest).read_text() == src.read_text(), dest


def test_the_scenario_ships_byte_identical_to_the_dataset_file(rendered):
    assert (rendered / "environment" / "scenario.json").read_text() \
        == _SCENARIO.read_text()


def test_the_verifier_token_stays_out_of_the_agents_reach(rendered):
    assert (rendered / "tests" / "verifier_token.txt").read_text() == "deadbeef"
    # The agent's image is built from Dockerfile, which copies only `team`.
    dockerfile = (rendered / "environment" / "Dockerfile").read_text()
    copied = re.findall(r"^COPY\s+(\S+)", dockerfile, re.M)
    assert copied == ["team"], copied
    assert "deadbeef" not in (rendered / "environment" / "team").read_text()
    assert "deadbeef" not in (rendered / "instruction.md").read_text()


def test_the_instruction_promises_only_verbs_the_client_implements(rendered):
    team = (rendered / "environment" / "team").read_text()
    m = re.search(r"COMMANDS = \(([^)]*)\)", team)
    assert m, "team no longer declares COMMANDS"
    implemented = set(re.findall(r'"(\w+)"', m.group(1)))
    promised = set(re.findall(r"`team (\w+)",
                              (rendered / "instruction.md").read_text()))
    assert promised <= implemented, promised - implemented


def test_the_compose_defaults_both_roles_to_the_frontier_series(rendered):
    compose = (rendered / "environment" / "docker-compose.yaml").read_text()
    assert 'MAF_MAIN_MODEL: "${MAF_MAIN_MODEL:-gpt-5.6-sol}"' in compose
    assert 'MAF_SUB_MODEL: "${MAF_SUB_MODEL:-gpt-5.6-sol}"' in compose
    # Configurable, defaulted off: the downgrade hatch passes through the
    # compose but carries no default value, so enforcement is the resting state.
    assert 'MAF_ALLOW_SUB_DOWNGRADE: "${MAF_ALLOW_SUB_DOWNGRADE:-}"' in compose


def test_a_names_instruction_does_not_offer_docs():
    names = Constraints(roster=("Cabs", "Calendar"), topology=Topology.STAR,
                        visibility=Visibility.NAMES)
    text = render_instruction(names)
    assert "team docs" not in text.split("## Commands")[0]
    assert "names only" in text


def test_a_finite_economy_target_is_advisory_not_a_task_blocker():
    economy = Constraints(
        roster=("Cabs", "Calendar", "Messages"),
        topology=Topology.STAR,
        visibility=Visibility.DOCS,
        delegation_budget=4,
    )
    text = render_instruction(economy)
    assert "delegation-efficiency target is **4**" in text
    assert "not a hard cap" in text
    assert "at most" not in text


def test_the_shipped_main_gets_the_canonical_objective_action_contract():
    text = render_instruction(C)
    assert OBJECTIVE_ACTION_CONTRACT in text
    assert OBJECTIVE_ACTION_CONTRACT_VERSION in text


def test_the_sidecar_serializes_a_soft_target_and_has_no_exhaustion_path(
    tmp_path,
):
    if not _SCENARIO.exists():
        pytest.skip("gaia2_data is not fetched (gitignored); rendering needs it")
    economy = Constraints(
        roster=("Cabs", "Calendar", "Messages"),
        topology=Topology.STAR,
        visibility=Visibility.DOCS,
        delegation_budget=4,
    )
    task = write_task(
        _SCENARIO,
        "scenario_universe_30_68r6vs",
        economy,
        tmp_path,
        token="deadbeef",
    )
    compose = (task / "environment" / "docker-compose.yaml").read_text()
    server = (task / "environment" / "server.py").read_text()
    assert '"delegation_target": 4' in compose
    assert '"delegation_budget"' not in compose
    assert "delegation budget exhausted" not in server
    assert '"target_is_hard_cap": False' in server


def test_the_solution_claims_nothing_it_cannot_demonstrate(rendered):
    solve = (rendered / "solution" / "solve.sh").read_text()
    assert "exit 1" in solve
    assert "no reference orchestration" in solve


# -- the artifacts under tasks/ must not drift behind the generator --------

_TASKS = sorted((REPO / "tasks").glob("gaia2-*"))


@pytest.mark.skipif(not _TASKS, reason="no rendered gaia2 tasks in the repo")
@pytest.mark.parametrize("task", _TASKS, ids=lambda p: p.name)
@pytest.mark.parametrize("dest", sorted(VERBATIM_COPIES), ids=lambda d: d)
def test_committed_tasks_match_the_generator(task, dest):
    shipped = task / dest
    assert shipped.exists(), (
        f"{task.name} does not ship {dest} -- re-render with "
        f"`python -m forge.gaia2.cli render`")
    assert shipped.read_text() == VERBATIM_COPIES[dest].read_text(), (
        f"{task.name} ships a stale {dest} -- re-render with "
        f"`python -m forge.gaia2.cli render`")


def test_the_sidecar_pin_file_travels_with_every_task():
    """The container installs the same file `.venv-gaia2` installs.

    `forge/tests/test_environment.py` forbids the sidecar from naming a version
    inline, which only helps if the file it installs instead actually arrives in
    the rendered task. Putting it in VERBATIM_COPIES also buys the byte-identity
    guard above for free -- a bumped pin that is not re-rendered fails there.
    """
    assert "environment/requirements.txt" in VERBATIM_COPIES, (
        "the sidecar installs -r requirements.txt but the renderer does not "
        "ship it; every rendered task would fail to build"
    )
    assert VERBATIM_COPIES["environment/requirements.txt"] == (
        REPO / "requirements-gaia2.txt"), (
        "the task's requirements.txt must be the repo's own gaia2 pin file, "
        "not a second copy that can drift from it")


@pytest.mark.skipif(not _TASKS, reason="no rendered gaia2 tasks in the repo")
@pytest.mark.parametrize("task", _TASKS, ids=lambda p: p.name)
def test_committed_tasks_ship_no_module_the_generator_dropped(task):
    for sub, expected in (("maf_gaia2", SIDECAR_GAIA2_MODULES),
                          ("maf_appworld", SIDECAR_APPWORLD_MODULES)):
        shipped = {p.name for p in (task / "environment" / sub).glob("*.py")}
        assert shipped == set(expected), (
            f"{task.name} ships {sorted(shipped)} in {sub} but the renderer "
            f"emits {sorted(expected)}")


@pytest.mark.skipif(not _TASKS, reason="no rendered gaia2 tasks in the repo")
@pytest.mark.parametrize("task", _TASKS, ids=lambda p: p.name)
def test_committed_tasks_carry_a_world_and_a_token(task):
    scenario = task / "environment" / "scenario.json"
    assert scenario.exists() and scenario.stat().st_size > 100_000, (
        f"{task.name} ships no world; its sidecar cannot start")
    token = (task / "tests" / "verifier_token.txt").read_text().strip()
    assert re.fullmatch(r"[0-9a-f]{32}", token), (
        f"{task.name} has a malformed verifier token")


# -- deterministic renders --------------------------------------------------

from forge.gaia2.harbor import (  # noqa: E402
    _put,
    derive_token,
    provenance,
    runtime_digest,
)
from forge.gaia2.judge_parse import JUDGE_PARSE_VERSION  # noqa: E402

FAKE_SCENARIO = '{"scenario_id": "scenario_fake_1", "events": []}\n'


def _fake_scenario(tmp_path):
    p = tmp_path / "scenario_fake_1.json"
    p.write_text(FAKE_SCENARIO)
    return p


def test_the_token_is_a_function_of_cell_and_versions_only():
    a = derive_token("scenario_x", "star-docs-binf")
    assert a == derive_token("scenario_x", "star-docs-binf")
    assert re.fullmatch(r"[0-9a-f]{32}", a)
    assert a != derive_token("scenario_y", "star-docs-binf")
    assert a != derive_token("scenario_x", "star-names-binf")
    seed = (f"scenario_x|star-docs-binf|{OBJECTIVE_ACTION_CONTRACT_VERSION}"
            f"|{JUDGE_PARSE_VERSION}")
    import hashlib
    assert a == hashlib.sha256(seed.encode()).hexdigest()[:32]


def test_the_runtime_digest_covers_every_verbatim_source(monkeypatch, tmp_path):
    before = runtime_digest()
    assert re.fullmatch(r"[0-9a-f]{64}", before)
    assert before == runtime_digest()
    # Change one shipped source and the digest moves.
    dest, src = next(iter(VERBATIM_COPIES.items()))
    fake = tmp_path / "changed.txt"
    fake.write_text(src.read_text() + "\n# changed\n")
    monkeypatch.setitem(VERBATIM_COPIES, dest, fake)
    assert runtime_digest() != before


def test_put_writes_only_when_bytes_differ(tmp_path):
    p = tmp_path / "sub" / "f.txt"
    assert _put(p, "one\n") is True
    stamp = p.stat().st_mtime_ns
    assert _put(p, "one\n") is False
    assert p.stat().st_mtime_ns == stamp
    assert _put(p, "two\n") is True
    assert p.read_text() == "two\n"


def test_a_render_writes_provenance_with_exactly_the_five_keys(tmp_path):
    scen = _fake_scenario(tmp_path)
    task = write_task(scen, "scenario_fake_1", C, tmp_path / "out",
                      token=derive_token("scenario_fake_1", C.label))
    prov = json.loads((task / "provenance.json").read_text())
    assert prov == {
        "scenario_id": "scenario_fake_1",
        "config": C.label,
        "objective_action_contract": OBJECTIVE_ACTION_CONTRACT_VERSION,
        "judge_parse": JUDGE_PARSE_VERSION,
        "runtime_digest": runtime_digest(),
    }
    assert prov == provenance("scenario_fake_1", C)


def test_a_second_render_of_the_same_cell_rewrites_nothing(tmp_path):
    scen = _fake_scenario(tmp_path)
    token = derive_token("scenario_fake_1", C.label)
    task = write_task(scen, "scenario_fake_1", C, tmp_path / "out", token=token)
    stamps = {p: p.stat().st_mtime_ns for p in task.rglob("*") if p.is_file()}
    assert len(stamps) > 10
    write_task(scen, "scenario_fake_1", C, tmp_path / "out", token=token)
    after = {p: p.stat().st_mtime_ns for p in task.rglob("*") if p.is_file()}
    assert after == stamps


def test_a_render_after_a_runtime_change_touches_only_what_changed(tmp_path, monkeypatch):
    scen = _fake_scenario(tmp_path)
    token = derive_token("scenario_fake_1", C.label)
    task = write_task(scen, "scenario_fake_1", C, tmp_path / "out", token=token)
    stamps = {p: p.stat().st_mtime_ns for p in task.rglob("*") if p.is_file()}
    dest = "environment/server.py"
    fake = tmp_path / "server_changed.py"
    fake.write_text(VERBATIM_COPIES[dest].read_text() + "\n# changed\n")
    monkeypatch.setitem(VERBATIM_COPIES, dest, fake)
    write_task(scen, "scenario_fake_1", C, tmp_path / "out", token=token)
    changed = {p.relative_to(task).as_posix()
               for p, t in stamps.items() if p.stat().st_mtime_ns != t}
    assert changed == {"environment/server.py", "provenance.json"}


# -- the grid as rendered -----------------------------------------------------

from forge.gaia2.grid import Cell  # noqa: E402
from forge.gaia2.harbor import render_grid, write_manifest  # noqa: E402


def _cell(tmp_path, sid, constraints, soft):
    p = tmp_path / f"{sid}.json"
    p.write_text(json.dumps({"scenario_id": sid}))
    return Cell(sid, p, None, constraints, soft, 4)


def test_the_manifest_lists_every_cell_sorted_by_name(tmp_path):
    names = Constraints(roster=("Cabs", "Calendar"), topology=Topology.STAR,
                        visibility=Visibility.NAMES)
    grid = [_cell(tmp_path, "scenario_b", C, True), _cell(tmp_path, "scenario_a", names, False)]
    p = write_manifest(grid, tmp_path / "out")
    assert p == tmp_path / "out" / "MANIFEST.json"
    rows = json.loads(p.read_text())
    assert rows == [
        {"name": "gaia2-star-docs-binf-scenario_b", "scenario_id": "scenario_b",
         "config": "star-docs-binf", "soft_judge": True},
        {"name": "gaia2-star-names-binf-scenario_a", "scenario_id": "scenario_a",
         "config": "star-names-binf", "soft_judge": False},
    ]
    assert p.read_text().endswith("\n")


def test_render_grid_renders_each_cell_with_its_derived_token_and_the_manifest(tmp_path):
    grid = [_cell(tmp_path, "scenario_a", C, True)]
    dirs = render_grid(grid, tmp_path / "out")
    assert dirs == [tmp_path / "out" / "gaia2-star-docs-binf-scenario_a"]
    token = (dirs[0] / "tests" / "verifier_token.txt").read_text()
    assert token == derive_token("scenario_a", "star-docs-binf")
    assert (tmp_path / "out" / "MANIFEST.json").exists()
