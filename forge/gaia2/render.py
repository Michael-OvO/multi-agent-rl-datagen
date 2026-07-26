"""Render Gaia2 cells: seamful scenarios x the three abilities, plus control.

Specs only. No ARE runtime exists in this repo yet, so a rendered cell is a
complete, priced *description* of a rollout -- scenario, constraint config,
ability tag, roster, seam edges, structural difficulty -- and not an
executable task directory. When the runtime lands, these specs are its work
orders; until then they are the measured answer to "what would we run".

The grid per admitted scenario is fixed by the one-knob rule
(`forge/abilities.py`): the shared control first, then one cell per ability.
Nothing else is rendered -- a second turned knob prices nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from forge.abilities import Ability, config_for
from forge.appworld.partition import control_for
from forge.gaia2.mine import admit, scenario_id
from forge.gaia2.structure import Structure, structure_of

#: Grid order per scenario: control, then the abilities in narrative order.
_GRID: tuple[Ability | None, ...] = (
    None,
    Ability.DISCOVERY,
    Ability.CONTEXT_TRANSFER,
    Ability.DELEGATION_ECONOMY,
)


@dataclass(frozen=True)
class CellSpec:
    """One (scenario, config) cell, fully priced but not yet executable."""

    scenario_id: str
    category: str | None
    ability: Ability | None  # None = the shared control
    config: str
    roster: tuple[str, ...]
    seam_edges: tuple[tuple[str, str], ...]
    writes: int
    depth: int
    width: int

    def as_row(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "category": self.category,
            "ability": self.ability.value if self.ability else None,
            "config": self.config,
            "roster": list(self.roster),
            "seam_edges": [list(edge) for edge in self.seam_edges],
            "writes": self.writes,
            "depth": self.depth,
            "width": self.width,
        }


def render_cells(scenarios: list[dict]) -> list[CellSpec]:
    """The full grid over every scenario that is usable *and* seamful."""
    cells: list[CellSpec] = []
    for scenario in sorted(scenarios, key=scenario_id):
        span = admit(scenario)
        if not (span.usable and span.seamful):
            continue
        structure: Structure = structure_of(scenario)
        seam_edges = tuple(
            sorted({(seam.source, seam.target) for seam in span.seams})
        )
        category = (scenario.get("_gaia2") or {}).get("category")
        for ability in _GRID:
            config = (
                control_for(span.roster)
                if ability is None
                else config_for(ability, span.roster)
            )
            cells.append(
                CellSpec(
                    scenario_id=span.scenario_id,
                    category=category,
                    ability=ability,
                    config=config.label,
                    roster=span.roster,
                    seam_edges=seam_edges,
                    writes=structure.writes,
                    depth=structure.depth,
                    width=structure.width,
                )
            )
    return cells
