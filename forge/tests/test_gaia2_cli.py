"""The render command: one scenario's four cells, or the whole grid."""

import json
from types import SimpleNamespace

import pytest

from forge.gaia2 import cli, grid
from forge.gaia2.harbor import derive_token


def _span(scenario, target=3):
    return SimpleNamespace(usable=True, seamful=True, reply_conditioned=False,
                           roster_blind=(), roster=("Cabs", "Calendar", "Messages"),
                           delegation_target=target,
                           scenario_id=scenario["scenario_id"])


@pytest.fixture
def world(tmp_path, monkeypatch):
    (tmp_path / "sweep").mkdir()
    (tmp_path / "sweep" / "gaia2_cells.json").write_text(json.dumps(
        [{"scenario_id": "scenario_a"}]))
    (tmp_path / "sweep" / "gaia2_cells_adaptability.json").write_text("[]")
    (tmp_path / "gaia2_data" / "mini").mkdir(parents=True)
    (tmp_path / "gaia2_data" / "mini" / "scenario_a.json").write_text(
        json.dumps({"scenario_id": "scenario_a"}))
    monkeypatch.setattr(grid, "admit", _span)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    return tmp_path


def test_render_scenario_writes_the_four_grid_cells_with_derived_tokens(world, capsys):
    cli.main(["render", "--scenario", str(world / "gaia2_data" / "mini" / "scenario_a.json"),
              "--out", str(world / "tasks")])
    names = sorted(p.name for p in (world / "tasks").glob("gaia2-*"))
    assert names == ["gaia2-open-docs-binf-scenario_a", "gaia2-star-docs-b3-scenario_a",
                     "gaia2-star-docs-binf-scenario_a", "gaia2-star-names-binf-scenario_a"]
    tok = (world / "tasks" / "gaia2-star-docs-b3-scenario_a" / "tests" / "verifier_token.txt").read_text()
    assert tok == derive_token("scenario_a", "star-docs-b3")
    assert not (world / "tasks" / "MANIFEST.json").exists(), "one scenario is not the grid"
    out = capsys.readouterr().out
    assert "gaia2-open-docs-binf-scenario_a" in out


def test_render_all_writes_the_grid_and_the_manifest(world):
    cli.main(["render", "--all", "--out", str(world / "tasks")])
    rows = json.loads((world / "tasks" / "MANIFEST.json").read_text())
    assert [r["name"] for r in rows] == [
        "gaia2-open-docs-binf-scenario_a", "gaia2-star-docs-b3-scenario_a",
        "gaia2-star-docs-binf-scenario_a", "gaia2-star-names-binf-scenario_a"]
    assert all((world / "tasks" / r["name"] / "provenance.json").exists() for r in rows)


def test_render_all_honours_the_economy_target(world):
    cli.main(["render", "--all", "--out", str(world / "tasks"), "--economy-target", "7"])
    assert (world / "tasks" / "gaia2-star-docs-b7-scenario_a").exists()


def test_render_refuses_a_scenario_that_is_not_admitted(world, monkeypatch):
    monkeypatch.setattr(grid, "admit", lambda s: SimpleNamespace(
        usable=False, seamful=False, reply_conditioned=False, roster_blind=(),
        roster=(), delegation_target=1, scenario_id="scenario_a"))
    with pytest.raises(SystemExit):
        cli.main(["render", "--scenario", str(world / "gaia2_data" / "mini" / "scenario_a.json"),
                  "--out", str(world / "tasks")])


def test_scenario_and_all_are_exclusive(world):
    with pytest.raises(SystemExit):
        cli.main(["render", "--all", "--scenario", "x.json"])
