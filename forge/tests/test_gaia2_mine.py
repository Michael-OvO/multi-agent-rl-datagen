"""The Gaia2 miner: rosters and seams from gold write actions, no code to parse.

Gaia2 scenarios carry no reference *code* -- their ground truth is a list of
OracleEvents (gold write actions) plus the full initial state of every app. So
the two mining rules port from AppWorld, but their mechanics change:

  * roster: AppWorld read it off `apis.<app>.<method>(` calls. Here it is the
    apps the gold writes touch, **plus** every app a seam proves was read --
    the read side never appears in oracle events, so seam sources are the only
    evidence an app's state was needed.
  * seams: AppWorld ran a taint pass over solution code. Here a seam is *state
    provenance*: a gold write whose argument value exists in a different app's
    initial state, is absent from the target app's own state, and was not
    handed to the agent in the user instruction. The fact had to cross.
"""

from __future__ import annotations

import json
from pathlib import Path

from forge.gaia2.mine import (
    admit,
    gold_writes,
    information_seams,
    user_text,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "gaia2"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / f"{name}.json").read_text())


def test_gold_writes_extracts_app_function_and_args():
    writes = gold_writes(_load("seamful"))
    assert len(writes) == 1
    w = writes[0]
    assert w.app == "Emails"
    assert w.function == "send_email"
    assert dict(w.args)["recipients"] == "erik.lund@example.se"


def test_user_text_comes_from_user_events_only():
    text = user_text(_load("seamful"))
    assert "kitchen leak" in text
    # The gold write's payload is not part of what the user said.
    assert "erik.lund@example.se" not in text


def test_information_seam_found_via_state_provenance():
    seams = information_seams(_load("seamful"))
    assert len(seams) == 1
    s = seams[0]
    assert (s.source, s.target) == ("Contacts", "Emails")
    assert s.value == "erik.lund@example.se"


def test_roster_includes_seam_sources_not_just_write_apps():
    span = admit(_load("seamful"))
    # Emails is written; Contacts is only *read* -- the seam is the sole
    # evidence it was needed, and it must still make the roster.
    assert span.roster == ("Contacts", "Emails")
    assert span.usable
    assert span.seamful


def test_value_present_in_user_text_is_not_a_seam():
    scenario = _load("seamful")
    # Hand the agent the email address in the instruction: nothing needs to
    # cross apps any more, so the seam must disappear.
    scenario["events"][0]["action"]["args"][0]["value"] += (
        " His address is erik.lund@example.se."
    )
    assert information_seams(scenario) == []


def test_value_local_to_target_app_is_not_a_seam():
    seams = information_seams(_load("singleapp"))
    assert seams == []


def test_single_app_scenario_is_not_usable():
    span = admit(_load("singleapp"))
    assert span.roster == ("RentAFlat",)
    assert not span.usable


def test_multi_app_writes_without_crossing_fact_is_operation_seam():
    span = admit(_load("operation"))
    # Two apps written, but every argument value came from the user's own
    # instruction: parallel chores, nothing to coordinate about.
    assert span.roster == ("Calendar", "Shopping")
    assert span.usable
    assert not span.seamful
    assert information_seams(_load("operation")) == []


def test_infra_apps_never_join_the_roster():
    for name in ("seamful", "singleapp", "operation"):
        assert "AgentUserInterface" not in admit(_load(name)).roster
