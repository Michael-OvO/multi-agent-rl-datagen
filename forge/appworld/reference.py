"""The reference orchestration for a task: what a competent Main would have done.

## Why these are hand-written, and what that costs

A Harbor task ships a `solution/` that proves it is solvable. For most task
families that is a replay of a recorded trajectory. These tasks have no such
thing, and the reason is the point of the whole design: the specialists are real
LLMs, so the work is not a script, and the Main's job is not to *do* the work but
to *decompose* it -- to notice that `venmo` cannot know who your roommates are
and that `phone` can.

So a reference path records only the decomposition. It asks `phone` for the
names, then hands those names to `venmo`. The specialists still do the work, and
still might do it badly.

That makes this oracle **probabilistic, not deterministic**. It is a real
weakness and it is stated rather than hidden: `solve.sh` needs an
`OPENAI_API_KEY` at verification time, costs tokens, and can fail on a bad
specialist turn. What it buys is the only thing an oracle is for -- evidence that
the task can be solved at all, so that a failing Main is failing at orchestration
rather than fighting a broken harness. Measured: 3/3 at `success=True`, 6/6
(`sweep/appworld_oracle.json`).

`harbor.py` used to assert "there is nothing to replay" and ship `exit 1`. That
was never the real objection -- these paths replay fine, they just do it with
live models. The honest objection was "nondeterministic", which is a cost to
state, not a reason to ship no solution at all.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    """One delegation. `{prev}` interpolates the previous step's report.

    That placeholder is the cross-app fact the Main is supposed to carry. A
    reference path without one is not demonstrating orchestration.
    """

    specialist: str
    brief: str


@dataclass(frozen=True)
class Reference:
    steps: tuple[Step, ...]
    #: Action tasks answer `completed`, which the sidecar converts to None.
    #: Prose here silently caps the task at 0.833 -- see server.py's _as_answer.
    answer: str = "completed"


#: Keyed by AppWorld task id. Only tasks listed here get a runnable solution;
#: the rest ship a solve.sh that fails loudly and says why, because a solution
#: that quietly does nothing is worse than none.
#:
#: The three `2a163ab` variants are one family -- like the transactions on your
#: feed involving a group only `phone` can name. They differ in the group and the
#: day, which is what makes them three tasks rather than one measured thrice.
#: **Every** brief insists on paging its list to the end -- both of them, not
#: just venmo's.
#:
#: Measured 2026-07-15 on `2a163ab_3`. First the venmo specialist liked 10 of the
#: 15 required transactions and reported success; AppWorld named the miss exactly
#: ("In right but not left: [8226, 484, 3299, 8015, 8026]"), which is only
#: readable because /state returns the failing requirements rather than a count of
#: them. Telling venmo to page the whole feed fixed that, and `_3` still failed
#: about half the time.
#:
#: The second half was the same bug one step upstream: **`phone` was dropping a
#: coworker.** Passing run -- 8 names, ending "...Robin Burton, and Timothy W".
#: Failing run -- 7, no Timothy. So venmo liked 13 instead of 15 and was correct
#: about every one of them. `_1` and `_2` never showed this because 3 roommates
#: and 3 siblings fit on one page; `_3` has 8 coworkers and does not. The flake
#: was never random -- it was one page boundary, and the brief that did not
#: mention it.
#:
#: A specialist that stops at page 1 is not wrong about what it saw. Saying how
#: far to look is the coordinator's job, which is the capability under test, so
#: it belongs in the reference.
REFERENCE_PATHS: dict[str, Reference] = {
    "2a163ab_1": Reference(steps=(
        Step("phone",
             "List the full names of all of my roommates -- only the "
             "contacts whose relationship to me is 'roommate', not my other "
             "contacts. Page through every page of the contact search "
             "(keep increasing page_index until a page comes back empty) so "
             "you do not miss any."),
        Step("venmo",
             "On my Venmo social feed, find every transaction from today that "
             "involves any of these people: {prev}. Page through the ENTIRE "
             "social feed first -- keep increasing page_index until a page comes "
             "back empty -- and collect every matching transaction before you "
             "like anything. Then like every one of them. Report how many you "
             "liked."),
    )),
    "2a163ab_2": Reference(steps=(
        Step("phone",
             "List the full names of all of my siblings -- only the "
             "contacts whose relationship to me is 'sibling', not my other "
             "contacts. Page through every page of the contact search "
             "(keep increasing page_index until a page comes back empty) so "
             "you do not miss any."),
        Step("venmo",
             "On my Venmo social feed, find every transaction from yesterday "
             "that involves any of these people: {prev}. Page through the ENTIRE "
             "social feed first -- keep increasing page_index until a page comes "
             "back empty -- and collect every matching transaction before you "
             "like anything. Then like every one of them. Report how many you "
             "liked."),
    )),
    "2a163ab_3": Reference(steps=(
        Step("phone",
             "List the full names of all of my coworkers -- only the "
             "contacts whose relationship to me is 'coworker', not my other "
             "contacts. Page through every page of the contact search "
             "(keep increasing page_index until a page comes back empty) so "
             "you do not miss any."),
        Step("venmo",
             "On my Venmo social feed, find every transaction from yesterday or "
             "today that involves any of these people: {prev}. Page through the "
             "ENTIRE social feed first -- keep increasing page_index until a "
             "page comes back empty -- and collect every matching transaction "
             "before you like anything. Then like every one of them. Report how "
             "many you liked."),
    )),
}
