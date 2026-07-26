"""Rendering Gaia2 cells: seamful scenarios x the three abilities, plus the
control -- specs only, since no ARE runtime exists yet to execute them.

The one-knob rule from `forge/abilities.py` decides the grid; `admit`
decides who enters it. A scenario that is not seamful renders nothing:
partitioning an operation seam decorates, and decoration is the exact
failure `select.py` and `seams.py` were built to refuse.
"""

from __future__ import annotations

import json
from pathlib import Path

from forge.abilities import Ability
from forge.gaia2.render import render_cells

_FIXTURES = Path(__file__).parent / "fixtures" / "gaia2"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / f"{name}.json").read_text())


def test_seamful_scenario_renders_control_plus_three_ability_cells():
    cells = render_cells([_load("seamful")])
    assert [(c.ability, c.config) for c in cells] == [
        (None, "open-docs-binf"),
        (Ability.DISCOVERY, "star-names-binf"),
        (Ability.CONTEXT_TRANSFER, "star-docs-binf"),
        (Ability.DELEGATION_ECONOMY, "star-docs-b2"),
    ]


def test_cells_carry_roster_seams_and_structure():
    cell = render_cells([_load("seamful")])[0]
    assert cell.scenario_id == "fixture_seamful"
    assert cell.roster == ("Contacts", "Emails")
    assert cell.seam_edges == (("Contacts", "Emails"),)
    assert (cell.writes, cell.depth, cell.width) == (1, 1, 1)


def test_unseamful_scenarios_render_nothing():
    assert render_cells([_load("singleapp"), _load("operation")]) == []


def test_rows_are_json_ready():
    row = render_cells([_load("seamful")])[1].as_row()
    assert row["ability"] == "capability-discovery"
    assert row["config"] == "star-names-binf"
    assert row["roster"] == ["Contacts", "Emails"]
