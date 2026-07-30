"""Structural difficulty of a Gaia2 scenario, read off its oracle-event DAG.

Gold writes carry `dependencies`, so every scenario ships its own difficulty
geometry for free:

  * `writes` -- how many gold writes exist. An upper bound on how much
    delegated work a partition has to route, and one mechanical input to the
    advisory delegation target.
  * `depth`  -- the longest dependency chain among gold writes: forced
    sequencing no topology can parallelise away.
  * `width`  -- the largest number of gold writes at the same dependency
    level: the parallelism a star Main could exploit in one fan-out.

All mechanical, no LLM. Dependencies on non-oracle events (the USER turn,
environment events) count as level zero: they gate *when* work may start,
not which write precedes which.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from forge.gaia2.mine import _INFRA_APPS


@dataclass(frozen=True)
class Structure:
    writes: int
    depth: int
    width: int


def structure_of(scenario: dict) -> Structure:
    """Measure one scenario's oracle-event DAG. Raises on a cyclic one."""
    oracle: dict[str, dict] = {}
    for event in scenario.get("events") or []:
        if event.get("class_name") != "OracleEvent":
            continue
        action = event.get("action") or {}
        if not action.get("app") or action["app"] in _INFRA_APPS:
            continue
        oracle[event.get("event_id", f"anon-{len(oracle)}")] = event

    levels: dict[str, int] = {}
    visiting: set[str] = set()

    def level(event_id: str) -> int:
        if event_id not in oracle:
            return 0  # USER / environment events gate start time, not order
        if event_id in levels:
            return levels[event_id]
        if event_id in visiting:
            raise ValueError(f"dependency cycle through {event_id!r}")
        visiting.add(event_id)
        deps = oracle[event_id].get("dependencies") or []
        levels[event_id] = 1 + max((level(d) for d in deps), default=0)
        visiting.discard(event_id)
        return levels[event_id]

    for event_id in oracle:
        level(event_id)

    if not oracle:
        return Structure(writes=0, depth=0, width=0)
    per_level = Counter(levels.values())
    return Structure(
        writes=len(oracle),
        depth=max(levels.values()),
        width=max(per_level.values()),
    )
