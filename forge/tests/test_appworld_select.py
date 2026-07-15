"""The selection rule is the anti-toy guard. These tests pin it.

Measured against real AppWorld ground truth on 2026-07-15: counting `supervisor`
as a collaborator rates 147/147 tasks "multi-agent"; excluding the submit channel
rates 51/147. The 96-task difference is single-app puzzles that would ship with a
decorative second specialist and measure nothing. If these tests are ever
loosened, that is what comes back.
"""

from forge.appworld.select import (
    MIN_ROSTER,
    derive_roster,
    parse_calls,
    span_of,
    usable,
)

# Shape of a real AppWorld ground-truth solution (2a163ab_1: roommates/venmo).
_REAL_GT = """
def _solution(main_user, apis, requester, public_data):
    phone_token = apis.phone.access_token_from(main_user)
    contacts = apis.phone.search_contacts(access_token=phone_token)
    venmo_token = apis.venmo.access_token_from(main_user)
    feed = apis.venmo.show_social_feed(access_token=venmo_token)
    apis.venmo.like_transaction(transaction_id=1)
    return answer

def solution(main_user, apis, requester, public_data):
    answer = _solution(main_user, apis, requester, public_data)
    apis.supervisor.complete_task(answer=answer, status="success")
"""

# A single-app task. Every AppWorld task calls supervisor.complete_task, so this
# one looks like two apps to a naive filter and is really one.
_SINGLE_APP_GT = """
def _solution(main_user, apis, requester, public_data):
    token = apis.spotify.access_token_from(main_user)
    return apis.spotify.show_song(song_id=1)

def solution(main_user, apis, requester, public_data):
    answer = _solution(main_user, apis, requester, public_data)
    apis.supervisor.complete_task(answer=answer, status="success")
"""


def test_parse_calls_finds_app_and_api():
    calls = parse_calls(_REAL_GT)
    assert ("phone", "search_contacts") in calls
    assert ("venmo", "like_transaction") in calls
    assert ("supervisor", "complete_task") in calls


def test_submit_channel_is_not_a_specialist():
    # THE anti-toy assertion. supervisor.complete_task appears in all 147
    # ground-truth tasks and carries no information between apps.
    assert "supervisor" not in derive_roster(_SINGLE_APP_GT)


def test_single_app_task_is_dropped_not_padded():
    span = span_of("x_1", "train", "Show me a song.", _SINGLE_APP_GT)
    assert span.roster == ("spotify",)
    assert not span.usable, "a one-app task has no coordination to test"
    assert usable([span]) == []


def test_roster_comes_from_the_task_not_from_us():
    span = span_of("2a163ab_1", "train", "Like roommates' transactions.", _REAL_GT)
    assert span.roster == ("phone", "venmo")
    assert span.usable


def test_roster_is_order_independent():
    # A task must render identically regardless of the order its GT happens to
    # call apps in, or the same task becomes two different tasks across runs.
    swapped = _REAL_GT.replace("phone", "TMP").replace("venmo", "phone").replace("TMP", "venmo")
    assert derive_roster(_REAL_GT) == derive_roster(swapped)


def test_api_docs_is_not_a_specialist():
    gt = "apis.api_docs.show_api_descriptions(app_name='phone')\napis.phone.login()\napis.venmo.login()"
    assert "api_docs" not in derive_roster(gt)


def test_supervisor_would_count_if_it_carried_real_data():
    # Only the submit channel is infrastructure. If a task genuinely reads data
    # from supervisor, that IS a coordination edge and must count -- otherwise
    # the filter would silently drop real work.
    gt = "apis.supervisor.show_account_passwords()\napis.spotify.login()"
    assert derive_roster(gt) == ("spotify", "supervisor")


def test_min_roster_is_two():
    assert MIN_ROSTER == 2
