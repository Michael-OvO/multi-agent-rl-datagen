"""The seam analysis must find the shapes AppWorld's ground truth actually uses.

Each of these is a shape that made a naive pass report zero seams on the shipped
task family -- i.e. would have said the only tasks this repo has ever rendered
are decoration.
"""

import json
from pathlib import Path

from forge.appworld.seams import has_information_seam, seams_of

_ROOT = Path(__file__).resolve().parents[2]
_DATA = _ROOT / "appworld_data" / "tasks"

import pytest

_has_data = _DATA.exists()


# -- the shapes ---------------------------------------------------------------


def test_a_fact_reaching_another_apps_arguments_is_a_seam():
    code = """
def solution(apis):
    names = apis.phone.search_contacts(query="roommate")
    apis.venmo.search(query=names)
"""
    seams = seams_of(code)
    assert [(s.source, s.target, s.via) for s in seams] == [("phone", "venmo", "argument")]


def test_a_fact_reaching_only_a_guard_clause_is_still_a_seam():
    """The shape every shipped task uses, and the one a naive pass misses.

    The guarded call is not inside the `if` -- the `if` body is a bare `continue`
    and the call comes after it. Looking at enclosing `if` bodies finds nothing
    here.
    """
    code = """
def solution(apis):
    emails = apis.phone.search_contacts(query="roommate")
    for entry in apis.venmo.show_social_feed():
        if entry.sender.email not in emails:
            continue
        apis.venmo.like_transaction(transaction_id=entry.id)
"""
    seams = seams_of(code)
    assert [(s.source, s.target, s.via) for s in seams] == [("phone", "venmo", "guard")]


def test_an_api_handed_to_a_helper_is_still_that_app():
    """`find_all_from_pages(apis.phone.search_contacts, ...)` never calls it.

    select.py's regex needs a paren right after the method name and misses this;
    `phone` makes 2a163ab_1's roster only because `access_token_from` happens to
    be called directly elsewhere.
    """
    code = """
def solution(apis):
    names = find_all_from_pages(apis.phone.search_contacts, query="roommate")
    apis.venmo.search(query=names)
"""
    assert has_information_seam(code)


def test_taint_survives_a_helper_call():
    code = """
def solution(apis):
    people = apis.phone.search_contacts(query="roommate")
    emails = list_of(people, "email")
    apis.venmo.search(query=emails)
"""
    assert has_information_seam(code)


def test_two_apps_that_never_exchange_a_fact_are_not_a_seam():
    """An operation seam: both worked, nothing crossed. Roles would decorate it."""
    code = """
def solution(apis):
    apis.phone.set_alarm(time="08:00")
    apis.venmo.pay(user="alice", amount=5)
"""
    assert seams_of(code) == []
    assert not has_information_seam(code)


def test_an_app_feeding_only_itself_is_not_a_seam():
    code = """
def solution(apis):
    feed = apis.venmo.show_social_feed()
    for entry in feed:
        apis.venmo.like_transaction(transaction_id=entry.id)
"""
    assert seams_of(code) == []


def test_the_submit_channel_is_not_a_source():
    """supervisor carries credentials and the answer, never a fact between apps."""
    code = """
def solution(apis):
    profile = apis.supervisor.show_profile()
    token = apis.venmo.login(username=profile["email"])
    apis.venmo.pay(user="alice", amount=5, access_token=token)
"""
    assert seams_of(code) == []


def test_unparseable_ground_truth_reports_nothing_rather_than_crashing():
    assert seams_of("def solution(:  syntax error") == []


# -- against the corpus -------------------------------------------------------


def _gt(task_id: str) -> str:
    return (_DATA / task_id / "ground_truth" / "solution.py").read_text()


@pytest.mark.skipif(not _has_data, reason="appworld_data not downloaded")
@pytest.mark.parametrize("task_id", ["2a163ab_1", "2a163ab_2", "2a163ab_3"])
def test_every_shipped_task_has_the_seam_it_is_shipped_for(task_id):
    """If this goes red, the tasks in tasks/ are decoration and nothing else in
    the repo would say so."""
    seams = seams_of(_gt(task_id))
    assert [(s.source, s.target) for s in seams] == [("phone", "venmo")], (
        f"{task_id} ships as a phone->venmo coordination task and its ground "
        f"truth does not cross that seam: {seams}"
    )


@pytest.mark.skipif(not _has_data, reason="appworld_data not downloaded")
def test_the_seam_filter_is_stricter_than_the_roster_filter():
    """The measurement that motivated this module: 51 multi-app, 39 that coordinate.

    `select.py` keeps a task when its ground truth touches >= 2 apps and its
    docstring says a task that cannot be coordinated is dropped. 12 of the 51 it
    keeps never move a fact between their apps.
    """
    spans = json.loads((_ROOT / "sweep" / "appworld_span.json").read_text())
    multi = [s for s in spans if len(s["roster"]) >= 2]
    with_seam = [s for s in multi if has_information_seam(_gt(s["task_id"]))]

    assert len(multi) == 51, f"select.py's filter moved: {len(multi)}"
    assert len(with_seam) == 39, (
        f"the seam count moved to {len(with_seam)}; the report states 39 and "
        f"every claim about the usable corpus size rests on it"
    )
    assert len(with_seam) < len(multi), "the seam filter must be the stricter one"
