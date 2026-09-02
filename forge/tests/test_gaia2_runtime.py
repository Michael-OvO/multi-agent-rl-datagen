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
from pathlib import Path

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

_FIXTURES_GAIA2 = Path(__file__).parent / "fixtures" / "gaia2"

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
    client = FakeClient(["WAIT 600", "DONE :: booked the 12:45 cab, ride 91346c"])
    log = EpisodeLog()
    answer = run_main(client, world, "order a cab", STAR_DOCS, log)

    assert answer == "booked the 12:45 cab, ride 91346c"
    assert world.waited[0] == 600
    assert any("Cabs: ride status updated" in seen for seen in client.seen), \
        "the notification never reached the Main's transcript"
    wait_events = [e for e in log.events if e["type"] == "wait"]
    assert wait_events[0]["arrived"] == ["Cabs: ride status updated"]
    assert log.waits == 1  # the between-turns linger is not the Main's wait


def test_a_timed_out_wait_says_so_instead_of_pretending_progress():
    world = FakeWorld(wait_script=([], []))
    client = FakeClient(["WAIT 60", "DONE :: booked the 12:45 cab, ride 91346c"])
    answer = run_main(client, world, "task", STAR_DOCS, EpisodeLog())

    assert answer == "booked the 12:45 cab, ride 91346c"
    assert any("No notification arrived" in seen for seen in client.seen)


def test_a_notification_arriving_between_steps_is_delivered_unprompted():
    world = FakeWorld(drain_script=(
        [Msg("notification", "EmailClientApp: New email received")],
    ))
    client = FakeClient(["DONE :: booked the 12:45 cab, ride 91346c"])
    run_main(client, world, "task", STAR_DOCS, EpisodeLog())

    assert any("EmailClientApp: New email received" in seen
               for seen in client.seen)


# -- the constraints are enforced, not described ----------------------------


def test_a_delegation_outside_the_topology_is_blocked_not_obeyed():
    world = FakeWorld()
    client = FakeClient(["DELEGATE Venmo :: do something",
                         "DONE :: booked the 12:45 cab, ride 91346c"])
    log = EpisodeLog()
    run_main(client, world, "task", STAR_DOCS, log)

    assert log.delegations == 0
    assert any("cannot reach Venmo" in seen for seen in client.seen)


def test_the_delegation_target_is_soft_and_work_continues_past_it():
    tight = Constraints(roster=ROSTER, topology=Topology.STAR,
                        visibility=Visibility.DOCS,
                        delegation_budget=len(ROSTER))
    client = FakeClient(["DELEGATE Contacts :: a", "DELEGATE Cabs :: b",
                         "DELEGATE Contacts :: c", "DONE :: booked the 12:45 cab, ride 91346c"])
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
    client = FakeClient(["DONE :: booked the ride for 12:45", "DONE :: cancelled tomorrow's ride"])
    log = EpisodeLog()
    answer = run_main(client, world, "book a ride", STAR_DOCS, log)

    assert answer == "cancelled tomorrow's ride"
    assert log.user_turns == 2
    assert world.sent_to_user == ["booked the ride for 12:45",
                                 "cancelled tomorrow's ride"]


# -- the OPEN control holds the tools itself --------------------------------


def test_the_open_control_calls_tools_itself_and_cannot_delegate():
    world = FakeWorld()
    client = FakeClient(['CALL Contacts__lookup :: {"name": "Kai"}',
                        "DELEGATE Contacts :: lookup Kai",
                         "DONE :: booked the 12:45 cab, ride 91346c"])
    log = EpisodeLog()
    run_main(client, world, "task", control_for(ROSTER), log)

    assert world.calls == [("Contacts__lookup", {"name": "Kai"})]
    assert log.delegations == 0
    assert any("no specialists" in seen.lower() for seen in client.seen)


# -- model parity is wired in, not advisory ---------------------------------


def test_a_downgraded_specialist_is_refused_before_any_model_runs():
    client = FakeClient(["DONE :: booked the 12:45 cab, ride 91346c"])
    with raises(ValueError, match="below the Main's"):
        run_main(client, FakeWorld(), "task", STAR_DOCS, EpisodeLog(),
                 model="gpt-5.6-sol", sub_model="gpt-4.1")
    assert client.seen == [], "an episode ran despite the parity violation"


def test_the_explicit_downgrade_flag_lets_the_labelled_experiment_run():
    client = FakeClient(["DONE :: booked the 12:45 cab, ride 91346c"])
    world = FakeWorld(wait_script=([],))
    answer = run_main(client, world, "task", STAR_DOCS, EpisodeLog(),
                      model="gpt-5.6-sol", sub_model="gpt-4.1",
                      allow_sub_downgrade=True)
    assert answer == "booked the 12:45 cab, ride 91346c"


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
    client = FakeClient(["DONE :: booked the 12:45 cab, ride 91346c"])
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
    main_client = FakeClient(["DONE :: booked the 12:45 cab, ride 91346c"])
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
    assert OBJECTIVE_ACTION_CONTRACT_VERSION == "objective-actions-v3"


def test_the_main_is_told_that_reporting_commits_the_turn():
    # Measured 2026-07-30: 88 of 108 fatally stopped v2 cells had messaged the
    # user first. Gaia2 counts turns by those messages and stops the world when
    # a committed turn does not match the oracle, so casual progress updates
    # were killing episodes. The contract has to say so.
    client = FakeClient(["DONE :: booked the 12:45 cab, ride 91346c"])
    run_main(client, FakeWorld(wait_script=([],)), "task", STAR_DOCS, EpisodeLog())
    system = client.systems[0]
    assert "COMMITS the work" in system
    assert "NEVER send progress updates" in system


def test_a_bare_completed_is_pushed_back_before_it_commits_the_turn():
    # The DONE text is literally what the user receives, and Gaia2's own
    # reports carry specifics ("Consultations with Vigdis Rasmussen ... have
    # been scheduled"). "completed" commits a turn with an empty report.
    client = FakeClient(["DONE :: completed",
                         "DONE :: messaged both colleagues and booked the 12:45 cab"])
    world = FakeWorld(wait_script=([],))
    log = EpisodeLog()
    answer = run_main(client, world, "task", STAR_DOCS, log)
    assert answer == "messaged both colleagues and booked the 12:45 cab"
    assert world.sent_to_user == [answer], "the thin report must never reach the user"
    assert any("says\nnothing" in s or "says nothing" in s for s in client.seen)


def test_a_notification_after_a_report_keeps_the_episode_alive():
    # The world answers a completed phase with a reply, and the next phase of
    # work hangs off it; returning at that moment abandons the task.
    client = FakeClient(["DONE :: scheduled all three consultations for Friday",
                         "DONE :: rescheduled Birgitta to 9 AM Saturday"])
    world = FakeWorld(wait_script=(
        [Msg("notification", "Calendar: attendee requested a new time")], []))
    log = EpisodeLog()
    answer = run_main(client, world, "task", STAR_DOCS, log)
    assert answer == "rescheduled Birgitta to 9 AM Saturday"
    assert len(world.sent_to_user) == 2


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
                         "DONE :: booked the 12:45 cab, ride 91346c"])
    log = EpisodeLog()
    run_main(client, FakeWorld(), "task", control_for(ROSTER), log)
    malformed = [e for e in log.events
                 if e["type"] == "call" and e["status"] == "malformed"]
    assert len(malformed) == 1 and "not json" in malformed[0]["raw"]
    assert log.malformed == 1


def test_a_call_with_trailing_commentary_still_executes():
    # 96 of the 108 malformed lines in the v3 campaign were a correct tool
    # name and valid JSON followed by the model reasoning on the same line:
    #   CALL Emails__search_emails :: {"query":"Kare Jensen"} disallowed? No.
    # Rejecting those measured whether a reasoning model can suppress its own
    # commentary -- not any of the three abilities under test. The arguments
    # end where their JSON object closes; what follows is noise, not protocol.
    client = FakeClient(
        main_replies=[],
        specialist_replies=[
            'CALL Contacts__lookup :: {"name": "Kai"} disallowed? No, continue.',
            "FINAL: 12 Rose Lane"])
    log = EpisodeLog()
    calls: list[dict] = []
    run_specialist(client, FakeWorld(), "Contacts", "find Kai", log,
                   calls_out=calls)
    assert log.malformed == 0
    assert calls[0]["status"] == "ok"
    assert calls[0]["args"] == {"name": "Kai"}


def test_trailing_commentary_recovery_respects_braces_inside_strings():
    # The recovery scan must know that a brace inside a JSON string is data,
    # not structure -- otherwise it truncates the object at the wrong depth
    # and mangles the arguments it was trying to save.
    client = FakeClient(
        main_replies=[],
        specialist_replies=[
            'CALL Contacts__lookup :: {"name": "Br{ce} Kai"} hmm {thinking}',
            "FINAL: 12 Rose Lane"])
    log = EpisodeLog()
    calls: list[dict] = []
    run_specialist(client, FakeWorld(), "Contacts", "find Kai", log,
                   calls_out=calls)
    assert log.malformed == 0
    assert calls[0]["args"] == {"name": "Br{ce} Kai"}


def test_a_control_call_with_multiline_commentary_still_executes():
    # The Main-level CALL goes through the same parser, and the trailing
    # thought often arrives on its own line -- the regex spans newlines.
    client = FakeClient([
        'CALL Contacts__lookup :: {"name": "Kai"}\nWait, is that the right one?',
        "DONE :: booked the 12:45 cab, ride 91346c"])
    log = EpisodeLog()
    run_main(client, FakeWorld(), "task", control_for(ROSTER), log)
    assert log.malformed == 0
    ok = [e for e in log.events if e["type"] == "call" and e["status"] == "ok"]
    assert len(ok) == 1 and ok[0]["args"] == {"name": "Kai"}


def test_truncated_json_is_still_corrected_not_guessed_at():
    # Recovery only fires when a complete object is actually there. A call
    # cut off mid-arguments has no faithful reading, and inventing one would
    # execute a tool with arguments the model never finished stating.
    client = FakeClient(
        main_replies=[],
        specialist_replies=['CALL Contacts__lookup :: {"name": ',
                            'CALL Contacts__lookup :: {"name": "Kai"}',
                            "FINAL: 12 Rose Lane"])
    log = EpisodeLog()
    calls: list[dict] = []
    run_specialist(client, FakeWorld(), "Contacts", "find Kai", log,
                   calls_out=calls)
    assert log.malformed == 1
    assert calls[0]["status"] == "malformed"
    assert calls[1]["status"] == "ok"


# -- the trajectory serializes ----------------------------------------------


def test_the_trajectory_serializes_every_event_in_order():
    world = FakeWorld(wait_script=(
        [Msg("notification", "Cabs: ride status updated")],
        [],
    ))
    client = FakeClient(
        main_replies=["DELEGATE Contacts :: find Kai's address",
                      "WAIT 300", "DONE :: booked the 12:45 cab, ride 91346c"],
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


def _outage_corpus():
    corpus = json.loads(
        (_FIXTURES_GAIA2 / "outage_corpus.json").read_text())
    return corpus["fabrications"], corpus["honest"]


def test_the_outage_detector_hears_every_corpus_fabrication():
    # The corpus is fixtures/gaia2/outage_corpus.json: every zero-call FINAL
    # from the paid campaigns that fabricates an infrastructure outage,
    # verbatim. The v5 miss was consequential -- the economy arm failed
    # *because* of a fabricated outage while recording false_outages: 0.
    # Triage for new wordings happens in the evidence files: each campaign's
    # *_credit.json lists the zero-call reports the detector did not flag;
    # new fabrications get appended to the corpus, and this test forces the
    # matcher to keep up.
    fabrications, _ = _outage_corpus()
    assert len(fabrications) >= 17, "corpus shrank?"
    for final in fabrications:
        client = FakeClient(
            main_replies=[],
            specialist_replies=[f"FINAL: {final}",
                                'CALL Contacts__lookup :: {"name": "Kai"}',
                                "FINAL: 12 Rose Lane"])
        log = EpisodeLog()
        report = run_specialist(client, FakeWorld(), "Contacts", "find Kai",
                                log)
        assert log.false_outages == 1, f"missed fabrication: {final[:60]}"
        assert report == "12 Rose Lane"


def test_honest_corpus_wordings_stay_unflagged():
    # The other half of the same corpus, and the reason the detector cannot
    # simply get greedier: these are true statements about missing data or
    # capability, which the prompt explicitly asks for. Flagging them would
    # reject honesty and demand the specialist fabricate an attempt.
    _, honest = _outage_corpus()
    assert len(honest) >= 13, "corpus shrank?"
    for final in honest:
        client = FakeClient(main_replies=[],
                            specialist_replies=[f"FINAL: {final}"])
        log = EpisodeLog()
        report = run_specialist(client, FakeWorld(), "Contacts", "check", log)
        assert log.false_outages == 0, f"honest report flagged: {final[:60]}"
        assert report == final


def test_no_prompt_advertises_a_token_its_own_guard_rejects():
    # The class-guard for prompt/guard contradictions. The Main's verb menu
    # taught `DONE :: ... or 'completed' if the task was an action`, and the
    # thin-report guard then rejected exactly that token -- a fixed
    # one-turn tax on 13 of 20 v4 episodes and 9 of 12 v5 episodes, paid
    # for following the instructions verbatim. A prompt and a guard written
    # by hand in two places will drift again; this pins the whole class:
    # nothing a prompt displays as an acceptable output may draw a
    # correction from the runtime's own validators.
    from forge.gaia2.runtime import _THIN_REPORTS, _main_system, _specialist_system

    world = FakeWorld()
    prompts = {
        "main": _main_system(world, STAR_DOCS, None),
        "main-open": _main_system(world, control_for(ROSTER),
                                  {a: world.catalog(a) for a in ROSTER}),
        "specialist": _specialist_system(world, ("Contacts",)),
    }
    for name, prompt in prompts.items():
        for token in _THIN_REPORTS:
            if not token:
                continue
            for quoted in (f"'{token}'", f'"{token}"'):
                assert quoted not in prompt, (
                    f"the {name} prompt advertises {quoted} as acceptable "
                    f"output, but _THIN_REPORTS rejects it -- the model pays "
                    f"a correction turn for obeying the prompt"
                )


def test_the_zero_call_census_separates_flagged_from_unflagged():
    # The triage feed. Every campaign's credit evidence lists the zero-call
    # reports the detector did NOT flag, so a novel fabrication wording
    # surfaces in the next seed's evidence file instead of waiting for a
    # third review round to find it. Flagged ones are counted, not listed --
    # they are already handled.
    from forge.gaia2.runtime import zero_call_census

    events = [
        {"type": "delegation", "specialist": "Messages",
         "calls": [{"tool": None, "args": None, "status": "false-outage"}],
         "report": "no tool-call execution opportunity was available in this run"},
        {"type": "delegation", "specialist": "Contacts",
         "calls": [],
         "report": "I cannot determine her address from Contacts."},
        {"type": "delegation", "specialist": "Cabs",
         "calls": [{"tool": "Cabs__order_ride", "args": {}, "status": "ok"}],
         "report": "ordered the 12:45 cab"},
        {"type": "main", "content": "DONE :: done it"},
    ]
    flagged, unflagged = zero_call_census(events)
    assert flagged == 1
    assert unflagged == ["I cannot determine her address from Contacts."]


def test_the_main_is_told_what_a_delegation_costs_in_time():
    # The one replicated constraint effect in v4 and v5: context and economy
    # both ordered a correct cab ~60-75 seconds late, because after observing
    # three minutes of silence they spent one more delegation re-verifying
    # the silence. A delegation round-trip consumes tens of simulated seconds
    # while both models think -- and no prompt ever said so. The agent
    # cannot budget a cost it was never told exists.
    from forge.gaia2.runtime import _main_system

    constrained = _main_system(FakeWorld(), STAR_DOCS, None)
    assert "30-60 seconds" in constrained, \
        "the Main prompt never states the time cost of a delegation"
    assert "already observed" in constrained, \
        "the Main prompt never warns against re-verifying observed silence"
    # The open control has no specialists, so the costing does not apply.
    open_prompt = _main_system(FakeWorld(), control_for(ROSTER),
                               {a: FakeWorld().catalog(a) for a in ROSTER})
    assert "30-60 seconds" not in open_prompt


# -- the stop is the most common outcome, and it must say why ---------------


def test_a_stop_event_records_the_world_s_own_reason():
    # Measured 2026-08-29 over sweep/gaia2_credit.json and
    # sweep/gaia2_v3_credit.json: 201 of 249 soft-judged rollouts ended at
    # "(environment stopped)" rather than at an answer, and not one records
    # why -- `log.event(world, "stop")` wrote a type and a timestamp and
    # nothing else. The reason is already in our hands when we write that
    # row: ARE's stop notification carries "Environment stopped with state
    # <STATE>", and _deliver was dropping the text on the floor. Without it
    # a clean end and a validation failure are the same row.
    world = FakeWorld(drain_script=(
        [Msg("stop", "Environment stopped with state FAILED")],))
    log = EpisodeLog()

    answer = run_main(FakeClient([]), world, "task", STAR_DOCS, log)

    assert answer == "(environment stopped)"
    stops = [e for e in log.events if e["type"] == "stop"]
    assert len(stops) == 1
    assert stops[0]["reason"] == "Environment stopped with state FAILED"


def test_a_stop_event_records_the_world_clock_when_the_world_keeps_one():
    # Whether the episode died against its horizon or long before it is the
    # whole diagnosis, and the row cannot carry it without the clock: the
    # same campaign shows stopped episodes ending at a median 313 simulated
    # seconds while finished ones ran to 992.
    class TimedWorld(FakeWorld):
        def clock_facts(self):
            return {"duration": 1000.0, "time_passed": 313.0, "remaining": 687.0}

    world = TimedWorld(drain_script=(
        [Msg("stop", "Environment stopped with state STOPPED")],))
    log = EpisodeLog()

    run_main(FakeClient([]), world, "task", STAR_DOCS, log)

    stop = [e for e in log.events if e["type"] == "stop"][0]
    assert stop["duration"] == 1000.0
    assert stop["time_passed"] == 313.0
    assert stop["remaining"] == 687.0


def test_a_world_that_keeps_no_clock_still_logs_its_stop():
    # The world is duck-typed on purpose (module docstring); a substrate that
    # exposes no clock must still record the stop, not crash on the way out.
    world = FakeWorld(drain_script=([Msg("stop", "done")],))
    log = EpisodeLog()

    run_main(FakeClient([]), world, "task", STAR_DOCS, log)

    stop = [e for e in log.events if e["type"] == "stop"][0]
    assert stop["reason"] == "done"
    assert "duration" not in stop


def test_the_one_real_world_implements_the_clock_contract():
    # `forge/tests` cannot import are_world -- it needs `are.*`, which the
    # pinned main environment deliberately does not carry (that module's
    # docstring says why) -- so the duck-typed contract is guarded
    # structurally instead. Without this, deleting AreWorld.clock_facts
    # would silently return every stop row to being clockless and nothing
    # in this suite would fail.
    import ast

    source = Path(__file__).parents[1] / "gaia2" / "are_world.py"
    world = next(node for node in ast.walk(ast.parse(source.read_text()))
                 if isinstance(node, ast.ClassDef) and node.name == "AreWorld")
    methods = {n.name for n in world.body if isinstance(n, ast.FunctionDef)}
    assert "clock_facts" in methods, \
        "AreWorld must expose clock_facts(); runtime._clock_facts reads it"


def test_the_contract_forbids_embellishing_a_tool_call_s_arguments():
    # Measured over the v6 campaign (2026-08-30, workers=1): the soft judge
    # scored 0 of 107, and 93% of those failures name an oracle call the
    # agent never made. It never made them because the scenario graph gates
    # the environment's replies on the agent's earlier calls MATCHING the
    # oracle -- adaptability scenarios schedule "Luisa replies you are
    # mistaken" with deps=[OracleEvent]. In scenario_universe_21_44vlco the
    # gate was one Calendar__add_calendar_event: the oracle carries
    # title="Photoshoot with Sheryl's Sweets" and empty tag/description/
    # location, the Main sent "Sheryl's Sweets Photoshoot" plus a tag, a
    # description and a location it inferred, and the judge answered "tool
    # judge reject". Luisa never replied, four downstream oracle events
    # became unreachable, and the episode scored zero for work it was never
    # given the chance to do.
    #
    # The contract already governs WHETHER to act. Nothing governed the
    # shape of the arguments, so a helpful Main forfeited the episode by
    # being helpful. This is the world's convention, not any task's answer.
    assert "only the fields the user specified" in OBJECTIVE_ACTION_CONTRACT, \
        "the contract never tells the Main to leave unspecified fields empty"
    assert "user's own wording" in OBJECTIVE_ACTION_CONTRACT, \
        "the contract never tells the Main to mirror rather than paraphrase"
    # Versioned because a prompt change re-prices every comparison: v6 and
    # anything after it must not read as the same experiment.
    assert OBJECTIVE_ACTION_CONTRACT_VERSION == "objective-actions-v3"


def test_the_contract_pins_values_the_user_or_a_tool_already_gave():
    # The v6 rejection surface, field by field across all 32 distinct cases:
    # 28 prose, 12 structured values, 4 invented-empty, 2 capitalisation, 2
    # over-qualified. v2 covered the invented-empty four. These are the rest
    # of the structured ones, each from a measured case:
    #   u21_x1l1om  attendees   oracle ['Luis Pimentel']
    #                           agent  ['Luis Pimentel <lpimentel@bistroporto.com>']
    #   u21_kgqyjr  end_location oracle 'Malmohusvagen 34, Malmo'
    #                           agent  'Malmohusvagen 34, 211 18 Malmo'  (postcode added)
    #   u24_tmxihx  start_location oracle 'Home'   agent 'My home'
    #   u24_4pjsme  location    oracle 'Local cafe'  agent 'local cafe'
    #   u22_6wkrhc  user_ids    oracle two numbers; agent added the user's own
    assert "exactly as it was given" in OBJECTIVE_ACTION_CONTRACT, \
        "nothing tells the Main to pass a supplied value through unchanged"
    assert "anyone the user did not name" in OBJECTIVE_ACTION_CONTRACT, \
        "nothing forbids padding a recipient list or a group"


def test_the_contract_bounds_what_a_message_body_may_contain():
    # u24_4pjsme reply_to_email, the clearest measured case. Oracle body:
    #   "I am free to meet you on October 19, 2024 at 2pm for two hours at
    #    the local cafe; does this time work for you? ..."
    # Agent body: a greeting, "I would be happy to discuss this with you",
    # the same substance with 2pm-for-two-hours restyled to "2:00 PM to
    # 4:00 PM", and "Best regards, Ursula". Semantically identical, rejected.
    #
    # Deliberately NOT a rule against greetings: 10 of the 15 oracle bodies
    # measured DO greet. What separates them is length and restyling, so
    # that is what the rule names.
    assert "only what the user asked you to convey" in OBJECTIVE_ACTION_CONTRACT, \
        "nothing bounds the body to the substance the user asked for"
    assert OBJECTIVE_ACTION_CONTRACT_VERSION == "objective-actions-v3"
