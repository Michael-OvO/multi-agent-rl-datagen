"""The Gaia2 campaign grid, defined once.

The grid is every admitted seamful scenario with a fetched file (mini first,
then adaptability) crossed with the OPEN control and the three one-knob
ability cells. The campaign runs it, `forge.gaia2.cli render --all` renders
it, and `forge/tests/test_gaia2_tasks_current.py` checks the rendered tasks
against it -- all through this module, so none of the three can hold a
different opinion about which cells exist.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from forge.abilities import Ability, config_for
from forge.appworld.partition import Constraints, control_for
from forge.gaia2.mine import admit

#: None is the OPEN control; the rest are the one-knob ability cells.
GRID = (None, Ability.DISCOVERY, Ability.CONTEXT_TRANSFER,
        Ability.DELEGATION_ECONOMY)

#: Where the grid's scenarios are listed, and the split each list came from.
CELL_FILES = (("sweep/gaia2_cells.json", "mini"),
              ("sweep/gaia2_cells_adaptability.json", "adaptability"))


@dataclass(frozen=True)
class Cell:
    """One (scenario, configuration) pair: what one campaign episode runs and
    what one Harbor task ships."""
    scenario_id: str
    scenario_path: Path
    ability: Ability | None
    constraints: Constraints
    soft_judge: bool
    economy_target: int

    @property
    def task_name(self) -> str:
        return f"gaia2-{self.constraints.label}-{self.scenario_id}"


def eligible(span, scripted_only: bool) -> bool:
    """Admission, plus the optional judge-uniform restriction.

    `--scripted-only` exists because the grader is welded to the scenario:
    reply-conditioned scenarios can only run under the soft judge, and in the
    v3 campaign that judge's column was all zeros -- so every cross-arm
    comparison rode on the 5 of 37 scenarios the deterministic verifier
    grades. A seed spent under this flag buys 20 cells that can actually
    move, instead of 148 of which 128 are structurally pinned to zero.
    """
    if not (span.usable and span.seamful):
        return False
    if span.roster_blind:
        # The partition provably omits a fact the gold writes consume (see
        # mine.BlindFact): every seat is locked out of it, so every episode
        # is a guaranteed failure. v4 bought four of these on one scenario.
        return False
    return not (scripted_only and span.reply_conditioned)


def scenario_paths(root: Path) -> dict[str, Path]:
    """Every unique seamful scenario with a fetched file, mini first."""
    seen: dict[str, Path] = {}
    for cells_file, split in CELL_FILES:
        for cell in json.loads((root / cells_file).read_text()):
            sid = cell["scenario_id"]
            if sid in seen:
                continue
            path = root / "gaia2_data" / split / f"{sid}.json"
            if path.exists():
                seen[sid] = path
    return seen


def _target(span, economy_target: int | None, economy_target_offset: int) -> int:
    if economy_target is not None:
        return economy_target
    return max(1, span.delegation_target + economy_target_offset)


def cells_for(scenario_path: Path, *, economy_target: int | None = None,
              economy_target_offset: int = 0,
              scripted_only: bool = False) -> list[Cell]:
    """The four cells of one scenario, or none if it is not admitted."""
    scenario_path = Path(scenario_path)
    span = admit(json.loads(scenario_path.read_text()))
    if not eligible(span, scripted_only):
        return []
    target = _target(span, economy_target, economy_target_offset)
    out = []
    for ability in GRID:
        constraints = (control_for(span.roster) if ability is None
                       else config_for(ability, span.roster, budget_target=target))
        out.append(Cell(span.scenario_id, scenario_path, ability, constraints,
                        span.reply_conditioned, target))
    return out


def cells(root: Path, *, scripted_only: bool = False,
          economy_target: int | None = None,
          economy_target_offset: int = 0) -> list[Cell]:
    """The whole grid, scenarios in id order, four cells each."""
    out: list[Cell] = []
    for _sid, path in sorted(scenario_paths(root).items()):
        out.extend(cells_for(path, economy_target=economy_target,
                             economy_target_offset=economy_target_offset,
                             scripted_only=scripted_only))
    return out
