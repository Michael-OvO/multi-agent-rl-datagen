"""The Main's entire interface, and the instruction's promises about it.

The DOCS instruction told the Main to run `team docs <name>`. The client
implemented `roster`, `ask` and `done`. So the one configuration whose whole
point is that the Main can read its specialists' documentation answered
`unknown command 'docs'`, and every DOCS measurement was taken against a team
the Main could not interrogate the way it was told to.

The specific fix is the command. The general fix is
`test_every_command_the_instruction_promises_is_implemented`: the instruction and
the client are two halves of one contract, and nothing was checking they agreed.
"""

import importlib.machinery
import importlib.util
import re
from pathlib import Path

import pytest

from forge.appworld.harbor import render_instruction
from forge.appworld.partition import Constraints, Topology, Visibility

TEAM = Path(__file__).resolve().parents[1] / "appworld" / "container" / "team"

ROSTER = ("phone", "venmo")
DOCS_CONFIG = Constraints(roster=ROSTER, topology=Topology.STAR,
                          visibility=Visibility.DOCS)
NAMES_CONFIG = Constraints(roster=ROSTER, topology=Topology.STAR,
                           visibility=Visibility.NAMES)

ROSTER_REPLY = {
    "roster": ["phone", "venmo"],
    "topology": "star",
    "delegation_budget": None,
    "instruction": "Like every transaction from today.",
    "docs": {
        "phone": "phone: search_contacts, show_messages",
        "venmo": "venmo: show_transactions, like_transaction",
    },
}


def _load_team():
    """Import the `team` script, which has no .py suffix, as a module."""
    loader = importlib.machinery.SourceFileLoader("_team_under_test", str(TEAM))
    spec = importlib.util.spec_from_loader("_team_under_test", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture
def team(monkeypatch):
    mod = _load_team()
    calls = []

    def fake_call(method, path, payload=None):
        calls.append((method, path, payload))
        if path == "/roster":
            return dict(ROSTER_REPLY)
        return {"report": "did it"}

    monkeypatch.setattr(mod, "_call", fake_call)
    mod.calls = calls
    return mod


# -- the contract between the instruction and the client -------------------


def test_every_command_the_instruction_promises_is_implemented():
    for constraints in (DOCS_CONFIG, NAMES_CONFIG):
        text = render_instruction("do a thing", constraints)
        promised = set(re.findall(r"`team (\w+)", text))
        assert promised, "the instruction should name the commands at all"
        unimplemented = promised - set(_load_team().COMMANDS)
        assert not unimplemented, (
            f"the instruction tells the Main to run {sorted(unimplemented)}, "
            f"which the client does not implement"
        )


# -- team docs ------------------------------------------------------------


def test_docs_prints_the_named_specialists_documentation(team, capsys):
    assert team.main(["docs", "phone"]) == 0
    out = capsys.readouterr().out
    assert "search_contacts" in out
    assert "like_transaction" not in out, "one specialist's docs, not the team's"


def test_docs_refuses_an_unknown_specialist(team, capsys):
    assert team.main(["docs", "gmail"]) == 2
    assert "gmail" in capsys.readouterr().err


def test_docs_says_so_when_the_team_has_no_documentation(team, capsys, monkeypatch):
    # NAMES visibility: /roster carries no docs, and that is the knob working,
    # not a failure. The Main must be told which it is.
    monkeypatch.setattr(team, "_call",
                        lambda m, p, payload=None: {"roster": ["phone", "venmo"]})
    assert team.main(["docs", "phone"]) == 2
    assert "not available" in capsys.readouterr().err.lower()


def test_docs_requires_a_name(team, capsys):
    assert team.main(["docs"]) == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_help_mentions_docs(team, capsys):
    team.main(["--help"])
    assert "docs" in capsys.readouterr().out


# -- the verbs that already worked keep working ---------------------------


def test_roster_still_reports(team, capsys):
    assert team.main(["roster"]) == 0
    assert ("GET", "/roster", None) in team.calls


def test_ask_sends_the_brief(team):
    assert team.main(["ask", "venmo", "like", "everything", "from", "today"]) == 0
    assert team.calls[-1] == (
        "POST", "/ask",
        {"specialist": "venmo", "brief": "like everything from today"})


def test_done_defaults_to_completed(team):
    assert team.main(["done"]) == 0
    assert team.calls[-1] == ("POST", "/done", {"answer": "completed"})


def test_an_unknown_command_is_refused(team, capsys):
    assert team.main(["deploy"]) == 2
    assert "deploy" in capsys.readouterr().err
