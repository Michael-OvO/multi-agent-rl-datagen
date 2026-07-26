"""The three-abilities layer: one ability, one knob, and a yield per ability.

The consolidation this encodes (docs/iteration_three_abilities.md): the three
most trainable multi-agent abilities are capability discovery (whom to
delegate to), context transfer (what to put in the brief), and delegation
economy (when to spawn, when to stop). Each maps to exactly one constraint
knob, so a rendered cell exercises one ability and its verdict prices that
ability -- never a blend.
"""

from __future__ import annotations

import pytest

from forge.abilities import Ability, ability_of, config_for, yield_by_ability
from forge.appworld.partition import Topology, Visibility
from forge.appworld.validity import Cell, judge_cell

ROSTER = ("phone", "venmo")


# --- ability -> config: one knob each -------------------------------------


def test_discovery_config_turns_only_the_visibility_knob():
    c = config_for(Ability.DISCOVERY, ROSTER)
    assert c.visibility is Visibility.NAMES
    assert c.topology is Topology.STAR
    assert c.delegation_budget is None


def test_context_transfer_config_is_the_pure_partition():
    c = config_for(Ability.CONTEXT_TRANSFER, ROSTER)
    assert c.visibility is Visibility.DOCS
    assert c.topology is Topology.STAR
    assert c.delegation_budget is None


def test_economy_config_turns_only_the_budget_knob():
    c = config_for(Ability.DELEGATION_ECONOMY, ROSTER)
    assert c.visibility is Visibility.DOCS  # discovery neutralised
    assert c.delegation_budget == len(ROSTER)  # tightest solvable budget


# --- config label -> ability: how sweep rows get tagged -------------------


def test_ability_of_reads_the_one_turned_knob():
    assert ability_of("star-names-binf") is Ability.DISCOVERY
    assert ability_of("star-docs-binf") is Ability.CONTEXT_TRANSFER
    assert ability_of("star-docs-b2") is Ability.DELEGATION_ECONOMY


def test_finite_budget_wins_precedence_over_visibility():
    # A names+budget cell would blend two abilities; if one ever appears in a
    # sweep, it is priced as economy and flagged upstream, never double-counted.
    assert ability_of("star-names-b2") is Ability.DELEGATION_ECONOMY


def test_the_control_has_no_ability():
    assert ability_of("open-docs-binf") is None


def test_chain_cells_price_no_ability():
    # A non-star partition turns the topology knob *and* whatever else is set:
    # two knobs, so it prices no single ability. It is a topology experiment.
    assert ability_of("chain-names-binf") is None
    assert ability_of("chain-docs-b2") is None


def test_unparseable_labels_raise():
    with pytest.raises(ValueError):
        ability_of("not-a-config")


# --- cells -> yield per ability --------------------------------------------


def _cell(config: str, scores: tuple[float, ...], control: float = 1.0,
          floor: float = 0.333) -> Cell:
    return Cell(
        task_id="t1",
        config=config,
        scores=scores,
        control=control,
        floor=floor,
        verdict=judge_cell(list(scores), control, floor),
    )


def test_yield_by_ability_groups_and_counts_valid_cells():
    cells = [
        _cell("star-names-binf", (0.5, 0.667, 0.833, 0.5, 0.667)),   # VALID
        _cell("star-docs-binf", (1.0, 1.0, 1.0, 1.0, 1.0)),          # NO_BITE
        _cell("star-docs-b2", (0.333, 0.333, 0.333, 0.333, 0.333)),  # DEGENERATE
    ]
    y = yield_by_ability(cells)
    assert y[Ability.DISCOVERY].valid == 1
    assert y[Ability.DISCOVERY].total == 1
    assert y[Ability.CONTEXT_TRANSFER].valid == 0
    assert y[Ability.DELEGATION_ECONOMY].valid == 0


def test_yield_by_ability_ignores_control_cells():
    cells = [_cell("open-docs-binf", (1.0, 1.0, 1.0, 1.0, 1.0))]
    assert yield_by_ability(cells) == {}


def test_v5_sweep_ability_yield_matches_the_readme():
    """The committed evidence, re-read through the ability lens.

    README reports star-docs 3/3 and star-names 2/3 at five seeds. Tagged by
    ability that is context-transfer 3/3 and discovery 2/3 -- and chain rows,
    a topology experiment, must not pollute either bucket.
    """
    import json
    from pathlib import Path

    from forge.appworld.validity import judge_cells

    root = Path(__file__).parent.parent.parent
    rows = json.loads((root / "sweep/appworld_knobs_v5.json").read_text())
    floors = {
        r["partial"]
        for r in json.loads((root / "sweep/appworld_donothing.json").read_text())
    }
    assert len(floors) == 1
    cells = judge_cells(rows, floors.pop())

    y = yield_by_ability(cells)
    assert y[Ability.CONTEXT_TRANSFER].valid == 3
    assert y[Ability.CONTEXT_TRANSFER].total == 3
    assert y[Ability.DISCOVERY].valid == 2
    assert y[Ability.DISCOVERY].total == 3
    assert y[Ability.CONTEXT_TRANSFER].measured
    assert y[Ability.DISCOVERY].measured
