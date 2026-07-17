"""Decide whether a rendered configuration is usable RL data, and measure yield.

The rule this module exists to enforce: **a configuration counts only if its
score lands strictly between the do-nothing floor and the unconstrained
control.**

  * At or below the floor, the run carries no more signal than an agent that
    did nothing. The reward cannot tell trying from not trying, so there is no
    gradient to learn from -- whether the cause was a hard task or a broken
    harness.
  * At or above the control, the constraint never bit. The run measures the
    base task, not the coordination we partitioned for.

This is the same shape as SWE-smith's Fail-to-Pass rule -- a candidate
perturbation counts iff the repo's existing tests go red -- with one difference:
our oracle is graded rather than binary, so the rule is a sandwich rather than a
flip. Both are mechanical, free, and inherit somebody else's judge.

Why this is code and not a paragraph: the rule already existed in prose, and
this repo still published `0.333` as "the partition is hard" for two days. It
was the floor. `select.py` enforces which tasks may be rendered; nothing
enforced which renders were worth training on. A rule nobody runs is a rule that
loses to the flattering number -- so `cli.py judge` runs this one.

Yield is the fraction of measurable cells that come back VALID. SWE-smith
reports 56% / 35% / 40.2% / 33.8% / 96.9% for its five generators and uses them
to decide where to spend. We had no such number for any knob.

**A single seed cannot measure yield.** Validity is a property of the score
distribution over rollouts, not of one draw: one seed cannot separate "this cell
always bottoms out" from "this cell got unlucky once". With `SEEDS_FOR_YIELD`
seeds in *every* cell these functions measure yield; below it they report the
same arithmetic as an *observation*, and `Yield.measured` says which you have.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

#: Until every cell of a config has this many seeds, the ratio these functions
#: return is an observation about the draws in hand, not an estimate of yield.
SEEDS_FOR_YIELD = 5

#: A config whose first *segment* is this is the unconstrained control: same
#: task, same oracle, partition off. It is free -- just turn the knob off.
_CONTROL_PREFIX = "open"


class Verdict(str, Enum):
    """Why a (task, config) cell is or is not usable RL data."""

    VALID = "valid"  # floor < score < control -- the constraint bit, task survived
    DEGENERATE = "degenerate"  # score <= floor -- no signal above doing nothing
    NO_BITE = "no-bite"  # score >= control -- the constraint changed nothing
    CONTROL_FAILED = "control-failed"  # the control is on the floor: unmeasurable
    NO_VARIANCE = "no-variance"  # every replicate scored the same: no advantage


def is_control(config: str) -> bool:
    """Whether this config is the unconstrained control for its task.

    Matched on the first hyphen-separated segment, not as a prefix: `openish`
    starts with `open` and is not the control.
    """
    return config.split("-")[0] == _CONTROL_PREFIX


def is_measurement(row: dict) -> bool:
    """Whether a sweep row is a real measurement rather than a non-event.

    `ran` and `error` are the mechanism-level fields, and they are the only
    thing separating "the agent tried and failed" from "the agent never ran":
    gpt-5.x rejects `temperature=0`, every call 400'd, an `except` swallowed it,
    and the rows reported the *untouched world's score* -- numerically identical
    to genuine failure. A row the sweep never scored (`partial is None`) is the
    same class of non-event.
    """
    return (
        bool(row.get("ran", True))
        and row.get("error") is None
        and row.get("partial") is not None
    )


def judge(score: float, control: float, floor: float) -> Verdict:
    """Classify one (task, config) cell against its two fixed points.

    `control` is checked first: when the unconstrained agent is itself on the
    floor, the base task is broken and no knob's effect on it is measurable.
    Reading a constrained score against a failed control is how a harness bug
    gets written up as difficulty.
    """
    if control <= floor:
        return Verdict.CONTROL_FAILED
    if score <= floor:
        return Verdict.DEGENERATE
    if score >= control:
        return Verdict.NO_BITE
    return Verdict.VALID


@dataclass(frozen=True)
class Judgement:
    task_id: str
    config: str
    score: float
    control: float
    floor: float
    verdict: Verdict

    @property
    def usable(self) -> bool:
        return self.verdict is Verdict.VALID

    @property
    def measurable(self) -> bool:
        """Whether this cell could be judged at all, or its control had failed."""
        return self.verdict is not Verdict.CONTROL_FAILED


def judge_cell(scores: list[float], control: float, floor: float) -> Verdict:
    """Classify a (task, config) *cell* from its replicates.

    This is the verdict that matters for RL data, because the unit of data is the
    task instance, not the rollout: you sample K rollouts of one prompt and the
    gradient comes from how they *differ*. A cell whose replicates all score the
    same has no advantage to give, whatever that score is.

    That last case is `theory-of-mind` wearing a different number. v1's dimension
    scored 1.0 on 12 of 12 -- reward everywhere, variance nowhere, gradient zero
    (WRITEUP.md section 1). Five replicates all landing on 0.833 are the same
    object: comfortably inside the sandwich, and worth nothing. One seed cannot
    express this at all -- a single point has no variance by construction -- which
    is why `SEEDS_FOR_YIELD` exists, and why a 1-seed sweep measures no yield.
    """
    if control <= floor:
        return Verdict.CONTROL_FAILED
    if max(scores) <= floor:
        return Verdict.DEGENERATE  # never rises above doing nothing
    if min(scores) >= control:
        return Verdict.NO_BITE  # always ties the ceiling
    if len(scores) >= 2 and len(set(scores)) == 1:
        return Verdict.NO_VARIANCE  # zero advantage; see above
    return Verdict.VALID


@dataclass(frozen=True)
class Cell:
    """One (task, config) pair and every replicate of it."""

    task_id: str
    config: str
    scores: tuple[float, ...]
    control: float
    floor: float
    verdict: Verdict

    @property
    def usable(self) -> bool:
        return self.verdict is Verdict.VALID

    @property
    def measurable(self) -> bool:
        return self.verdict is not Verdict.CONTROL_FAILED

    @property
    def seeds(self) -> int:
        return len(self.scores)


@dataclass(frozen=True)
class Yield:
    """How many of a config's measurable cells are worth training on."""

    config: str
    valid: int  #: usable *cells*, not rollouts: the unit of RL data is the prompt
    total: int  #: measurable cells only -- see `unmeasurable`
    unmeasurable: int  #: cells whose control failed; not the knob's fault
    seeds: int  #: replicates in the config's *weakest* cell

    @property
    def rate(self) -> float:
        return self.valid / self.total if self.total else 0.0

    @property
    def measured(self) -> bool:
        """Whether `rate` estimates yield, or merely counts the draws in hand."""
        return self.seeds >= SEEDS_FOR_YIELD


def control_by_task(rows: list[dict]) -> dict[str, float]:
    """Each task's control ceiling: the mean of its unconstrained rollouts.

    Mean rather than one row: a dict keyed by task silently keeps whichever
    control row comes *last* in the file, so at more than one seed every verdict
    downstream would depend on JSON row order. Mean rather than max: the ceiling
    a knob is read against should be what the unconstrained agent typically
    reaches, not its luckiest draw -- `max` would manufacture NO_BITE into VALID.

    Non-measurements are excluded here too. A control that never ran is the
    worst row in the sweep to trust, because it defines every other verdict on
    its task.
    """
    scores: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if is_control(r["config"]) and is_measurement(r):
            scores[r["task_id"]].append(r["partial"])
    return {task: sum(v) / len(v) for task, v in scores.items()}


def judge_rows(rows: list[dict], floor: float) -> list[Judgement]:
    """Classify every constrained cell in a sweep. Control rows judge nothing.

    Raises rather than skipping when a task has no control that ran: a
    constrained score has no meaning without the ceiling it is read against, and
    dropping it silently would shrink the denominator of a yield without saying
    so.
    """
    controls = control_by_task(rows)
    out = []
    for r in rows:
        if is_control(r["config"]) or not is_measurement(r):
            continue
        task = r["task_id"]
        if task not in controls:
            raise ValueError(
                f"task {task!r} has no control rollout that ran, so its "
                f"config {r['config']!r} has no ceiling to be read against"
            )
        control = controls[task]
        out.append(
            Judgement(
                task_id=task,
                config=r["config"],
                score=r["partial"],
                control=control,
                floor=floor,
                verdict=judge(r["partial"], control, floor),
            )
        )
    return out


def judge_cells(rows: list[dict], floor: float) -> list[Cell]:
    """Group a sweep into (task, config) cells and judge each from its replicates.

    `judge_rows` scores rollouts, which is the right unit for a table a human
    reads. This is the right unit for a *yield*: the thing you would put in a
    training set is the prompt, and its worth is a property of the spread across
    the rollouts you sample from it.
    """
    controls = control_by_task(rows)
    scores: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in rows:
        if is_control(r["config"]) or not is_measurement(r):
            continue
        task = r["task_id"]
        if task not in controls:
            raise ValueError(
                f"task {task!r} has no control rollout that ran, so its "
                f"config {r['config']!r} has no ceiling to be read against"
            )
        scores[(task, r["config"])].append(r["partial"])

    return [
        Cell(
            task_id=task,
            config=config,
            scores=tuple(vals),
            control=controls[task],
            floor=floor,
            verdict=judge_cell(vals, controls[task], floor),
        )
        for (task, config), vals in sorted(scores.items())
    ]


def yield_by_config(cells: list[Cell]) -> dict[str, Yield]:
    """Yield per config: usable cells over measurable cells.

    Cells whose control failed are reported separately rather than counted as
    failures: blaming a knob for a base task nobody can solve is exactly the
    write-up this module exists to prevent.
    """
    grouped: dict[str, list[Cell]] = defaultdict(list)
    for c in cells:
        grouped[c.config].append(c)

    out = {}
    for config, cs in grouped.items():
        measurable = [c for c in cs if c.measurable]
        out[config] = Yield(
            config=config,
            valid=sum(c.usable for c in measurable),
            total=len(measurable),
            unmeasurable=len(cs) - len(measurable),
            # The weakest cell governs: a config with one 9-replicate task and
            # one 1-replicate task has not been measured at 5, and an average
            # would say it had.
            seeds=min((c.seeds for c in cs), default=0),
        )
    return out
