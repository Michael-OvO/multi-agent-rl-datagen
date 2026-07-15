"""Pin the constraint layer's guarantees.

The one that matters most: no knob may reach the judge. Everything here changes
who can act; nothing here changes what counts as done.
"""

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


def test_budget_below_roster_size_is_rejected():
    # An unsolvable task produces no signal, just noise.
    with pytest.raises(ValueError, match="unsolvable"):
        Constraints(roster=("a", "b", "c"), delegation_budget=2)


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
    with pytest.raises(Exception):
        c.topology = Topology.OPEN  # type: ignore[misc]
