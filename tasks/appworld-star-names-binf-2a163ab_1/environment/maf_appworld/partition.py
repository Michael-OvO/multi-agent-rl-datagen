"""The constraint layer: turn a single-agent AppWorld task into a multi-agent one
by restricting access, information, and communication -- never by touching the
judge.

## Why constraints and not construction

The dimension this project retired (`theory-of-mind`) built both the world and
the judge. A flaw in the world's design became a flaw in the reward: `q_opt` was
wrong, so obeying the instruction scored 1.0 on 12 of 12 runs with zero
gradient, and every validity gate passed while it happened.

A constraint cannot do that. It changes **who can do what**, never **what counts
as done**. AppWorld's `evaluate()` -- a programmatic state check with no LLM in
it, which also catches side effects -- is the judge, unmodified, for every
configuration here.

The consequence is the whole point: a badly chosen constraint makes a task too
easy or too hard, and that is **measurable** (run it and look at the spread). A
badly designed oracle makes the reward measure the wrong thing, and that is
**invisible**. We are trading an invisible failure mode for a visible one.

## The knobs

Each knob targets one capability from the brief. Every knob must be shown to
move the score against the `open` control, or it is decoration and gets deleted.
That check is not optional: it is the only thing standing between this and a pile
of sub-agents that look impressive and measure nothing.

The roster itself is never a knob -- `select.derive_roster` reads it off the
task's ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Topology(str, Enum):
    """Who may talk to whom. Targets: Main<->Sub and Sub<->Sub communication."""

    #: Control condition: no partition at all. The Main holds every API itself.
    #: This is the ablation twin -- if a configuration does not beat `OPEN` on
    #: difficulty, the partition never tested coordination.
    OPEN = "open"

    #: Main talks to each specialist; specialists cannot talk to each other. All
    #: cross-app facts must pass through the Main.
    STAR = "star"

    #: Specialists are ordered; each may hand off only to the next. The Main
    #: seeds the first. Forces Sub<->Sub relay.
    CHAIN = "chain"


class Visibility(str, Enum):
    """What the Main knows about its specialists. Targets: role-awareness."""

    #: The Main is given each specialist's API documentation up front.
    DOCS = "docs"

    #: The Main is given names only. To learn what a specialist can do it must
    #: ask. This is what makes capability discovery a communication act rather
    #: than a lookup -- and what makes "which specialist could possibly know
    #: this?" a question the Main has to reason about instead of read.
    NAMES = "names"


@dataclass(frozen=True)
class Constraints:
    """One configuration of the constraint layer.

    `roster` is derived from the task, never chosen here.
    """

    roster: tuple[str, ...]
    topology: Topology = Topology.STAR
    visibility: Visibility = Visibility.NAMES
    #: Max delegations the Main may issue. None = unbounded. Targets: planning
    #: over trial-and-error. A budget is a constraint on the world, not a term
    #: in the reward -- the reward stays AppWorld's terminal state check.
    delegation_budget: int | None = None

    def __post_init__(self) -> None:
        if self.topology is not Topology.OPEN and len(self.roster) < 2:
            raise ValueError(
                f"roster {self.roster} has nothing to coordinate; "
                "select.usable() should have dropped this task"
            )
        if self.delegation_budget is not None and self.delegation_budget < len(self.roster):
            raise ValueError(
                f"budget {self.delegation_budget} < roster size {len(self.roster)}: "
                "the task would be unsolvable, which measures nothing"
            )

    @property
    def main_has_apis(self) -> bool:
        """Only the control condition lets the Main touch the environment."""
        return self.topology is Topology.OPEN

    def allowed_targets(self, sender: str) -> tuple[str, ...]:
        """Who `sender` may send a request to under this topology."""
        if self.topology is Topology.OPEN:
            return ()
        if self.topology is Topology.STAR:
            return self.roster if sender == "main" else ()
        # CHAIN: main seeds the head; each specialist may hand off to the next.
        if sender == "main":
            return (self.roster[0],)
        if sender in self.roster:
            i = self.roster.index(sender)
            return (self.roster[i + 1],) if i + 1 < len(self.roster) else ()
        return ()

    @property
    def label(self) -> str:
        budget = "inf" if self.delegation_budget is None else str(self.delegation_budget)
        return f"{self.topology.value}-{self.visibility.value}-b{budget}"


def control_for(roster: tuple[str, ...]) -> Constraints:
    """The ablation twin for any configuration: same task, same oracle, no partition.

    This is the comparison every configuration must win. It is free -- we do not
    design it, we just turn the knob off.
    """
    return Constraints(roster=roster, topology=Topology.OPEN, visibility=Visibility.DOCS)
