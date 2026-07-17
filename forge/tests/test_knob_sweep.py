"""The sweep must measure the task that ships.

Both bugs this file guards were the same shape: the in-process sweep and the
shipped container disagreed about something, the sweep's version was more
flattering, and the number went in the write-up. `test_appworld_harbor.py`
already pins the *code* the container runs; nothing pinned the *semantics* the
sweep runs beside it.
"""

import re
from pathlib import Path

from scripts.appworld_knob_sweep import _is_action_answer

_CONTAINER = Path(__file__).resolve().parents[1] / "appworld" / "container" / "server.py"


def test_the_sweep_and_the_sidecar_agree_on_what_an_action_answer_is():
    """`_as_answer` in the container is the rule; this is the same rule.

    They diverged: the sweep also matched `liked `/`unable`/`no venmo`, read off
    the one shipped task family. Those fired on every open-control row and
    nothing else -- the control being the only arm never told the protocol --
    converting its prose to None and lifting it 0.833 -> 1.000. The ceiling every
    knob is read against was a string prefix.
    """
    src = _CONTAINER.read_text()
    m = re.search(r'if answer\.strip\(\)\.lower\(\) in \(([^)]*)\):', src)
    assert m, "container/server.py::_as_answer no longer has a literal word list"
    container_words = {w.strip().strip('"\'') for w in m.group(1).split(",") if w.strip()}

    for w in container_words:
        assert _is_action_answer(w), (
            f"the container submits {w!r} as None and the sweep does not; "
            f"the sweep is scoring a different task than the one that ships"
        )


def test_the_sweep_does_not_rescue_prose_the_container_would_submit_verbatim():
    """The retrofit, by the exact strings it used to match."""
    for prose in (
        "Liked all 4 transactions from today involving your roommates",
        "No Venmo social-feed transactions from yesterday were available",
        "Unable to complete because the phone specialist has no Venmo access",
        "Rated 5 songs",  # the spotify family the retrofit never anticipated
    ):
        assert not _is_action_answer(prose), (
            f"{prose[:40]!r} is prose; the container submits it verbatim and "
            f"`assert answers match` fails. A sweep that converts it to None "
            f"reports a score the shipped task cannot reproduce."
        )


def test_a_run_that_never_answered_submits_nothing_rather_than_its_own_marker():
    """`(out of steps)` is the harness talking, not the agent.

    Submitting it as prose fails `assert answers match` and drops a dead run to
    1/6 = 0.167 -- the pre-fix floor, which no probe measures. The do-nothing
    baseline submits None and scores 2/6 = 0.333; a dead run must be comparable
    to it.
    """
    assert _is_action_answer("(out of steps)")
    assert _is_action_answer("(error)")


def test_the_open_control_is_told_the_answer_protocol():
    """The control is the ceiling; it may not be the only arm left guessing.

    `run_main` tells the partitioned Main to answer `completed` for an action
    task. `_run_open_control` did not, so the control answered prose every time
    and only a retrofitted prefix kept it at 1.000.
    """
    src = Path(__file__).resolve().parents[1].parent / "scripts" / "appworld_knob_sweep.py"
    body = src.read_text()
    fn = body[body.index("def _run_open_control"):body.index("def run_one")]
    assert "completed" in fn, (
        "the open control is not told the answer protocol that every partitioned "
        "arm is told"
    )
