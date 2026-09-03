"""The rendered grid under tasks/ must be the grid the runtime would render
now. Runnable on a clone without gaia2_data: everything but the world
byte-identity check reads only tracked files.

Fix for every failure here: `python -m forge.gaia2.cli render --all`."""

import json
import re
from pathlib import Path

import pytest

from forge.gaia2.harbor import VERBATIM_COPIES, derive_token, runtime_digest
from forge.gaia2.judge_parse import JUDGE_PARSE_VERSION
from forge.gaia2.runtime import (
    OBJECTIVE_ACTION_CONTRACT,
    OBJECTIVE_ACTION_CONTRACT_VERSION,
)

REPO = Path(__file__).resolve().parents[2]
TASKS = REPO / "tasks"
MANIFEST = TASKS / "MANIFEST.json"
FIX = "re-render with `python -m forge.gaia2.cli render --all`"

_rows = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else []
_ids = [r["name"] for r in _rows]


def test_the_manifest_exists_and_names_the_grid():
    assert MANIFEST.exists(), f"tasks/MANIFEST.json is missing -- {FIX}"
    assert _rows == sorted(_rows, key=lambda r: r["name"]), (
        f"tasks/MANIFEST.json is not sorted by name -- {FIX}")
    assert all(set(r) == {"name", "scenario_id", "config", "soft_judge"} for r in _rows), (
        f"a MANIFEST.json row has keys other than name, scenario_id, config, soft_judge -- {FIX}")
    assert len(_rows) >= 100, (
        f"the grid is 132 cells; a manifest of {len(_rows)} rows is a partial render -- {FIX}")


def test_every_manifest_entry_is_a_task_and_every_gaia2_task_is_an_entry():
    on_disk = {p.name for p in TASKS.glob("gaia2-*") if p.is_dir()}
    assert on_disk == set(_ids), (
        f"tasks/ and MANIFEST.json disagree: only on disk {sorted(on_disk - set(_ids))}, "
        f"only in manifest {sorted(set(_ids) - on_disk)} -- {FIX}")


@pytest.mark.parametrize("name", _ids)
def test_each_task_ships_the_current_runtime(name):
    task = TASKS / name
    for dest, src in VERBATIM_COPIES.items():
        assert (task / dest).read_bytes() == Path(src).read_bytes(), (
            f"{name} ships a stale {dest} -- {FIX}")


@pytest.mark.parametrize("row", _rows, ids=_ids)
def test_each_task_s_provenance_is_current(row):
    task = TASKS / row["name"]
    prov = json.loads((task / "provenance.json").read_text())
    assert prov == {
        "scenario_id": row["scenario_id"],
        "config": row["config"],
        "objective_action_contract": OBJECTIVE_ACTION_CONTRACT_VERSION,
        "judge_parse": JUDGE_PARSE_VERSION,
        "runtime_digest": runtime_digest(),
    }, f"{row['name']} was rendered from an older runtime, contract or parse -- {FIX}"


@pytest.mark.parametrize("row", _rows, ids=_ids)
def test_each_task_s_instruction_carries_the_current_contract(row):
    text = (TASKS / row["name"] / "instruction.md").read_text()
    assert OBJECTIVE_ACTION_CONTRACT in text and OBJECTIVE_ACTION_CONTRACT_VERSION in text, (
        f"{row['name']} briefs the Main under an older contract -- {FIX}")


@pytest.mark.parametrize("row", _rows, ids=_ids)
def test_each_task_s_token_is_the_derived_one(row):
    token = (TASKS / row["name"] / "tests" / "verifier_token.txt").read_text()
    assert token == derive_token(row["scenario_id"], row["config"]), (
        f"{row['name']} carries a token that is not derived from its cell -- {FIX}")


@pytest.mark.parametrize("row", _rows, ids=_ids)
def test_each_task_s_world_is_the_dataset_file(row):
    candidates = list((REPO / "gaia2_data").glob(f"*/{row['scenario_id']}.json"))
    if not candidates:
        pytest.skip("gaia2_data is not fetched (gitignored)")
    shipped = (TASKS / row["name"] / "environment" / "scenario.json").read_bytes()
    assert any(shipped == p.read_bytes() for p in candidates), (
        f"{row['name']} ships a world that differs from the dataset file -- {FIX}")


def test_the_fix_named_here_is_a_command_that_exists():
    src = (REPO / "forge" / "gaia2" / "cli.py").read_text()
    assert re.search(r'"--all"', src), "the render command lost --all"
