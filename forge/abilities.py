"""The three trainable abilities, and the one knob each is allowed to turn.

The consolidation (docs/iteration_three_abilities.md): of everything a
multi-agent Main must do, three abilities are simultaneously the largest
measured failure mass, provably RL-trainable, and cheap to verify --
capability discovery (*whom* to delegate to), context transfer (*what* to put
in the brief), and delegation economy (*when* to spawn and stop). This module
pins each ability to exactly one constraint knob so that a rendered cell
exercises one ability and its sandwich verdict prices that ability, never a
blend:

    DISCOVERY           visibility = NAMES     (docs off, budget off)
    CONTEXT_TRANSFER    the pure partition     (docs on, budget off)
    DELEGATION_ECONOMY  finite budget          (docs on, so discovery is
                                                neutralised and only the
                                                budget bites)

Why one knob each: the knob deltas are per-ability price tags only while the
other knobs are held at their neutral setting. A names+budget cell moves two
abilities at once and its delta prices neither -- `ability_of` still
classifies it (as economy, the harsher constraint) so a stray sweep row is
never double-counted, but `config_for` will never render one.

Nothing here touches a judge, an oracle, or a reward. Abilities are
constraint templates plus bookkeeping over `validity` verdicts.
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum

from forge.appworld.partition import Constraints, Topology, Visibility
from forge.appworld.validity import Cell, Yield, is_control

_TOPOLOGIES = {t.value for t in Topology}
_VISIBILITIES = {v.value for v in Visibility}


class Ability(str, Enum):
    """The three abilities worth rendering cells for, by measured trainability."""

    DISCOVERY = "capability-discovery"
    CONTEXT_TRANSFER = "context-transfer"
    DELEGATION_ECONOMY = "delegation-economy"


def config_for(ability: Ability, roster: tuple[str, ...]) -> Constraints:
    """The constraint configuration that isolates `ability` on `roster`.

    Star topology throughout: chain remains unshipped, and a topology change
    would be a second turned knob.
    """
    if ability is Ability.DISCOVERY:
        return Constraints(
            roster=roster, topology=Topology.STAR, visibility=Visibility.NAMES
        )
    if ability is Ability.CONTEXT_TRANSFER:
        return Constraints(
            roster=roster, topology=Topology.STAR, visibility=Visibility.DOCS
        )
    # The tightest budget that leaves the task solvable: one delegation per
    # specialist. Constraints itself rejects anything lower.
    return Constraints(
        roster=roster,
        topology=Topology.STAR,
        visibility=Visibility.DOCS,
        delegation_budget=len(roster),
    )


def ability_of(config: str) -> Ability | None:
    """Which ability a config label prices. None for the control.

    Labels are `partition.Constraints.label`: `<topology>-<visibility>-b<budget>`.
    Non-star partitions (chain, and any future tree) also return None: a
    changed topology is a turned knob on top of whatever else the label sets,
    so the cell is a topology experiment, not a priced ability --
    sweep/appworld_knobs_v5.json's chain rows must not pollute the discovery
    bucket. Precedence when a *star* label still has two knobs turned (never
    rendered by `config_for`, but sweeps are data and data drifts): a finite
    budget wins, because a budget binds harder than missing docs and the cell
    must land in exactly one bucket.
    """
    parts = config.split("-")
    if (
        len(parts) != 3
        or parts[0] not in _TOPOLOGIES
        or parts[1] not in _VISIBILITIES
        or not parts[2].startswith("b")
    ):
        raise ValueError(f"not a constraint label: {config!r}")
    if is_control(config):
        return None
    if parts[0] != Topology.STAR.value:
        return None
    if parts[2] != "binf":
        return Ability.DELEGATION_ECONOMY
    if parts[1] == Visibility.NAMES.value:
        return Ability.DISCOVERY
    return Ability.CONTEXT_TRANSFER


def yield_by_ability(cells: list[Cell]) -> dict[Ability, Yield]:
    """Usable cells over measurable cells, bucketed by the ability they price.

    Control cells judge nothing and land in no bucket. The Yield semantics
    are `validity.yield_by_config`'s, one level up: cells whose control
    failed are reported separately, and `seeds` is the weakest cell's.
    """
    grouped: dict[Ability, list[Cell]] = defaultdict(list)
    for cell in cells:
        ability = ability_of(cell.config)
        if ability is not None:
            grouped[ability].append(cell)

    out = {}
    for ability, cs in grouped.items():
        measurable = [c for c in cs if c.measurable]
        out[ability] = Yield(
            config=ability.value,
            valid=sum(c.usable for c in measurable),
            total=len(measurable),
            unmeasurable=len(cs) - len(measurable),
            seeds=min((c.seeds for c in cs), default=0),
        )
    return out
