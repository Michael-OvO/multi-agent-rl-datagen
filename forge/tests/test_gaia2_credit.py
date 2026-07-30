"""Partial credit and pivots, pinned against the campaign that motivated them.

126 of 131 full-campaign cells failed, yet their trajectories hold correct
prefixes a group-relative optimizer would punish wholesale. These tests pin
the two escapes: a graded, monotone partial reward (doing more gold writes
never scores less) and a located first-fault pivot for prefix replay.
"""

from forge.gaia2.credit import assess, split_for_replay


def _scenario(writes):
    return {"metadata": {"definition": {"scenario_id": "s"}}, "apps": [],
            "events": [
                {"class_name": "OracleEvent", "event_type": "AGENT",
                 "action": {"app": app, "function": fn,
                            "args": [{"name": n, "value": v} for n, v in args]}}
                for app, fn, args in writes]}


GOLD = _scenario([
    ("Messages", "send_message",
     (("user_id", "+61412345658"), ("content", "Who's ordering?"))),
    ("Messages", "send_message",
     (("user_id", "+31652345678"), ("content", "Who's ordering?"))),
    ("Cabs", "order_ride",
     (("service_type", "Default"), ("ride_time", "2024-10-15 12:45:00"))),
])


def _call(tool, args, status="ok"):
    return {"tool": tool, "args": args, "status": status, "result": "ok"}


def _delegation(specialist, calls, report="done"):
    return {"type": "delegation", "specialist": specialist, "brief": "b",
            "report": report, "calls": calls, "sim_time": "t"}


def test_exact_matches_score_fully_and_name_matches_half():
    events = [_delegation("Messages", [
        _call("Messages__send_message",
              {"user_id": "+61412345658", "content": "Who's ordering?"}),
        _call("Messages__send_message",
              {"user_id": "+31652345678", "content": "Hi! Who is ordering?"}),
    ])]
    credit = assess(GOLD, events)
    assert credit.gold_total == 3
    assert credit.covered == 2 and credit.exact == 1
    # 1 exact + 0.5 * 1 name-only, over 3 gold writes.
    assert credit.partial_reward == (1 + 0.5) / 3


def test_doing_more_of_the_task_never_scores_less():
    some = [_delegation("Messages", [
        _call("Messages__send_message",
              {"user_id": "+61412345658", "content": "Who's ordering?"})])]
    more = some + [_delegation("Cabs", [
        _call("Cabs__order_ride",
              {"service_type": "Default", "ride_time": "2024-10-15 12:45:00"})])]
    assert assess(GOLD, more).partial_reward > assess(GOLD, some).partial_reward


def test_the_pivot_lands_on_the_first_fault_not_the_last():
    events = [
        _delegation("Messages", [_call("Messages__send_message",
            {"user_id": "+61412345658", "content": "Who's ordering?"})]),
        _delegation("Messages", [], report="I could not send: tools unavailable."),
        {"type": "surrender", "reason": "gave up", "sim_time": "t"},
    ]
    credit = assess(GOLD, events)
    assert (credit.pivot, credit.pivot_kind) == (1, "refusal")
    cut = split_for_replay(events, credit)
    assert cut == {"prefix_events": 1, "suffix_events": 2,
                   "pivot": 1, "pivot_kind": "refusal"}


def test_a_wrong_argument_gold_write_is_the_fault_even_when_it_executes():
    # The star-names run that booked 13:45 instead of 12:45: the call
    # succeeded, the world changed, and it was still the first wrong step.
    events = [_delegation("Cabs", [
        _call("Cabs__order_ride",
              {"service_type": "Default", "ride_time": "2024-10-15 13:45:00"})])]
    credit = assess(GOLD, events)
    assert credit.pivot_kind == "wrong-arguments"
    assert credit.covered == 1 and credit.exact == 0


def test_a_clean_but_incomplete_trajectory_has_no_pivot():
    events = [_delegation("Messages", [_call("Messages__send_message",
        {"user_id": "+61412345658", "content": "Who's ordering?"})])]
    credit = assess(GOLD, events)
    assert credit.pivot is None
    assert split_for_replay(events, credit)["suffix_events"] == 0


def test_reworded_prose_is_scored_low_but_never_placed_as_the_pivot():
    # Validated against the hand-audited runs: exact-matching prose content
    # branded a correctly-reworded send as the first fault, ahead of the
    # real one. Structured args (numbers, datetimes, enums) place pivots;
    # prose only lowers the fidelity score.
    events = [_delegation("Messages", [
        _call("Messages__send_message",
              {"user_id": "+61412345658", "content": "Hi! Who is ordering today?"}),
    ])]
    credit = assess(GOLD, events)
    assert credit.pivot is None          # right number, reworded prose
    assert credit.covered == 1 and credit.exact == 0  # floor still conservative

    wrong_number = [_delegation("Messages", [
        _call("Messages__send_message",
              {"user_id": "+9999", "content": "Who's ordering?"})])]
    assert assess(GOLD, wrong_number).pivot_kind == "wrong-arguments"


def test_probe_errors_are_not_faults():
    # Reading a ValueError off list_rides is how specialists learned the
    # service types; discovery must not be branded the first mistake.
    events = [_delegation("Cabs", [
        _call("Cabs__list_rides", {"ride_time": "bad"}, status="error"),
        _call("Cabs__order_ride",
              {"service_type": "Default", "ride_time": "2024-10-15 12:45:00"}),
    ])]
    assert assess(GOLD, events).pivot is None
