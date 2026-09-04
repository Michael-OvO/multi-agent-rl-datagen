"""The campaign grid, defined once. The campaign, the render command and the
drift guard all read it from here, so they cannot disagree about which cells
exist."""

import json
from pathlib import Path
from types import SimpleNamespace

from forge.abilities import Ability
from forge.gaia2 import grid
from forge.gaia2.grid import GRID, Cell, cells, cells_for, eligible, scenario_paths


def span(usable=True, seamful=True, reply_conditioned=False, roster_blind=(),
         roster=("Cabs", "Calendar", "Messages"), delegation_target=6,
         scenario_id="scenario_a"):
    return SimpleNamespace(usable=usable, seamful=seamful,
                           reply_conditioned=reply_conditioned,
                           roster_blind=roster_blind, roster=roster,
                           delegation_target=delegation_target,
                           scenario_id=scenario_id)


def _root(tmp_path: Path, sids_mini=("scenario_a",), sids_adapt=("scenario_b",),
          fetched=("scenario_a", "scenario_b")) -> Path:
    (tmp_path / "sweep").mkdir()
    (tmp_path / "sweep" / "gaia2_cells.json").write_text(json.dumps(
        [{"scenario_id": s, "config": "open-docs-binf"} for s in sids_mini]))
    (tmp_path / "sweep" / "gaia2_cells_adaptability.json").write_text(json.dumps(
        [{"scenario_id": s, "config": "open-docs-binf"} for s in sids_adapt]))
    for split, sids in (("mini", sids_mini), ("adaptability", sids_adapt)):
        (tmp_path / "gaia2_data" / split).mkdir(parents=True)
        for s in sids:
            if s in fetched:
                (tmp_path / "gaia2_data" / split / f"{s}.json").write_text(
                    json.dumps({"scenario_id": s}))
    return tmp_path


def test_the_grid_is_the_control_and_the_three_abilities():
    assert GRID == (None, Ability.DISCOVERY, Ability.CONTEXT_TRANSFER,
                    Ability.DELEGATION_ECONOMY)


def test_eligible_keeps_the_campaign_s_rules():
    assert not eligible(span(usable=False), scripted_only=False)
    assert not eligible(span(seamful=False), scripted_only=True)
    assert eligible(span(reply_conditioned=True), scripted_only=False)
    assert not eligible(span(reply_conditioned=True), scripted_only=True)
    assert not eligible(span(roster_blind=(("Emails", "send_email", "x"),)),
                        scripted_only=False)


def test_scenario_paths_prefers_mini_and_skips_unfetched(tmp_path):
    root = _root(tmp_path, sids_mini=("scenario_a",),
                 sids_adapt=("scenario_a", "scenario_b", "scenario_c"),
                 fetched=("scenario_a", "scenario_b"))
    paths = scenario_paths(root)
    assert set(paths) == {"scenario_a", "scenario_b"}
    assert paths["scenario_a"].parent.name == "mini"
    assert paths["scenario_b"].parent.name == "adaptability"


def test_cells_for_yields_four_cells_with_the_scenario_s_target(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setattr(grid, "admit", lambda scenario: span(
        scenario_id=scenario["scenario_id"], delegation_target=5,
        reply_conditioned=True))
    out = cells_for(root / "gaia2_data" / "mini" / "scenario_a.json")
    assert [c.ability for c in out] == list(GRID)
    assert [c.constraints.label for c in out] == [
        "open-docs-binf", "star-names-binf", "star-docs-binf", "star-docs-b5"]
    assert all(c.scenario_id == "scenario_a" and c.soft_judge for c in out)
    assert all(c.economy_target == 5 for c in out)
    assert out[3].task_name == "gaia2-star-docs-b5-scenario_a"
    assert isinstance(out[0], Cell)


def test_cells_for_returns_nothing_for_an_inadmissible_scenario(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setattr(grid, "admit", lambda scenario: span(seamful=False))
    assert cells_for(root / "gaia2_data" / "mini" / "scenario_a.json") == []


def test_economy_target_override_and_offset(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setattr(grid, "admit", lambda scenario: span(delegation_target=6))
    p = root / "gaia2_data" / "mini" / "scenario_a.json"
    assert cells_for(p, economy_target=2)[3].constraints.label == "star-docs-b2"
    assert cells_for(p, economy_target_offset=-10)[3].constraints.label == "star-docs-b1"
    assert cells_for(p, economy_target_offset=1)[3].constraints.label == "star-docs-b7"


def test_cells_walks_every_fetched_scenario_in_id_order(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setattr(grid, "admit", lambda scenario: span(
        scenario_id=scenario["scenario_id"],
        reply_conditioned=scenario["scenario_id"] == "scenario_b"))
    out = cells(root)
    assert [c.scenario_id for c in out] == ["scenario_a"] * 4 + ["scenario_b"] * 4
    assert [c.soft_judge for c in out] == [False] * 4 + [True] * 4
    assert [c.scenario_id for c in cells(root, scripted_only=True)] == ["scenario_a"] * 4
