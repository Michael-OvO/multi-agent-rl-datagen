"""Pin the constraint layer's guarantees.

The one that matters most: no knob may reach the judge. Everything here changes
who can act; nothing here changes what counts as done.
"""

from dataclasses import FrozenInstanceError

import pytest

from forge.appworld.partition import (
    Constraints,
    Topology,
    Visibility,
    control_for,
)

ROSTER = ("phone", "venmo")


def test_main_has_no_apis_unless_it_is_the_control():
    assert not Constraints(roster=ROSTER, topology=Topology.STAR).main_has_apis
    assert not Constraints(roster=ROSTER, topology=Topology.CHAIN).main_has_apis
    assert Constraints(roster=ROSTER, topology=Topology.OPEN).main_has_apis


def test_star_routes_everything_through_main():
    c = Constraints(roster=ROSTER, topology=Topology.STAR)
    assert c.allowed_targets("main") == ROSTER
    # specialists cannot reach each other: a cross-app fact must pass through
    # the Main, which is what makes the Main's briefing quality measurable.
    assert c.allowed_targets("phone") == ()
    assert c.allowed_targets("venmo") == ()


def test_chain_forces_sub_to_sub_handoff():
    c = Constraints(roster=ROSTER, topology=Topology.CHAIN)
    assert c.allowed_targets("main") == ("phone",)   # main seeds the head only
    assert c.allowed_targets("phone") == ("venmo",)  # sub -> sub
    assert c.allowed_targets("venmo") == ()          # tail


def test_control_is_the_free_ablation_twin():
    c = control_for(ROSTER)
    assert c.main_has_apis
    assert c.topology is Topology.OPEN
    # Same task, same oracle, partition off. If a configuration does not beat
    # this, the sub-agents were decoration.
    assert c.allowed_targets("main") == ()


def test_control_is_allowed_on_a_single_app_roster():
    # The control must be constructible for any task, since it is the baseline.
    control_for(("spotify",))


def test_partition_on_a_single_app_roster_is_rejected():
    with pytest.raises(ValueError, match="nothing to coordinate"):
        Constraints(roster=("spotify",), topology=Topology.STAR)


def test_budget_below_roster_size_is_representable():
    # Roster size is not a solvability proof: a roster may include alternative
    # sources, and Gaia2 uses bN as a soft target rather than a hard cap.
    assert Constraints(
        roster=("a", "b", "c"), delegation_budget=2
    ).delegation_budget == 2


def test_budget_or_target_must_be_positive():
    with pytest.raises(ValueError, match="positive"):
        Constraints(roster=ROSTER, delegation_budget=0)


def test_budget_equal_to_roster_size_is_allowed():
    Constraints(roster=ROSTER, delegation_budget=2)


def test_labels_are_distinct_per_configuration():
    seen = {
        Constraints(roster=ROSTER, topology=t, visibility=v, delegation_budget=b).label
        for t in (Topology.STAR, Topology.CHAIN)
        for v in (Visibility.DOCS, Visibility.NAMES)
        for b in (None, 4)
    }
    assert len(seen) == 8, "configurations must not collide into one task id"


def test_constraints_are_frozen():
    # A task's configuration must not drift after rendering.
    c = Constraints(roster=ROSTER)
    with pytest.raises(FrozenInstanceError):
        c.topology = Topology.OPEN  # type: ignore[misc]


def test_chain_is_not_shipped_until_the_handoff_exists():
    """CHAIN's difficulty signal is fake until a specialist can actually hand off.

    The Main can reach only roster[0]; `allowed_targets(<specialist>)` returns
    the next hop and nothing calls it. So the task is unsolvable and its score
    reflects the step cap, not the topology.

    A knob that moves the score by breaking the task is worse than decoration.
    Ship it when the handoff is implemented AND measured.

    The docstring used to recite the measurement and nothing checked it -- so it
    kept saying 0.167 and `deleg=12 every time` long after the sweep said
    otherwise. It asserts against the sweep now.
    """
    import json
    from pathlib import Path

    from forge.appworld.cli import SHIPPED_CONFIGS

    rows = [r for r in json.loads(
        (Path(__file__).resolve().parents[2] / "sweep" /
         "appworld_knobs_v5.json").read_text())
        if r["config"].startswith("chain")]
    assert rows, "no chain rows in the sweep; drop this test with the config"
    floor = 0.333
    assert all(r["partial"] <= floor for r in rows), (
        f"chain now scores above the floor ({[r['partial'] for r in rows]}); "
        f"if the handoff was implemented, re-measure and reconsider shipping it"
    )

    assert all(t is not Topology.CHAIN for t, _, _ in SHIPPED_CONFIGS)


def test_chain_handoff_target_is_defined_even_though_unshipped():
    # The definition is right; the caller is missing. Keep this so whoever wires
    # the handoff has a spec to satisfy.
    c = Constraints(roster=("phone", "venmo", "gmail"), topology=Topology.CHAIN)
    assert c.allowed_targets("main") == ("phone",)
    assert c.allowed_targets("phone") == ("venmo",)
    assert c.allowed_targets("venmo") == ("gmail",)
    assert c.allowed_targets("gmail") == ()
