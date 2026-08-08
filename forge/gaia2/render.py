"""Render Gaia2 cells: seamful scenarios x the three abilities, plus control.

A cell is the measured specification shared by the in-process ARE runtime and
the Harbor task renderer: scenario, constraint config, ability tag, roster,
seam edges, delegation target, and structural difficulty.

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
    delegation_target: int
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
            "delegation_target": self.delegation_target,
            "writes": self.writes,
            "depth": self.depth,
            "width": self.width,
        }


def render_cells(
    scenarios: list[dict],
    economy_target: int | None = None,
    economy_target_offset: int = 0,
) -> list[CellSpec]:
    """The full grid over every scenario that is usable *and* seamful.

    By default each economy cell uses the miner's task-specific heuristic.
    `economy_target` overrides every task explicitly; otherwise
    `economy_target_offset` adjusts each heuristic, which makes sensitivity
    sweeps possible without changing the mined scenario.
    """
    if economy_target is not None and economy_target < 1:
        raise ValueError("economy_target must be positive")
    cells: list[CellSpec] = []
    for scenario in sorted(scenarios, key=scenario_id):
        span = admit(scenario)
        if not (span.usable and span.seamful):
            continue
        if span.roster_blind:
            # The partition provably omits a fact the gold writes consume
            # (mine.BlindFact); every cell built from it is a guaranteed
            # failure. Same refusal as the campaign and the render CLI.
            continue
        structure: Structure = structure_of(scenario)
        seam_edges = tuple(
            sorted({(seam.source, seam.target) for seam in span.seams})
        )
        category = (scenario.get("_gaia2") or {}).get("category")
        target = (
            economy_target
            if economy_target is not None
            else max(1, span.delegation_target + economy_target_offset)
        )
        for ability in _GRID:
            config = (
                control_for(span.roster)
                if ability is None
                else config_for(ability, span.roster,
                                budget_target=target)
            )
            cells.append(
                CellSpec(
                    scenario_id=span.scenario_id,
                    category=category,
                    ability=ability,
                    config=config.label,
                    roster=span.roster,
                    seam_edges=seam_edges,
                    delegation_target=target,
                    writes=structure.writes,
                    depth=structure.depth,
                    width=structure.width,
                )
            )
    return cells
