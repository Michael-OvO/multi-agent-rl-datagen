"""Gaia2 runtime tests with a scripted client and world -- no tokens, no
network, no `are.*` import.

Two failure families motivate this file. First, the AppWorld lesson:
structural constraints must be *enforced*, not described -- a Main that can
reach a forbidden specialist makes the topology decoration. Delegation
economy is intentionally different: bN is a soft target and exceeding it
must remain possible while producing an auxiliary penalty.
Second, the gaps this runtime exists to close must stay closed: the waiting
verb has to actually deliver what arrived (a WAIT that silently drops the
notification turns every time-based scenario into a coin flip), a
downgraded specialist has to be refused before any model runs, and the
trajectory has to serialize -- AppWorld's `RunLog.interactions` was appended
to for an entire sweep campaign and never written anywhere.
"""

import json

from pytest import approx, raises

from forge.appworld.partition import Constraints, Topology, Visibility, control_for
from forge.gaia2.runtime import (
    OBJECTIVE_ACTION_CONTRACT,
    OBJECTIVE_ACTION_CONTRACT_VERSION,
    EpisodeLog,
    Msg,
    describe_tool,
    run_main,
    run_specialist,
)

ROSTER = ("Contacts", "Cabs")

#: tool -> owning app, the fake world's whole ontology.
TOOLS = {
    "Contacts__lookup": "Contacts",
    "Cabs__order_ride": "Cabs",
}


class FakeWorld:
    """The World interface over scripts: canned catalogs, canned arrivals."""

    CATALOG_MARKER = "CATALOG-OF-{app}"

    def __init__(self, wait_script=(), drain_script=()):
        self._wait_script = [list(w) for w in wait_script]
        self._drain_script = [list(d) for d in drain_script]
        self.calls = []
        self.waited = []
        self.sent_to_user = []

    def time_str(self):
        return "2026-07-28 12:00:00"

    def catalog(self, app):
        return self.CATALOG_MARKER.format(app=app)

    def call(self, apps, tool, args):
        owner = TOOLS.get(tool)
        if owner is None:
            return f"unknown tool {tool!r}", "error"
        if owner not in tuple(apps):
            return f"{tool} belongs to {owner}, which you cannot use", "refused"
        self.calls.append((tool, args))
        return f"result-of-{tool}", "ok"

    def drain(self):
        return self._drain_script.pop(0) if self._drain_script else []

    def wait(self, seconds):
        self.waited.append(seconds)
        return self._wait_script.pop(0) if self._wait_script else []

    def send_user(self, text):
        self.sent_to_user.append(text)


def _wrap(text):
    return type("R", (), {"choices": [type("C", (), {
        "message": type("M", (), {"content": text})()})()]})()


class FakeClient:
    """Replays scripted Main replies; specialists get their own script.

    Told apart by system prompt, as in test_appworld_runtime.FakeClient --
    a specialist eating the Main's next scripted reply measures nothing.
    """

    def __init__(self, main_replies, specialist_replies=()):
        self._main = list(main_replies)
        self._specialist = list(specialist_replies)
        self.seen = []
        self.systems = []

        outer = self

        class _Completions:
            def create(self, model, messages, temperature=None):
                system = messages[0]["content"]
                outer.systems.append(system)
                if not system.startswith("You are the Main coordinator"):
                    return _wrap(outer._specialist.pop(0) if outer._specialist
                                 else "FINAL: did it")
                outer.seen.append(messages[-1]["content"])
                return _wrap(outer._main.pop(0) if outer._main
                             else "DONE :: exhausted")

        self.chat = type("Chat", (), {"completions": _Completions()})()


STAR_DOCS = Constraints(roster=ROSTER, topology=Topology.STAR,
                        visibility=Visibility.DOCS)


# -- the waiting feature ----------------------------------------------------


def test_the_wait_verb_jumps_time_and_delivers_what_arrived():
    world = FakeWorld(wait_script=(
        [Msg("notification", "Cabs: ride status updated")],
        [],
    ))
    client = FakeClient(["WAIT 600", "DONE :: completed"])
    log = EpisodeLog()
    answer = run_main(client, world, "order a cab", STAR_DOCS, log)

    assert answer == "completed"
    assert world.waited[0] == 600
    assert any("Cabs: ride status updated" in seen for seen in client.seen), \
        "the notification never reached the Main's transcript"
    wait_events = [e for e in log.events if e["type"] == "wait"]
    assert wait_events[0]["arrived"] == ["Cabs: ride status updated"]
    assert log.waits == 1  # the between-turns linger is not the Main's wait


def test_a_timed_out_wait_says_so_instead_of_pretending_progress():
    world = FakeWorld(wait_script=([], []))
    client = FakeClient(["WAIT 60", "DONE :: completed"])
    answer = run_main(client, world, "task", STAR_DOCS, EpisodeLog())

    assert answer == "completed"
    assert any("No notification arrived" in seen for seen in client.seen)


def test_a_notification_arriving_between_steps_is_delivered_unprompted():
    world = FakeWorld(drain_script=(
        [Msg("notification", "EmailClientApp: New email received")],
    ))
    client = FakeClient(["DONE :: completed"])
    run_main(client, world, "task", STAR_DOCS, EpisodeLog())

    assert any("EmailClientApp: New email received" in seen
               for seen in client.seen)


# -- the constraints are enforced, not described ----------------------------


def test_a_delegation_outside_the_topology_is_blocked_not_obeyed():
    world = FakeWorld()
    client = FakeClient(["DELEGATE Venmo :: do something",
                         "DONE :: completed"])
    log = EpisodeLog()
    run_main(client, world, "task", STAR_DOCS, log)

    assert log.delegations == 0
    assert any("cannot reach Venmo" in seen for seen in client.seen)


def test_the_delegation_target_is_soft_and_work_continues_past_it():
    tight = Constraints(roster=ROSTER, topology=Topology.STAR,
                        visibility=Visibility.DOCS,
                        delegation_budget=len(ROSTER))
    client = FakeClient(["DELEGATE Contacts :: a", "DELEGATE Cabs :: b",
                         "DELEGATE Contacts :: c", "DONE :: completed"])
    log = EpisodeLog()
    run_main(client, FakeWorld(), "task", tight, log)

    assert log.delegations == 3
    assert log.as_dict()["delegations_over_target"] == 1
    assert log.as_dict()["delegation_efficiency"] == approx(2 / 3, abs=1e-6)
    assert any("does not block further work" in seen for seen in client.seen)


def test_a_specialist_call_outside_its_app_is_refused_before_execution():
    world = FakeWorld()
    client = FakeClient(
        main_replies=[],
        specialist_replies=['CALL Cabs__order_ride :: {"where": "airport"}',
                            "FINAL: could not"])
    log = EpisodeLog()
    run_specialist(client, world, "Contacts", "order a cab", log)

    assert world.calls == [], "the out-of-app call reached the world"
    assert log.blocked == 1
    assert "Cabs__order_ride" in log.blocked_reasons[0]


# -- the honest-failure channel ---------------------------------------------


def test_fail_reaches_the_user_as_truth_not_silence():
    world = FakeWorld()
    client = FakeClient(["FAIL :: the cab app rejects every card"])
    log = EpisodeLog()
    answer = run_main(client, world, "task", STAR_DOCS, log)

    assert answer == "FAIL :: the cab app rejects every card"
    assert any("could not complete" in sent for sent in world.sent_to_user)
    assert [e["type"] for e in log.events].count("surrender") == 1


# -- multi-turn: Gaia2 schedules the follow-up after the report -------------


def test_a_follow_up_user_turn_continues_the_episode_after_done():
    world = FakeWorld(wait_script=(
        [Msg("user", "also cancel tomorrow's ride")],
        [],
    ))
    client = FakeClient(["DONE :: booked", "DONE :: cancelled"])
    log = EpisodeLog()
    answer = run_main(client, world, "book a ride", STAR_DOCS, log)

    assert answer == "cancelled"
    assert log.user_turns == 2
    assert world.sent_to_user == ["booked", "cancelled"]


# -- the OPEN control holds the tools itself --------------------------------


def test_the_open_control_calls_tools_itself_and_cannot_delegate():
    world = FakeWorld()
    client = FakeClient(['CALL Contacts__lookup :: {"name": "Kai"}',
                        "DELEGATE Contacts :: lookup Kai",
                         "DONE :: completed"])
    log = EpisodeLog()
    run_main(client, world, "task", control_for(ROSTER), log)

    assert world.calls == [("Contacts__lookup", {"name": "Kai"})]
    assert log.delegations == 0
    assert any("no specialists" in seen.lower() for seen in client.seen)


# -- model parity is wired in, not advisory ---------------------------------


def test_a_downgraded_specialist_is_refused_before_any_model_runs():
    client = FakeClient(["DONE :: completed"])
    with raises(ValueError, match="below the Main's"):
        run_main(client, FakeWorld(), "task", STAR_DOCS, EpisodeLog(),
                 model="gpt-5.6-sol", sub_model="gpt-4.1")
    assert client.seen == [], "an episode ran despite the parity violation"


def test_the_explicit_downgrade_flag_lets_the_labelled_experiment_run():
    client = FakeClient(["DONE :: completed"])
    world = FakeWorld(wait_script=([],))
    answer = run_main(client, world, "task", STAR_DOCS, EpisodeLog(),
                      model="gpt-5.6-sol", sub_model="gpt-4.1",
                      allow_sub_downgrade=True)
    assert answer == "completed"


def test_the_specialist_is_told_the_simulated_clock_not_left_to_guess():
    # Measured 2026-07-28 (star-names soft-judge run): a Cabs specialist
    # booked ride_time 2026-07-28 in a world set in 2024 -- the model's
    # knowledge of the real date filled the gap the prompt left open. Only
    # the Main was told the simulated time; now both roles are.
    client = FakeClient(main_replies=[], specialist_replies=["FINAL: noted"])
    run_specialist(client, FakeWorld(), "Cabs", "order a cab", EpisodeLog())
    specialist_system = client.systems[-1]
    assert "2026-07-28 12:00:00" in specialist_system  # FakeWorld's clock
    assert "simulated" in specialist_system


def test_the_specialist_must_do_the_doable_and_never_claim_an_outage():
    # Measured 2026-07-28 (the 'fixed' campaign): nine delegations across four
    # runs answered "the messaging tools were unavailable" with zero calls and
    # zero malformed lines -- briefs asking for scheduling or monitoring were
    # rounded down to a fabricated outage. The official harness's app-agent
    # rule 9 is the remedy (partial results + a precise named gap); this pins
    # its port.
    client = FakeClient(main_replies=[], specialist_replies=["FINAL: noted"])
    run_specialist(client, FakeWorld(), "Cabs", "order a cab", EpisodeLog())
    system = client.systems[-1]
    assert "never report your tools as unavailable" in system
    assert "name the part you could not do" in system


def test_the_main_is_told_specialists_cannot_wait_or_schedule():
    # The other half of the same finding: the refusing briefs asked for
    # "send at 07:00" and "monitor replies" -- work no specialist can do.
    # The official harness keeps all temporality with the delegating agent.
    client = FakeClient(["DONE :: completed"])
    run_main(client, FakeWorld(wait_script=([],)), "task", STAR_DOCS, EpisodeLog())
    system = client.systems[0]
    assert "cannot wait, monitor, or" in system
    assert "the clock is YOURS" in system


def test_every_agent_gets_the_same_objective_action_contract():
    """Execution semantics cannot depend on whether work is delegated.

    The audited cab trajectory treated the initial BOOKED state as a later
    update and sent a second successful message. The Main and the specialist
    must share one generic baseline/transition/exact-once contract; a cab-only
    correction would merely overfit that trajectory.
    """
    main_client = FakeClient(["DONE :: completed"])
    run_main(
        main_client,
        FakeWorld(wait_script=([],)),
        "task",
        STAR_DOCS,
        EpisodeLog(),
    )
    main_system = main_client.systems[0]

    specialist_client = FakeClient(
        main_replies=[],
        specialist_replies=["FINAL: noted"],
    )
    run_specialist(
        specialist_client,
        FakeWorld(),
        "Cabs",
        "inspect a ride",
        EpisodeLog(),
    )
    specialist_system = specialist_client.systems[-1]

    assert OBJECTIVE_ACTION_CONTRACT in main_system
    assert OBJECTIVE_ACTION_CONTRACT in specialist_system
    assert "literal rules, not suggestions" in OBJECTIVE_ACTION_CONTRACT
    assert "baseline" in OBJECTIVE_ACTION_CONTRACT
    assert "later observed transition" in OBJECTIVE_ACTION_CONTRACT
    assert "exactly once successfully" in OBJECTIVE_ACTION_CONTRACT
    assert "never repeat a successful write" in OBJECTIVE_ACTION_CONTRACT
    assert "BOOKED" not in OBJECTIVE_ACTION_CONTRACT
    assert OBJECTIVE_ACTION_CONTRACT_VERSION == "objective-actions-v1"


def test_a_zero_call_final_claiming_outage_is_rejected_and_retried():
    # Measured (the brieffix run, and 4-of-4 isolation probes on the
    # check-replies brief): this model reasons privately, sometimes imagines
    # tool calls there, and then reports "no tool calls could be executed in
    # this run". The runtime can see zero calls were made and that the tools
    # work, so the false report is rejected once, inside the same delegation.
    client = FakeClient(
        main_replies=[],
        specialist_replies=[
            "FINAL: I could not look it up because the tools were unavailable in this run.",
            'CALL Contacts__lookup :: {"name": "Kai"}',
            "FINAL: 12 Rose Lane"])
    log = EpisodeLog()
    calls: list[dict] = []
    world = FakeWorld()
    report = run_specialist(client, world, "Contacts", "find Kai", log,
                            calls_out=calls)
    assert report == "12 Rose Lane"
    assert log.false_outages == 1
    assert world.calls == [("Contacts__lookup", {"name": "Kai"})]
    assert calls[0]["status"] == "false-outage"
    assert "unavailable" in calls[0]["raw"]


def test_an_honest_cannot_know_final_is_not_mistaken_for_an_outage():
    # The rejection targets checkably false infrastructure claims only; a
    # specialist truthfully saying it cannot know something passes through
    # (and counts as a refusal, not a false outage).
    client = FakeClient(
        main_replies=[],
        specialist_replies=["FINAL: I cannot determine her address from Contacts."])
    log = EpisodeLog()
    report = run_specialist(client, FakeWorld(), "Contacts", "find address", log)
    assert report == "I cannot determine her address from Contacts."
    assert log.false_outages == 0
    assert log.refusals == 1


def test_the_refusal_counter_hears_could_not_and_unavailable():
    # The brieffix trajectory reported "I could not order the ride" with
    # refusals: 0 -- the old patterns missed the phrasing entirely.
    for phrasing in ("I could not order the ride, no service type was given.",
                     "I couldn’t check the conversations in time.",
                     "I was not able to complete the lookup."):
        log = EpisodeLog()
        client = FakeClient(main_replies=[],
                            specialist_replies=[f"FINAL: {phrasing}"])
        run_specialist(client, FakeWorld(), "Contacts", "task", log)
        assert log.refusals == 1, phrasing


def test_describe_tool_renders_the_argument_descriptions():
    # Gaia2 ships the valid enum values inside argument descriptions
    # ("service_type: type of service (Default, Premium, Van)"); the first
    # catalog formatter dropped every argument description, and a specialist
    # guessed 'default', drew ValueError, or declined. Never again.
    class Arg:
        def __init__(self, name, arg_type, description, has_default=False,
                     default=None):
            self.name, self.arg_type = name, arg_type
            self.description = description
            self.has_default, self.default = has_default, default

    class Tool:
        name = "Cabs__order_ride"
        function_description = "Orders a ride and returns the ride details."
        args = [
            Arg("start_location", "str", "starting point of the ride"),
            Arg("service_type", "str", "type of service (Default, Premium, Van)"),
            Arg("ride_time", "str | None",
                "the time of the ride in the format 'YYYY-MM-DD HH:MM:SS'.",
                has_default=True, default=None),
        ]

    text = describe_tool(Tool())
    assert "Cabs__order_ride(start_location: str, service_type: str" in text
    assert "type of service (Default, Premium, Van)" in text
    assert "YYYY-MM-DD HH:MM:SS" in text


def test_an_unparseable_specialist_line_is_recorded_not_just_corrected():
    # The audited b3 episode contained delegations whose reports claimed "no
    # tool execution was available" over zero recorded calls -- the model had
    # been emitting unparseable lines and nothing said so. Now the correction
    # loop leaves evidence.
    client = FakeClient(
        main_replies=[],
        specialist_replies=["let me call Contacts__lookup for Kai",
                            'CALL Contacts__lookup :: {"name": "Kai"}',
                            "FINAL: 12 Rose Lane"])
    log = EpisodeLog()
    calls: list[dict] = []
    run_specialist(client, FakeWorld(), "Contacts", "find Kai", log,
                   calls_out=calls)
    assert log.malformed == 1
    assert calls[0]["status"] == "malformed"
    assert "let me call" in calls[0]["raw"]
    assert calls[1]["status"] == "ok"


def test_a_malformed_control_call_leaves_a_trajectory_event():
    client = FakeClient(["CALL Contacts__lookup :: not json",
                         "DONE :: completed"])
    log = EpisodeLog()
    run_main(client, FakeWorld(), "task", control_for(ROSTER), log)
    malformed = [e for e in log.events
                 if e["type"] == "call" and e["status"] == "malformed"]
    assert len(malformed) == 1 and "not json" in malformed[0]["raw"]
    assert log.malformed == 1


# -- the trajectory serializes ----------------------------------------------


def test_the_trajectory_serializes_every_event_in_order():
    world = FakeWorld(wait_script=(
        [Msg("notification", "Cabs: ride status updated")],
        [],
    ))
    client = FakeClient(
        main_replies=["DELEGATE Contacts :: find Kai's address",
                      "WAIT 300", "DONE :: completed"],
        specialist_replies=['CALL Contacts__lookup :: {"name": "Kai"}',
                            "FINAL: 12 Rose Lane"])
    log = EpisodeLog()
    run_main(client, world, "get Kai a cab home", STAR_DOCS, log)

    types = [e["type"] for e in log.events]
    assert types == ["user", "main", "delegation", "main", "wait",
                     "notification", "main", "done", "wait"]
    delegation = log.events[2]
    assert delegation["report"] == "12 Rose Lane"
    assert delegation["calls"][0]["tool"] == "Contacts__lookup"
    assert delegation["calls"][0]["status"] == "ok"
    # The file the viewer loads is exactly this, so it must round-trip.
    serialized = json.loads(json.dumps(log.as_dict()))
    assert serialized["delegations"] == 1
    assert serialized["objective_action_contract"] == \
        OBJECTIVE_ACTION_CONTRACT_VERSION
