"""Select AppWorld tasks that can carry a multi-agent constraint, and derive
each one's roster from what the task actually needs.

The rule this module exists to enforce: **the task decides the partition, we
never do.** A task's roster is the set of apps its ground-truth solution really
touches. We never choose how many specialists a task gets, and we never pad a
task with a specialist it does not need. A task that cannot be coordinated is
dropped, not decorated.

Why that rule is load-bearing: `supervisor.complete_task` is how *every* task
submits its answer. Counting `supervisor` as a collaborator turns all 147
ground-truth tasks into "multi-app" ones -- and 96 of them are single-app
puzzles that would ship with a decorative second agent, pass every check, and
measure nothing. Measured 2026-07-15: naive filter says 147/147 usable; the
strict filter below says 51/147.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# `apis.<app>.<method>(` in a ground-truth solution.
_CALL = re.compile(r"apis\.(\w+)\.(\w+)\(")

# Apps that are never a coordination role:
#   api_docs   - documentation lookup, available to everyone
#   admin      - environment internals, not agent-facing
_INFRA_APPS = frozenset({"api_docs", "admin"})

# Individual APIs that are infrastructure even though their app is not.
# `supervisor.complete_task` is the submit channel: every task calls it exactly
# to hand in its answer. It carries no information between apps, so a
# "supervisor specialist" would have nothing to coordinate about.
_INFRA_APIS = frozenset({("supervisor", "complete_task")})

MIN_ROSTER = 2  # below this there is no coordination to test


@dataclass
class TaskSpan:
    """What a task actually requires, measured from its ground truth."""

    task_id: str
    split: str
    instruction: str
    roster: tuple[str, ...]  # the specialists this task needs, task-determined
    calls: tuple[tuple[str, str], ...] = field(default=())

    @property
    def usable(self) -> bool:
        return len(self.roster) >= MIN_ROSTER


def parse_calls(solution_code: str) -> list[tuple[str, str]]:
    """Every (app, api) pair the ground-truth solution invokes, in order."""
    return _CALL.findall(solution_code or "")


def derive_roster(solution_code: str) -> tuple[str, ...]:
    """The specialists a task needs: apps it touches for real work.

    Excludes infrastructure apps and the submit channel. Sorted for stability --
    a task's roster must not depend on call order, or the same task would render
    differently across runs.
    """
    apps = {
        app
        for app, api in parse_calls(solution_code)
        if app not in _INFRA_APPS and (app, api) not in _INFRA_APIS
    }
    return tuple(sorted(apps))


def span_of(task_id: str, split: str, instruction: str, solution_code: str) -> TaskSpan:
    return TaskSpan(
        task_id=task_id,
        split=split,
        instruction=instruction,
        roster=derive_roster(solution_code),
        calls=tuple(parse_calls(solution_code)),
    )


def usable(spans: list[TaskSpan]) -> list[TaskSpan]:
    """Tasks with real coordination in them. The rest are dropped, not padded."""
    return [s for s in spans if s.usable]
