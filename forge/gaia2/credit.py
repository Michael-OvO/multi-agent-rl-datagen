"""Partial credit and pivot points: the reward-formation layer.

The binary verdict is a terrible training signal on its own, and the full
campaign measured exactly why: 126 of 131 cells failed, yet their
trajectories are full of correct prefixes -- rosters navigated, seams
carried, cabs booked at the right minute -- that a group-relative,
critic-free optimizer (group relative policy optimization and kin) would
punish wholesale because the episode's one number is 0. The practitioner
literature calls this the credit-assignment wall of agentic reinforcement
learning and offers two escapes this module implements as *data
annotations*:

  * **Partial credit.** A graded reward floor computed from the gold
    writes: how many did the agent perform at all (coverage), and how many
    with exactly the gold arguments (fidelity). The floor is deliberately
    conservative -- exact string comparison undercounts what a soft judge
    would accept -- but it is deterministic, judge-free, and monotone:
    doing more of the task never scores less. The one rule that matters
    (Explained Variance Policy Optimization's finding): a partial signal
    must beat the group-mean baseline, and "did more gold writes" does.

  * **The pivot (cut point).** The first event where the trajectory went
    wrong -- a fabricated outage, a blocked call, a refusal, a gold write
    with wrong arguments -- located so training can replay everything
    before it as frozen prompt (prefix replay) and spend optimization only
    on the suffix, where the error actually lives. Pivot-style prefix
    replay is the cheap end of the family (tree rollouts with pivot-node
    search are the expensive end); the annotation supports both, since a
    pivot index over a recorded trajectory is exactly a branch point.

Nothing here touches the judge or the verdict. The verdict stays the
benchmark's own; these fields ride beside it, labelled as shaping.
"""

from __future__ import annotations

from dataclasses import dataclass

from forge.gaia2.mine import gold_writes

#: Call statuses that mark a fault at the moment they happen. Execution
#: errors ("error") are deliberately absent: probing a tool and reading its
#: ValueError is legitimate discovery (the catalogfix runs learned service
#: types exactly that way), so an error is evidence only when nothing
#: recovers -- which the later fault kinds already capture.
_FAULT_STATUSES = ("malformed", "false-outage", "refused")

#: Report phrasings that mark a zero-call delegation as a refusal fault.
_REFUSAL_WORDS = ("unavailable", "could not", "couldn't", "cannot",
                  "unable", "was not able", "no way")


@dataclass(frozen=True)
class Credit:
    """The annotation stamped beside a trajectory's verdict."""

    gold_total: int
    #: Gold writes the agent performed at all, matched by tool name as a
    #: multiset (two asks need two sends), regardless of arguments.
    covered: int
    #: Covered writes whose string arguments all equal gold's exactly --
    #: the conservative floor beneath any soft judge's semantics.
    exact: int
    #: Index into the trajectory's events of the first fault, or None for a
    #: fault-free trajectory (which may still have failed -- a missing gold
    #: write has no event to point at).
    pivot: int | None
    pivot_kind: str | None

    @property
    def coverage(self) -> float:
        return self.covered / self.gold_total if self.gold_total else 0.0

    @property
    def fidelity(self) -> float:
        return self.exact / self.gold_total if self.gold_total else 0.0

    @property
    def partial_reward(self) -> float:
        """Exact matches score fully, name-only matches half: an agent that
        sent the right message to the wrong number did *some* of the work,
        and pretending otherwise is the all-or-nothing signal again."""
        if not self.gold_total:
            return 0.0
        return (self.exact + 0.5 * (self.covered - self.exact)) / self.gold_total

    def as_dict(self) -> dict:
        return {
            "gold_total": self.gold_total,
            "covered": self.covered,
            "exact": self.exact,
            "coverage": round(self.coverage, 3),
            "fidelity": round(self.fidelity, 3),
            "partial_reward": round(self.partial_reward, 3),
            "pivot": self.pivot,
            "pivot_kind": self.pivot_kind,
        }


def _executed_calls(events: list[dict]) -> list[dict]:
    calls = []
    for event in events:
        if event.get("type") == "call" and event.get("status") == "ok":
            calls.append(event)
        if event.get("type") == "delegation":
            calls.extend(c for c in event.get("calls") or []
                         if c.get("status") == "ok")
    return calls


def _first_fault(events: list[dict], gold_by_tool: dict) -> tuple[int | None, str | None]:
    """The earliest event that went wrong, scanned chronologically."""
    for index, event in enumerate(events):
        kind = event.get("type")
        if kind == "call" and event.get("status") in _FAULT_STATUSES:
            return index, str(event.get("status"))
        if kind == "delegation":
            for call in event.get("calls") or []:
                if call.get("status") in _FAULT_STATUSES:
                    return index, str(call.get("status"))
                if call.get("status") == "ok" and _gold_arg_mismatch(
                        call, gold_by_tool):
                    return index, "wrong-arguments"
            if not (event.get("calls") or []) and any(
                    w in str(event.get("report", "")).lower()
                    for w in _REFUSAL_WORDS):
                return index, "refusal"
        if kind == "surrender":
            return index, "surrender"
        if kind == "stop":
            return index, "environment-stop"
    return None, None


def _checkable(value: str) -> bool:
    """Whether a gold argument value is structured enough that deviation is
    a *fault* rather than a phrasing choice: identifiers, phone numbers,
    datetimes, enum tokens -- not prose. Validating pivots against the four
    hand-audited runs caught this distinction: exact-matching prose branded
    a correctly-reworded message send as the first fault, ahead of the real
    one (a zero-call refusal two delegations later). Prose stays in the
    fidelity *score* as the documented conservative floor; it never places
    the pivot."""
    return " " not in value.strip() or bool(
        __import__("re").fullmatch(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?",
                                   value.strip()))


def _gold_arg_mismatch(call: dict, gold_by_tool: dict) -> bool:
    """True when this call is a gold-type write whose *structured* args
    match no gold variant -- the wrong-arguments fault."""
    variants = gold_by_tool.get(call.get("tool"))
    if not variants:
        return False
    args = call.get("args") or {}
    checked_any = False
    for variant in variants:
        # Empty gold values are omittable optionals (attachment_path: ""),
        # not content to check -- and an agent that omits the key entirely
        # said the same thing as one that passed "".
        checkable = [(n, v) for n, v in variant if v and _checkable(v)]
        if not checkable:
            continue
        checked_any = True
        if all(str(args.get(name, "")) == value for name, value in checkable):
            return False
    return checked_any


def assess(scenario: dict, events: list[dict]) -> Credit:
    """Stamp one trajectory with partial credit and its pivot."""
    gold = gold_writes(scenario)
    gold_by_tool: dict[str, list] = {}
    for write in gold:
        gold_by_tool.setdefault(f"{write.app}__{write.function}", []).append(
            list(write.args))

    remaining = {tool: len(variants) for tool, variants in gold_by_tool.items()}
    unclaimed = {tool: list(variants) for tool, variants in gold_by_tool.items()}
    covered = exact = 0
    for call in _executed_calls(events):
        tool = call.get("tool")
        if remaining.get(tool, 0) <= 0:
            continue
        remaining[tool] -= 1
        covered += 1
        args = call.get("args") or {}
        for variant in unclaimed[tool]:
            if all(str(args.get(name)) == value for name, value in variant):
                unclaimed[tool].remove(variant)
                exact += 1
                break

    pivot, pivot_kind = _first_fault(events, gold_by_tool)
    return Credit(gold_total=len(gold), covered=covered, exact=exact,
                  pivot=pivot, pivot_kind=pivot_kind)


def split_for_replay(events: list[dict], credit: Credit) -> dict:
    """The prefix-replay cut: everything before the pivot is frozen prompt,
    everything from it on is the suffix optimization operates on. A
    trajectory without a located fault has no cut -- its whole length is
    prefix, and the missing work belongs to a suffix that never happened.
    """
    if credit.pivot is None:
        return {"prefix_events": len(events), "suffix_events": 0,
                "pivot": None, "pivot_kind": None}
    return {"prefix_events": credit.pivot,
            "suffix_events": len(events) - credit.pivot,
            "pivot": credit.pivot, "pivot_kind": credit.pivot_kind}
