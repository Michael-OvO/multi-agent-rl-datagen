"""The causal delegation heuristic and Gaia2's soft economy signal."""

import json
from pathlib import Path

import pytest

from forge.abilities import Ability, config_for
from forge.gaia2.mine import admit, delegation_heuristic, delegation_target
from forge.gaia2.runtime import delegation_economy_features

REPO = Path(__file__).resolve().parents[2]


def _scenario(events, apps=()):
    return {
        "metadata": {"definition": {"scenario_id": "s"}},
        "apps": list(apps),
        "events": events,
    }


def _user(event_id="u"):
    return {
        "class_name": "Event",
        "event_id": event_id,
        "event_type": "USER",
        "dependencies": [],
        "event_relative_time": 0,
        "action": {
            "app": "AgentUserInterface",
            "function": "send_message_to_agent",
            "args": [],
        },
    }


def _env(event_id, dependencies):
    return {
        "class_name": "Event",
        "event_id": event_id,
        "event_type": "ENV",
        "dependencies": list(dependencies),
        "event_relative_time": 1,
        "action": {"app": "Messages", "function": "receive", "args": []},
    }


def _write(
    app,
    event_id,
    function="do",
    dependencies=("u",),
    args=(),
    relative=1,
):
    return {
        "class_name": "OracleEvent",
        "event_id": event_id,
        "event_type": "AGENT",
        "dependencies": list(dependencies),
        "event_relative_time": relative,
        "action": {
            "app": app,
            "function": function,
            "args": [{"name": n, "value": v} for n, v in args],
        },
    }


def test_independent_interleaving_is_grouped_instead_of_overcounted():
    # JSON order is not an execution plan. All three writes share one causal
    # frontier, so Calendar can do both calls in one visit.
    events = [
        _write("Calendar", "c1"),
        _write("Emails", "e1"),
        _write("Calendar", "c2"),
        _user(),
    ]
    estimate = delegation_heuristic(_scenario(events))
    assert estimate.write_visits == 2
    assert estimate.target == 2


def test_same_app_after_environment_reply_is_a_new_visit():
    events = [
        _write("Messages", "m1"),
        _env("reply", ("m1",)),
        _write("Messages", "m2", dependencies=("reply",)),
        _user(),
    ]
    estimate = delegation_heuristic(_scenario(events))
    assert estimate.phases == 2
    assert estimate.write_visits == 2


def test_same_app_after_a_long_delay_is_a_new_visit():
    events = [
        _write("Messages", "m1"),
        _write("Messages", "m2", dependencies=("m1",), relative=30),
        _user(),
    ]
    assert delegation_heuristic(_scenario(events)).write_visits == 2


def test_alternative_provenance_sources_cost_one_read_not_two():
    value = "1423 NW 23rd Ave, Portland, OR 97210"
    apps = [
        {"name": "Contacts", "app_state": {"address": value}},
        {"name": "InternalContacts", "app_state": {"address": value}},
        {"name": "Cabs", "app_state": {}},
    ]
    events = [
        _write(
            "Cabs",
            "cab",
            function="order_ride",
            args=(("end_location", value),),
        ),
        _user(),
    ]
    estimate = delegation_heuristic(_scenario(events, apps))
    assert estimate.write_visits == 1
    assert estimate.read_visits == 1
    assert estimate.target == 2


def test_repeated_seam_edges_do_not_hide_a_shared_cheapest_source():
    first = "first provenance fact"
    second = "second provenance fact"
    apps = [
        {"name": "Shared", "app_state": {"first": first, "second": second}},
        {"name": "FirstOnly", "app_state": {"first": first}},
        {"name": "SecondOnly", "app_state": {"second": second}},
        {"name": "Target", "app_state": {}},
    ]
    events = [
        _write("Target", "one", function="send_one", args=(("value", first),)),
        _write("Target", "two", function="send_two", args=(("value", second),)),
        _user(),
    ]
    estimate = delegation_heuristic(_scenario(events, apps))
    assert estimate.write_visits == 1
    assert estimate.read_visits == 1  # one Shared visit supplies both facts
    assert estimate.target == 2


def test_an_existing_early_source_visit_carries_the_read_for_free():
    value = "The Eagle Pub, Cambridge venue"
    apps = [
        {"name": "Calendar", "app_state": {"event": value}},
        {"name": "Cabs", "app_state": {}},
    ]
    events = [
        _write("Calendar", "calendar"),
        _write(
            "Cabs",
            "cab",
            function="order_ride",
            dependencies=("calendar",),
            args=(("end_location", value),),
        ),
        _user(),
    ]
    estimate = delegation_heuristic(_scenario(events, apps))
    assert estimate.write_visits == 2
    assert estimate.read_visits == 0


def test_a_same_phase_source_visit_after_the_consumer_is_not_free():
    value = "The Eagle Pub, Cambridge venue"
    apps = [
        {"name": "Calendar", "app_state": {"event": value}},
        {"name": "Cabs", "app_state": {}},
    ]
    events = [
        _write(
            "Cabs",
            "cab",
            function="order_ride",
            args=(("end_location", value),),
        ),
        _write("Calendar", "calendar", dependencies=("cab",)),
        _user(),
    ]
    estimate = delegation_heuristic(_scenario(events, apps))
    assert estimate.write_visits == 2
    assert estimate.read_visits == 1
    assert estimate.target == 3


def test_the_economy_target_is_explicitly_adjustable_even_below_roster_size():
    roster = ("Cabs", "Calendar", "Messages")
    adjusted = config_for(
        Ability.DELEGATION_ECONOMY, roster, budget_target=2)
    assert adjusted.delegation_budget == 2
    assert adjusted.label == "star-docs-b2"


def test_the_cab_scenario_heuristic_is_four_without_claiming_a_floor():
    path = REPO / "gaia2_data" / "mini" / "scenario_universe_30_68r6vs.json"
    if not path.exists():
        pytest.skip("gaia2_data is not fetched (gitignored)")
    scenario = json.loads(path.read_text())
    estimate = delegation_heuristic(scenario)
    span = admit(scenario)
    assert estimate.write_visits == 3  # Messages, then Cabs -> Messages
    assert estimate.read_visits == 1   # Calendar
    assert delegation_target(scenario) == span.delegation_target == 4


def test_soft_economy_signal_decays_but_never_declares_execution_blocked():
    assert delegation_economy_features(4, 4, task_success=True) == {
        "delegation_target": 4,
        "delegations_over_target": 0,
        "delegation_efficiency": 1.0,
        "delegation_economy_reward": 1.0,
    }
    assert delegation_economy_features(4, 5, task_success=True) == {
        "delegation_target": 4,
        "delegations_over_target": 1,
        "delegation_efficiency": 0.8,
        "delegation_economy_reward": 0.8,
    }
    assert delegation_economy_features(4, 5, task_success=False)[
        "delegation_economy_reward"
    ] == 0.0
