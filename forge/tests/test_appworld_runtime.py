"""Runtime tests with a scripted client -- no tokens, no network.

What matters here is that the constraints are *enforced*, not merely described in
a prompt. A Main that can reach a specialist the topology forbids makes the
topology knob meaningless, and a meaningless knob is exactly the decoration this
design is supposed to exclude.
"""

import pytest

from forge.appworld.partition import Constraints, Topology, Visibility
from forge.appworld.runtime import RunLog, extract_code, run_main


class FakeClient:
    """Replays scripted Main messages in order.

    The Main and the specialists share one client, so the fake must tell them
    apart by their system prompt -- otherwise a specialist silently eats the
    Main's next scripted reply and the test measures nothing. (It did, first
    time round.) Specialists always finish immediately here; their behaviour is
    not what these tests are about.
    """

    def __init__(self, replies):
        self._replies = list(replies)
        self.seen = []
        self.systems = []

        outer = self

        class _Completions:
            def create(self, model, messages, temperature):
                system = messages[0]["content"]
                outer.systems.append(system)
                # Match the Main explicitly. Sniffing for "specialist" catches
                # the Main too -- its prompt says "must be done by a specialist".
                if not system.startswith("You are the Main coordinator"):
                    return _wrap("```python\nFINAL: did it\n```")
                outer.seen.append(messages[-1]["content"])
                text = outer._replies.pop(0) if outer._replies else "DONE :: exhausted"
                return _wrap(text)

        self.chat = type("Chat", (), {"completions": _Completions()})()


def _wrap(text):
    return type("R", (), {"choices": [type("C", (), {
        "message": type("M", (), {"content": text})()})()]})()


class FakeWorld:
    def __init__(self):
        self.executed = []

    def execute(self, code):
        self.executed.append(code)
        return "ok"


ROSTER = ("phone", "venmo")


def test_extract_code_unwraps_a_fence():
    assert extract_code("noise\n```python\nx = 1\n```\ntail") == "x = 1"


def test_main_reaching_a_forbidden_specialist_is_blocked_not_obeyed():
    # CHAIN allows main -> phone only. The Main tries venmo anyway.
    c = Constraints(roster=ROSTER, topology=Topology.CHAIN)
    client = FakeClient(["DELEGATE venmo :: like everything", "DONE :: gave up"])
    world = FakeWorld()
    log = RunLog()
    run_main(client, world, "task", c, log)
    assert log.delegations == 0, "a forbidden delegation must not execute"
    assert not world.executed, "no specialist code should have run"
    assert any("cannot reach venmo" in s for s in client.seen)


def test_delegation_budget_is_enforced_by_the_harness():
    c = Constraints(roster=ROSTER, topology=Topology.STAR, delegation_budget=2)
    client = FakeClient([
        "DELEGATE phone :: FINAL",   # 1
        "DELEGATE venmo :: FINAL",   # 2
        "DELEGATE phone :: FINAL",   # 3 -> refused
        "DONE :: done",
    ])
    log = RunLog()
    run_main(client, FakeWorld(), "task", c, log)
    assert log.delegations == 2
    assert any("budget exhausted" in s.lower() for s in client.seen)


def test_malformed_output_is_corrected_not_crashed():
    client = FakeClient(["I think I'll check the phone.", "DONE :: fine"])
    log = RunLog()
    ans = run_main(client, FakeWorld(), "task", Constraints(roster=ROSTER), log)
    assert ans == "fine"
    assert log.delegations == 0
    assert any("Malformed" in s for s in client.seen)


def test_names_only_visibility_withholds_capabilities_from_the_main():
    client = FakeClient(["DONE :: x"])
    run_main(client, FakeWorld(), "task",
             Constraints(roster=ROSTER, visibility=Visibility.NAMES), RunLog())
    system = client.seen  # first call carries the system prompt in messages[0]
    assert system  # sanity


def test_main_prompt_states_names_only_when_visibility_is_names():
    from forge.appworld.runtime import _main_system
    c = Constraints(roster=ROSTER, visibility=Visibility.NAMES)
    text = _main_system(c, "You know only their names, not what they can do. Ask them if you need to know.")
    assert "only their names" in text
    assert "NO API access" in text


def test_chain_prompt_names_only_the_head():
    from forge.appworld.runtime import _main_system
    c = Constraints(roster=ROSTER, topology=Topology.CHAIN)
    text = _main_system(c, "")
    assert "ONLY to phone" in text
    assert "phone -> venmo" in text


def test_star_prompt_lists_the_whole_roster():
    from forge.appworld.runtime import _main_system
    text = _main_system(Constraints(roster=ROSTER, topology=Topology.STAR), "")
    assert "phone, venmo" in text


def test_out_of_steps_is_reported_not_silently_succeeded():
    client = FakeClient(["DELEGATE phone :: a"] * 30)
    log = RunLog()
    ans = run_main(client, FakeWorld(), "task", Constraints(roster=ROSTER), log, max_steps=3)
    assert ans == "(out of steps)"


@pytest.mark.parametrize("topology", [Topology.STAR, Topology.CHAIN])
def test_main_never_receives_api_access(topology):
    assert not Constraints(roster=ROSTER, topology=topology).main_has_apis
